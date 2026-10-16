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
    parser.add_argument("--setup-shortcut", action="store_true", help="Register GNOME Super+G shortcut")
    parser.add_argument("--remove-shortcut", action="store_true", help="Unregister GNOME shortcut")
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
    if args.setup_shortcut:
        mgr = GnomeShortcutManager()
        import shutil
        exec_bin = shutil.which("linux-game-bar") or str(Path.home() / ".local" / "bin" / "linux-game-bar")
        cmd = f"{exec_bin} --toggle"
        ok = mgr.register_shortcut(cmd, shortcut="<Super>g")
        if ok:
            print("Successfully registered GNOME shortcut Super + G ->", cmd)
            return 0
        else:
            print("Failed to register GNOME shortcut. Check logs.")
            return 1

    if args.remove_shortcut:
        mgr = GnomeShortcutManager()
        ok = mgr.unregister_shortcut()
        if ok:
            print("Successfully unregistered GNOME shortcut.")
            return 0
        else:
            print("No Linux Game Bar shortcut found to unregister.")
            return 0

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
