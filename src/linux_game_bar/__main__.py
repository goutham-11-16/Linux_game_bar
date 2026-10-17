"""Command line interface and main entrypoint for Linux Game Bar."""

import sys
import argparse
import logging
from pathlib import Path

from linux_game_bar import __version__
from linux_game_bar.platform.detector import EnvironmentDetector
from linux_game_bar.platform.gnome_integration import GnomeShortcutManager
from linux_game_bar.single_instance import SingleInstanceManager
from linux_game_bar.application import LinuxGameBarApp

logger = logging.getLogger("linux_game_bar.cli")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="linux-game-bar",
        description="Xbox Game Bar-inspired overlay for Ubuntu GNOME",
    )
    parser.add_argument("--version", action="version", version=f"Linux Game Bar {__version__}")
    parser.add_argument("--toggle", action="store_true", help="Toggle overlay visibility")
    parser.add_argument("--show", action="store_true", help="Show overlay dashboard")
    parser.add_argument("--hide", action="store_true", help="Hide overlay dashboard")
    parser.add_argument("--quit", action="store_true", help="Quit running daemon instance")
    parser.add_argument("--diagnostics", action="store_true", help="Print platform capabilities diagnostic report")
    parser.add_argument("--screenshot", action="store_true", help="Take a silent screenshot without opening Game Bar")
    parser.add_argument("--setup-shortcut", action="store_true", help="Register GNOME global shortcuts (Super+G and Super+Alt+Print)")
    parser.add_argument("--setup-screenshot-shortcut", action="store_true", help="Register GNOME Super+Alt+Print screenshot shortcut")
    parser.add_argument("--remove-shortcut", action="store_true", help="Unregister GNOME shortcuts")
    parser.add_argument("--daemon", action="store_true", help="Start background daemon without opening overlay")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose debug logging")
    parser.add_argument("--install", metavar="SOURCE", help="Install widget from Git URL, ZIP, or folder")
    parser.add_argument("--list-plugins", action="store_true", help="List installed widgets")
    parser.add_argument("--remove-plugin", metavar="ID", help="Remove an installed widget")
    parser.add_argument("command", nargs="?", choices=["install", "list-plugins", "remove-plugin"], help="Widget management command")
    parser.add_argument("target", nargs="?", help="Target URL, zip file, or widget ID")

    args = parser.parse_args()

    # Widget Package Management CLI
    if args.command == "install" or args.install:
        from linux_game_bar.sdk.installer import WidgetInstaller
        src = args.target or args.install
        if not src:
            print("Error: Missing target repository URL, zip file, or folder path to install.")
            return 1
        print(f"Installing widget from: {src} ...")
        ok, msg, wid = WidgetInstaller.install(src)
        if ok:
            print(f"SUCCESS: {msg}")
            return 0
        else:
            print(f"FAILED: {msg}")
            return 1

    if args.command == "list-plugins" or args.list_plugins:
        from linux_game_bar.sdk.installer import WidgetInstaller
        plugins = WidgetInstaller.list_installed_plugins()
        if not plugins:
            print("No third-party widgets installed.")
            return 0
        print(f"Installed Third-Party Widgets ({len(plugins)}):")
        print(f"{'ID':<32} {'TITLE':<24} {'PATH'}")
        print("-" * 80)
        for p in plugins:
            print(f"{p['id']:<32} {p['title']:<24} {p['path']}")
        return 0

    if args.command == "remove-plugin" or args.remove_plugin:
        from linux_game_bar.sdk.installer import WidgetInstaller
        target_id = args.target or args.remove_plugin
        if not target_id:
            print("Error: Missing widget ID to remove.")
            return 1
        ok, msg = WidgetInstaller.uninstall_plugin(target_id)
        if ok:
            print(f"SUCCESS: {msg}")
            return 0
        else:
            print(f"FAILED: {msg}")
            return 1

    # 1. Diagnostics flag
    if args.diagnostics:
        caps = EnvironmentDetector.detect()
        print(caps.summary())
        return 0

    # 2. GNOME Shortcut Management flags
    if args.setup_shortcut or args.setup_screenshot_shortcut:
        from linux_game_bar.platform.gnome_integration import (
            GnomeShortcutManager,
            DEFAULT_SHORTCUT_NAME,
            DEFAULT_SCREENSHOT_SHORTCUT_NAME,
        )
        mgr = GnomeShortcutManager()
        import shutil
        exec_bin = shutil.which("linux-game-bar") or str(Path.home() / ".local" / "bin" / "linux-game-bar")

        res_ok = True
        if args.setup_shortcut:
            cmd = f"{exec_bin} --toggle"
            ok_toggle = mgr.register_shortcut(cmd, shortcut="<Super>g", name=DEFAULT_SHORTCUT_NAME)
            if ok_toggle:
                print("Successfully registered GNOME shortcut Super + G ->", cmd)
            else:
                print("Failed to register GNOME shortcut Super + G.")
                res_ok = False

        # Register screenshot shortcut
        snap_cmd = f"{exec_bin} --screenshot"
        ok_snap = mgr.register_shortcut(snap_cmd, shortcut="<Super><Alt>Print", name=DEFAULT_SCREENSHOT_SHORTCUT_NAME)
        if ok_snap:
            print("Successfully registered GNOME screenshot shortcut Super + Alt + Print ->", snap_cmd)
        else:
            print("Failed to register GNOME screenshot shortcut.")
            res_ok = False

        return 0 if res_ok else 1

    if args.remove_shortcut:
        from linux_game_bar.platform.gnome_integration import (
            GnomeShortcutManager,
            DEFAULT_SHORTCUT_NAME,
            DEFAULT_SCREENSHOT_SHORTCUT_NAME,
        )
        mgr = GnomeShortcutManager()
        mgr.unregister_shortcut(name=DEFAULT_SHORTCUT_NAME)
        mgr.unregister_shortcut(name=DEFAULT_SCREENSHOT_SHORTCUT_NAME)
        print("Successfully unregistered GNOME shortcuts.")
        return 0

    # 3. Single Instance Command Forwarding
    if args.screenshot:
        if SingleInstanceManager.send_command("screenshot"):
            print("Requested background screenshot capture.")
            return 0
        from linux_game_bar.platform.portals import CaptureService
        service = CaptureService()
        ok, path_or_msg = service.take_screenshot(interactive=False)
        if ok:
            print(f"Screenshot captured: {path_or_msg}")
            return 0
        else:
            print(f"Capture failed: {path_or_msg}")
            return 1

    # 3. Single Instance Command Forwarding
    if args.quit:
        if SingleInstanceManager.send_command("quit"):
            print("Requested running instance to quit.")
            return 0
        else:
            print("No running instance found.")
            return 0

    if args.toggle:
        if SingleInstanceManager.send_command("toggle"):
            # Successfully toggled existing instance
            return 0
        # If no instance was running, start it and show
        app = LinuxGameBarApp(verbose=args.verbose)
        return app.run(show_immediately=True)

    if args.show:
        if SingleInstanceManager.send_command("show"):
            return 0
        app = LinuxGameBarApp(verbose=args.verbose)
        return app.run(show_immediately=True)

    if args.hide:
        if SingleInstanceManager.send_command("hide"):
            return 0
        return 0

    # Default launch
    if SingleInstanceManager.send_command("toggle"):
        print("Toggled existing running instance.")
        return 0

    app = LinuxGameBarApp(verbose=args.verbose)
    return app.run(show_immediately=not args.daemon)


if __name__ == "__main__":
    sys.exit(main())
