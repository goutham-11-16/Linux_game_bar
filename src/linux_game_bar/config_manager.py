"""Configuration manager with atomic JSON persistence and fallback protection."""

import json
import os
import shutil
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("linux_game_bar.config")


DEFAULT_CONFIG: Dict[str, Any] = {
    "theme": "xbox_dark",
    "accent_color": "#107C10",
    "overlay_opacity": 0.88,
    "hotkey": "<Super>g",
    "fallback_hotkey": "<Control><Alt>g",
    "autostart": False,
    "metrics": {
        "sampling_interval_ms": 1000,
        "history_points": 45,
        "show_per_core_cpu": False,
        "thermal_warning_c": 85.0,
    },
    "audio": {
        "preferred_backend": "pipewire",
        "step_percentage": 5,
    },
    "capture": {
        "screenshot_directory": "~/Pictures/Captures",
        "recording_directory": "~/Videos/Captures",
        "record_framerate": 30,
        "include_cursor": True,
        "audio_capture": True,
        "clean_background_capture": False,
        "screenshot_hotkey": "<Super><Alt>Print",
    },
    "autotyper": {
        "engine_enabled": True,
    },
    "launcher": {
        "favorites": ["steam", "discord", "lutris", "heroic", "obs"],
        "show_recent": True,
        "custom_entries": [],
    },
    "notes": {
        "auto_save_interval_ms": 1500,
    },
    "timer": {
        "default_duration_seconds": 1500,
        "sound_enabled": True,
    },
    "ui": {
        "open_widgets": ["performance", "audio", "capture"],
        "pinned_widgets": [],
        "widget_positions": {
            "performance": {"x": 40, "y": 90, "width": 320, "height": 440},
            "audio": {"x": 380, "y": 90, "width": 340, "height": 420},
            "capture": {"x": 740, "y": 90, "width": 380, "height": 520},
            "launcher": {"x": 380, "y": 90, "width": 480, "height": 460},
            "battery": {"x": 1080, "y": 90, "width": 300, "height": 340},
            "notes": {"x": 740, "y": 90, "width": 360, "height": 450},
            "timer": {"x": 1080, "y": 90, "width": 300, "height": 320},
        },
    },
}


class ConfigManager:
    """Manages reading, merging, validating, and saving configuration."""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path:
            self.config_path = config_path
        else:
            config_home = os.environ.get("XDG_CONFIG_HOME")
            base = Path(config_home) if config_home else Path.home() / ".config"
            self.config_path = base / "linux-game-bar" / "settings.json"

        self.config_dir = self.config_path.parent
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.data: Dict[str, Any] = {}
        self.load()

    def get(self, key: str, default: Any = None) -> Any:
        """Get value for a dot-separated key, e.g. 'metrics.sampling_interval_ms'."""
        parts = key.split(".")
        current = self.data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current

    def set(self, key: str, value: Any, auto_save: bool = True) -> None:
        """Set value for a dot-separated key and optionally persist."""
        parts = key.split(".")
        current = self.data
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
        if auto_save:
            self.save()

    def load(self) -> None:
        """Load configuration from disk with deep merge against defaults."""
        self.data = json.loads(json.dumps(DEFAULT_CONFIG))

        if not self.config_path.exists():
            logger.info(f"No existing config at {self.config_path}. Initializing defaults.")
            self.save()
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                user_data = json.load(f)
                self._deep_merge(self.data, user_data)
        except Exception as e:
            logger.error(f"Error reading config file {self.config_path}: {e}. Creating backup and resetting to defaults.")
            backup_path = self.config_path.with_suffix(".json.bak")
            try:
                shutil.copyfile(self.config_path, backup_path)
            except Exception:
                pass
            self.save()
            return

        if "capture" in self.data and isinstance(self.data["capture"], dict):
            self.data["capture"].setdefault("clean_background_capture", False)
            self.data["capture"].setdefault("screenshot_hotkey", "<Super><Alt>Print")

    def save(self) -> None:
        """Persist current configuration atomically using a temp file."""
        tmp_path = self.config_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
            os.replace(tmp_path, self.config_path)
        except Exception as e:
            logger.error(f"Failed to atomically write config to {self.config_path}: {e}")
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass

    def reset_to_defaults(self) -> None:
        """Reset configuration to factory defaults."""
        self.data = json.loads(json.dumps(DEFAULT_CONFIG))
        self.save()

    def _deep_merge(self, base: dict, override: dict) -> None:
        """Recursively update base dictionary with override values."""
        for key, val in override.items():
            if isinstance(val, dict) and key in base and isinstance(base[key], dict):
                self._deep_merge(base[key], val)
            else:
                base[key] = val
