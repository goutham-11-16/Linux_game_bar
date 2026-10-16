"""Unit tests for Embedded Web Browser Widget."""

import pytest
from PySide6.QtWidgets import QApplication
from linux_game_bar.config_manager import ConfigManager
from linux_game_bar.widgets.browser import BrowserWidget


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def test_browser_widget_initialization(qapp, tmp_path):
    cfg_file = tmp_path / "test_config.json"
    cfg = ConfigManager(config_path=cfg_file)

    widget = BrowserWidget(cfg)
    assert widget.widget_id == "browser"
    assert widget.widget_title == "BROWSER"
    assert widget.icon_name == "globe"
    assert widget.width() >= 320
    assert widget.height() >= 400


def test_browser_url_formatting():
    # Full URLs
    assert BrowserWidget.format_url_or_search("https://google.com") == "https://google.com"
    assert BrowserWidget.format_url_or_search("http://localhost:8080") == "http://localhost:8080"

    # Domain names
    assert BrowserWidget.format_url_or_search("reddit.com") == "https://reddit.com"
    assert BrowserWidget.format_url_or_search("en.wikipedia.org/wiki/Linux") == "https://en.wikipedia.org/wiki/Linux"

    # Search queries
    assert "duckduckgo.com/?q=elden+ring+map" in BrowserWidget.format_url_or_search("elden ring map")
    assert "duckduckgo.com/?q=cyberpunk+build" in BrowserWidget.format_url_or_search("cyberpunk build")
