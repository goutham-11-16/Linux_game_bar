"""
Widget Installer and Package Manager for Linux Game Bar Widget SDK.
Enables end users and developers to install, manage, and uninstall third-party widgets
from GitHub repositories, local .zip files, and project folders.
"""

import os
import sys
import shutil
import zipfile
import logging
import tempfile
import subprocess
import importlib.util
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from linux_game_bar.single_instance import SingleInstanceManager

logger = logging.getLogger("linux_game_bar.sdk.installer")


class WidgetInstaller:
    """Manages downloading, verifying, installing, and uninstalling widgets."""

    PLUGINS_DIR = Path.home() / ".local" / "share" / "linux-game-bar" / "plugins"

    @classmethod
    def get_plugins_dir(cls) -> Path:
        cls.PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
        return cls.PLUGINS_DIR

    @classmethod
    def install(cls, source: str) -> Tuple[bool, str, Optional[str]]:
        """
        Universal installer entry point.
        Accepts:
        - GitHub / Git URL (e.g. 'https://github.com/user/my-widget' or 'git@github.com:...')
        - Local .zip archive (e.g. '/path/to/my-widget.zip')
        - Local folder or .py file (e.g. '/path/to/my-widget')
        """
        source = source.strip()
        if not source:
            return False, "Empty source provided.", None

        if source.startswith(("http://", "https://", "git@")) or source.endswith(".git"):
            return cls.install_from_git(source)
        elif source.lower().endswith(".zip") and os.path.exists(source):
            return cls.install_from_zip(source)
        elif os.path.exists(source):
            return cls.install_from_path(source)
        else:
            return False, f"Source '{source}' is not a valid URL or existing file/directory.", None

    @classmethod
    def install_from_git(cls, repo_url: str) -> Tuple[bool, str, Optional[str]]:
        """Clones a Git repository into a temporary directory and installs it."""
        logger.info(f"Installing widget from Git repository: {repo_url}")
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "cloned_widget"
            try:
                res = subprocess.run(
                    ["git", "clone", "--depth", "1", repo_url, str(tmp_path)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if res.returncode != 0:
                    err_msg = res.stderr.strip() or "Git clone failed."
                    logger.error(f"Git clone error: {err_msg}")
                    return False, f"Failed to clone repository: {err_msg}", None

                git_dir = tmp_path / ".git"
                if git_dir.exists():
                    shutil.rmtree(git_dir, ignore_errors=True)

                return cls.install_from_path(str(tmp_path))

            except FileNotFoundError:
                return False, "Git CLI is not installed on this system.", None
            except Exception as ex:
                logger.exception(f"Unexpected error installing from git: {ex}")
                return False, f"Install error: {str(ex)}", None

    @classmethod
    def install_from_zip(cls, zip_path: str) -> Tuple[bool, str, Optional[str]]:
        """Extracts a .zip archive into a temporary directory and installs it."""
        logger.info(f"Installing widget from zip: {zip_path}")
        if not os.path.isfile(zip_path):
            return False, f"File does not exist: {zip_path}", None

        with tempfile.TemporaryDirectory() as tmp_dir:
            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(tmp_dir)

                entries = [Path(tmp_dir) / e for e in os.listdir(tmp_dir)]
                if len(entries) == 1 and entries[0].is_dir():
                    target_source = str(entries[0])
                else:
                    target_source = tmp_dir

                return cls.install_from_path(target_source)

            except zipfile.BadZipFile:
                return False, f"Invalid or corrupted ZIP archive: {zip_path}", None
            except Exception as ex:
                logger.exception(f"Unexpected error extracting zip: {ex}")
                return False, f"Extraction error: {str(ex)}", None

    @classmethod
    def install_from_path(cls, source_path: str) -> Tuple[bool, str, Optional[str]]:
        """Validates plugin structure and copies files into the user plugins directory."""
        src = Path(source_path).resolve()
        if not src.exists():
            return False, f"Source path does not exist: {source_path}", None

        valid, err, widget_id, meta_title = cls._inspect_plugin(src)
        if not valid or not widget_id:
            return False, f"Validation failed: {err}", None

        dest_dir = cls.get_plugins_dir() / widget_id
        try:
            if dest_dir.exists():
                shutil.rmtree(dest_dir)

            if src.is_dir():
                shutil.copytree(src, dest_dir)
            else:
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest_dir / "plugin.py")

            logger.info(f"Successfully installed widget '{meta_title}' ({widget_id}) to {dest_dir}")
            cls.notify_daemon_reload()
            return True, f"Widget '{meta_title}' ({widget_id}) installed successfully!", widget_id

        except Exception as ex:
            logger.exception(f"Failed copying plugin to {dest_dir}: {ex}")
            return False, f"Failed installing files: {str(ex)}", None

    @classmethod
    def _inspect_plugin(cls, path: Path) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """
        Inspects directory or python file to verify valid XboxGameBarWidgetPlugin or GameBarWidgetPlugin
        and extracts METADATA.id and METADATA.title.
        """
        candidate_file: Optional[Path] = None
        if path.is_file() and path.suffix == ".py":
            candidate_file = path
        elif path.is_dir():
            for name in ("plugin.py", "__init__.py", "main.py"):
                f = path / name
                if f.exists():
                    candidate_file = f
                    break
            if not candidate_file:
                py_files = list(path.glob("*.py"))
                if len(py_files) == 1:
                    candidate_file = py_files[0]

        if not candidate_file or not candidate_file.exists():
            return False, "No valid Python plugin entrypoint found (expected plugin.py or __init__.py).", None, None

        mod_name = f"_inspect_{abs(hash(str(candidate_file)))}"
        try:
            spec = importlib.util.spec_from_file_location(mod_name, str(candidate_file))
            if not spec or not spec.loader:
                return False, f"Could not create loader spec for {candidate_file}", None, None

            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)

            from linux_game_bar.sdk.widget import XboxGameBarWidgetPlugin, GameBarWidgetPlugin
            import inspect

            for _, obj in inspect.getmembers(mod, inspect.isclass):
                if issubclass(obj, (XboxGameBarWidgetPlugin, GameBarWidgetPlugin)) and obj not in (
                    XboxGameBarWidgetPlugin,
                    GameBarWidgetPlugin,
                ):
                    meta = getattr(obj, "METADATA", None)
                    if meta and getattr(meta, "id", None):
                        title = getattr(meta, "title", meta.id)
                        return True, "Valid", meta.id, title

            return False, "No class inheriting from XboxGameBarWidgetPlugin found with valid METADATA.", None, None

        except Exception as ex:
            return False, f"Error inspecting plugin script: {str(ex)}", None, None
        finally:
            sys.modules.pop(mod_name, None)

    @classmethod
    def list_installed_plugins(cls) -> List[Dict[str, str]]:
        """Returns a list of all installed third-party plugins in plugins directory."""
        plugins = []
        p_dir = cls.get_plugins_dir()
        if not p_dir.exists():
            return plugins

        for entry in p_dir.iterdir():
            if entry.is_dir():
                valid, _, w_id, title = cls._inspect_plugin(entry)
                if valid and w_id:
                    plugins.append({
                        "id": w_id,
                        "title": title or w_id,
                        "folder_name": entry.name,
                        "path": str(entry),
                    })
        return plugins

    @classmethod
    def uninstall_plugin(cls, plugin_id: str) -> Tuple[bool, str]:
        """Removes a plugin folder and notifies the running overlay to reload."""
        p_dir = cls.get_plugins_dir()
        target = p_dir / plugin_id
        if not target.exists():
            for entry in p_dir.iterdir():
                if entry.name == plugin_id:
                    target = entry
                    break

        if not target.exists():
            return False, f"Plugin '{plugin_id}' not found."

        try:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                os.remove(target)
            logger.info(f"Uninstalled plugin '{plugin_id}' from {target}")
            cls.notify_daemon_reload()
            return True, f"Widget '{plugin_id}' uninstalled successfully."
        except Exception as ex:
            logger.exception(f"Failed to uninstall plugin {plugin_id}: {ex}")
            return False, f"Uninstall error: {str(ex)}"

    @classmethod
    def notify_daemon_reload(cls) -> bool:
        """Sends an IPC reload signal to the running Game Bar daemon."""
        return SingleInstanceManager.send_command("reload")
