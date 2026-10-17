"""GNOME Shell custom shortcut integration via GSettings."""

import ast
import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Tuple

logger = logging.getLogger("linux_game_bar.gnome")

SCHEMA_MEDIA_KEYS = "org.gnome.settings-daemon.plugins.media-keys"
SCHEMA_CUSTOM_KEY = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
KEY_CUSTOM_BINDINGS = "custom-keybindings"
DEFAULT_SHORTCUT_NAME = "Linux Game Bar"
DEFAULT_SCREENSHOT_SHORTCUT_NAME = "Linux Game Bar Screenshot"
SHORTCUT_PATH_PREFIX = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"


class GnomeShortcutManager:
    """Manages registering, querying, and unregistering GNOME global shortcuts."""

    def __init__(self, backup_file: Optional[Path] = None):
        self.gsettings_bin = shutil.which("gsettings")
        if backup_file:
            self.backup_file = backup_file
        else:
            self.backup_file = Path.home() / ".config" / "linux-game-bar" / "shortcut_backup.json"

    def is_available(self) -> bool:
        """Check if gsettings tool is present."""
        return self.gsettings_bin is not None

    def get_custom_bindings(self) -> List[str]:
        """Return list of registered custom binding paths."""
        if not self.is_available():
            return []
        try:
            res = subprocess.run(
                [self.gsettings_bin, "get", SCHEMA_MEDIA_KEYS, KEY_CUSTOM_BINDINGS],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                timeout=3,
            )
            raw = res.stdout.strip()
            # Parse output like: @as [] or ['/path/to/custom0/', ...]
            if raw.startswith("@as "):
                raw = raw[4:]
            parsed = ast.literal_eval(raw)
            return list(parsed) if isinstance(parsed, (list, tuple)) else []
        except Exception as e:
            logger.error(f"Failed to read custom keybindings: {e}")
            return []

    def set_custom_bindings(self, paths: List[str]) -> bool:
        """Set the array of custom keybinding paths."""
        if not self.is_available():
            return False
        try:
            # GSettings expects format "['path1', 'path2']"
            formatted = str(paths)
            subprocess.run(
                [self.gsettings_bin, "set", SCHEMA_MEDIA_KEYS, KEY_CUSTOM_BINDINGS, formatted],
                check=True,
                timeout=3,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to write custom keybinding array: {e}")
            return False

    def get_binding_details(self, path: str) -> Dict[str, str]:
        """Fetch name, command, and binding for a custom keybinding path."""
        details = {"path": path, "name": "", "command": "", "binding": ""}
        if not self.is_available():
            return details
        schema_path = f"{SCHEMA_CUSTOM_KEY}:{path}"
        for key in ("name", "command", "binding"):
            try:
                res = subprocess.run(
                    [self.gsettings_bin, "get", schema_path, key],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                    timeout=2,
                )
                val = res.stdout.strip()
                if val.startswith("'") and val.endswith("'"):
                    val = val[1:-1]
                details[key] = val
            except Exception:
                pass
        return details

    def check_conflict(self, requested_shortcut: str) -> Optional[Tuple[str, str]]:
        """Check if requested_shortcut conflicts with an existing custom keybinding.

        Returns (conflicting_name, conflicting_command) or None.
        """
        norm_req = requested_shortcut.lower().replace(" ", "")
        for path in self.get_custom_bindings():
            details = self.get_binding_details(path)
            if details["name"] in (DEFAULT_SHORTCUT_NAME, DEFAULT_SCREENSHOT_SHORTCUT_NAME):
                continue
            if details["binding"].lower().replace(" ", "") == norm_req:
                return (details["name"], details["command"])
        return None

    def register_shortcut(self, command: str, shortcut: str = "<Super>g", name: str = DEFAULT_SHORTCUT_NAME) -> bool:
        """Register or update global shortcut in GNOME."""
        if not self.is_available():
            logger.error("gsettings not found on system.")
            return False

        current_paths = self.get_custom_bindings()

        # Save backup of initial state before making any modifications
        self._save_backup(current_paths)

        # Check if our shortcut is already registered
        target_path: Optional[str] = None
        for path in current_paths:
            details = self.get_binding_details(path)
            if details["name"] == name:
                target_path = path
                break

        # Allocate new path if not found
        if not target_path:
            # Find next free index
            idx = 0
            while True:
                candidate = f"{SHORTCUT_PATH_PREFIX}custom{idx}/"
                if candidate not in current_paths:
                    target_path = candidate
                    break
                idx += 1
            current_paths.append(target_path)

        schema_path = f"{SCHEMA_CUSTOM_KEY}:{target_path}"
        try:
            subprocess.run([self.gsettings_bin, "set", schema_path, "name", name], check=True, timeout=2)
            subprocess.run([self.gsettings_bin, "set", schema_path, "command", command], check=True, timeout=2)
            subprocess.run([self.gsettings_bin, "set", schema_path, "binding", shortcut], check=True, timeout=2)
            # Update the main bindings list
            self.set_custom_bindings(current_paths)
            logger.info(f"Registered GNOME shortcut '{shortcut}' -> '{command}' at {target_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to register GNOME shortcut: {e}")
            return False

    def unregister_shortcut(self, name: str = DEFAULT_SHORTCUT_NAME) -> bool:
        """Remove the application's custom keybinding from GNOME."""
        if not self.is_available():
            return False

        current_paths = self.get_custom_bindings()
        paths_to_remove = []

        for path in current_paths:
            details = self.get_binding_details(path)
            if details["name"] == name:
                paths_to_remove.append(path)
                # Reset individual keys
                schema_path = f"{SCHEMA_CUSTOM_KEY}:{path}"
                try:
                    subprocess.run([self.gsettings_bin, "reset-recursively", schema_path], timeout=2)
                except Exception:
                    pass

        if paths_to_remove:
            new_paths = [p for p in current_paths if p not in paths_to_remove]
            self.set_custom_bindings(new_paths)
            logger.info(f"Unregistered GNOME shortcut for '{name}'")
            return True

        return False

    def _save_backup(self, paths: List[str]) -> None:
        """Save a snapshot of existing bindings to restore if needed."""
        try:
            self.backup_file.parent.mkdir(parents=True, exist_ok=True)
            if not self.backup_file.exists():
                data = {"original_paths": paths}
                with open(self.backup_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save shortcut backup: {e}")
