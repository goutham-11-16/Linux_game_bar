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


def test_browser_clipboard_bridge(qapp, tmp_path):
    import urllib.parse
    from PySide6.QtGui import QClipboard
    from PySide6.QtWebEngineCore import QWebEngineSettings
    from linux_game_bar.widgets.browser import HAS_WEBENGINE, BrowserWebPage

    if not HAS_WEBENGINE:
        pytest.skip("QtWebEngine not available")

    cfg_file = tmp_path / "test_config.json"
    cfg = ConfigManager(config_path=cfg_file)
    widget = BrowserWidget(cfg)

    # 1. Verify profile script injection
    assert hasattr(widget, "_profile")
    scripts = widget._profile.scripts().find("gamebar_clipboard_bridge")
    assert len(scripts) >= 1

    # 2. Verify web settings
    assert widget.web_page.settings().testAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard) is True
    assert widget.web_page.settings().testAttribute(QWebEngineSettings.WebAttribute.JavascriptCanPaste) is True

    # 3. Verify console message clipboard handler
    test_code = "def solve():\n    return 42"
    encoded = urllib.parse.quote(test_code)
    widget.web_page.javaScriptConsoleMessage(0, f"__GAMEBAR_CLIPBOARD__:{encoded}", 1, "")

    cb = QApplication.clipboard()
    assert cb.text() == test_code


def test_browser_feature_permission(qapp, tmp_path):
    from PySide6.QtCore import QUrl
    from PySide6.QtWebEngineCore import QWebEnginePage
    from linux_game_bar.widgets.browser import HAS_WEBENGINE

    if not HAS_WEBENGINE:
        pytest.skip("QtWebEngine not available")

    cfg_file = tmp_path / "test_config.json"
    cfg = ConfigManager(config_path=cfg_file)
    widget = BrowserWidget(cfg)

    url = QUrl("https://chatgpt.com")
    # Emit permission request
    widget.web_page._on_feature_permission_requested(url, QWebEnginePage.Feature.ClipboardReadWrite)

