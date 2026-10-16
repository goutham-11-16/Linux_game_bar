"""Unit tests for LauncherWidget, browser detection, and custom applications."""

import os
from pathlib import Path
from linux_game_bar.config_manager import ConfigManager
from linux_game_bar.widgets.launcher import LauncherWidget, DesktopScanner, AppEntry, AddAppDialog


def test_desktop_scanner_discovers_applications():
    apps = DesktopScanner.scan_applications()
    assert isinstance(apps, list)
    assert len(apps) > 0
    # Common applications on Ubuntu
    app_names = [a.name.lower() for a in apps]
    assert any("settings" in n or "terminal" in n or "files" in n for n in app_names)


def test_browser_detection():
    browsers = DesktopScanner.detect_browsers()
    assert isinstance(browsers, list)
    assert len(browsers) > 0
    # On this machine, Brave, Firefox, or Chrome are installed
    names = [b.name for b in browsers]
    assert any("Firefox" in n or "Brave" in n or "Chrome" in n for n in names)


def test_custom_application_addition_and_persistence(qapp, tmp_path: Path):
    cfg_file = tmp_path / "settings.json"
    cfg = ConfigManager(config_path=cfg_file)

    widget = LauncherWidget(config_manager=cfg)

    # Add a custom app programmatically
    custom_app = AppEntry(
        id="custom_game_1",
        name="Retro Game Emulator",
        exec_cmd="/usr/bin/echo -fullscreen",
        icon="application-x-executable",
        is_game=True,
        is_custom=True,
        is_favorite=True,
    )
    widget.custom_apps.append(custom_app)
    widget._save_custom_apps()

    # Re-instantiate widget to verify persistence
    widget2 = LauncherWidget(config_manager=cfg)
    assert any(a.name == "Retro Game Emulator" for a in widget2.custom_apps)
    saved_entries = cfg.get("launcher.custom_entries", [])
    assert any(e.get("name") == "Retro Game Emulator" for e in saved_entries)


def test_safe_execution_prevents_shell_injection(qapp, tmp_path: Path, monkeypatch):
    """Verify that command execution uses argument vectors, not raw shell concatenation."""
    cfg = ConfigManager(config_path=tmp_path / "settings.json")
    widget = LauncherWidget(config_manager=cfg)

    executed_calls = []

    from PySide6.QtCore import QProcess
    orig_start = QProcess.startDetached

    def fake_start_detached(program, arguments):
        executed_calls.append((program, arguments))
        return True

    monkeypatch.setattr(QProcess, "startDetached", fake_start_detached)

    # Malicious injection attempt in exec string
    malicious_app = AppEntry(
        id="injection_test",
        name="Dangerous App",
        exec_cmd="/bin/echo 'hello'; rm -rf /fake/path",
        icon="icon",
    )
    widget._execute_app(malicious_app)

    assert len(executed_calls) == 1
    prog, args = executed_calls[0]
    assert prog == "/bin/echo"
    # Semicolon and subsequent args are passed safely as separate literal string arguments
    assert "rm" in args
    assert "-rf" in args
