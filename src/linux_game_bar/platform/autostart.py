"""XDG Autostart management for Linux Game Bar."""

import os
import logging
from pathlib import Path

logger = logging.getLogger("linux_game_bar.autostart")


class AutostartManager:
    """Manages ~/.config/autostart desktop entry for user login."""

    def __init__(self, autostart_dir: Path = None):
        if autostart_dir:
            self.autostart_dir = autostart_dir
        else:
            config_home = os.environ.get("XDG_CONFIG_HOME")
            base = Path(config_home) if config_home else Path.home() / ".config"
            self.autostart_dir = base / "autostart"

        self.desktop_file = self.autostart_dir / "linux-game-bar.desktop"

    def is_enabled(self) -> bool:
        """Check if autostart desktop entry exists and is active."""
        if not self.desktop_file.exists():
            return False
        try:
            with open(self.desktop_file, "r", encoding="utf-8") as f:
                content = f.read()
                if "X-GNOME-Autostart-enabled=false" in content:
                    return False
            return True
        except Exception:
            return False

    def enable(self, exec_cmd: str = "linux-game-bar") -> bool:
        """Create or update autostart desktop entry."""
        try:
            self.autostart_dir.mkdir(parents=True, exist_ok=True)
            content = f"""[Desktop Entry]
Type=Application
Name=Linux Game Bar
GenericName=Gaming Overlay
Comment=Xbox Game Bar-inspired overlay for Ubuntu GNOME
Exec={exec_cmd}
Icon=input-gaming
Terminal=false
Categories=Utility;Game;
StartupNotify=false
X-GNOME-Autostart-enabled=true
"""
            with open(self.desktop_file, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Enabled login autostart via {self.desktop_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to enable autostart: {e}")
            return False

    def disable(self) -> bool:
        """Remove autostart desktop entry."""
        try:
            if self.desktop_file.exists():
                self.desktop_file.unlink()
                logger.info(f"Removed autostart file {self.desktop_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to disable autostart: {e}")
            return False
