"""Tests for companion GNOME Shell extension files and metadata."""

import json
from pathlib import Path


def test_gnome_extension_metadata():
    ext_dir = Path("packaging/extension/linux-game-bar@ubuntu.com")
    metadata_file = ext_dir / "metadata.json"
    extension_js = ext_dir / "extension.js"

    assert metadata_file.exists()
    assert extension_js.exists()

    with open(metadata_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("uuid") == "linux-game-bar@ubuntu.com"
    assert "shell-version" in data
    # Must support GNOME 45 through 51
    assert "50" in data["shell-version"]
