"""Unit tests for ConfigManager."""

import json
from pathlib import Path
from linux_game_bar.config_manager import ConfigManager, DEFAULT_CONFIG


def test_config_initialization_creates_file(tmp_path: Path):
    cfg_file = tmp_path / "settings.json"
    mgr = ConfigManager(config_path=cfg_file)
    assert cfg_file.exists()
    assert mgr.get("theme") == "xbox_dark"
    assert mgr.get("hotkey") == "<Super>g"


def test_config_get_set_nested(tmp_path: Path):
    cfg_file = tmp_path / "settings.json"
    mgr = ConfigManager(config_path=cfg_file)

    mgr.set("metrics.sampling_interval_ms", 500)
    assert mgr.get("metrics.sampling_interval_ms") == 500

    # Reload from disk to verify persistence
    mgr2 = ConfigManager(config_path=cfg_file)
    assert mgr2.get("metrics.sampling_interval_ms") == 500


def test_corrupted_config_recovery(tmp_path: Path):
    cfg_file = tmp_path / "settings.json"
    # Write invalid json
    with open(cfg_file, "w") as f:
        f.write("{invalid json content!@@#")

    mgr = ConfigManager(config_path=cfg_file)
    # Should recover by falling back to default and creating backup
    assert mgr.get("theme") == "xbox_dark"
    bak_file = tmp_path / "settings.json.bak"
    assert bak_file.exists()
