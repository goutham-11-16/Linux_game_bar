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


def test_browser_home_navigation(qapp, tmp_path):
    from linux_game_bar.widgets.browser import HAS_WEBENGINE
    if not HAS_WEBENGINE:
        pytest.skip("QtWebEngine not available")

    cfg_file = tmp_path / "test_config.json"
    cfg = ConfigManager(config_path=cfg_file)
    cfg.set("browser.start_url", "https://example.com/home")
    widget = BrowserWidget(cfg)

    assert widget.web_view.url().toString() == "https://example.com/home"

    # Navigate elsewhere, then press home
    widget._navigate_to_url("https://example.com/other")
    assert widget.web_view.url().toString() == "https://example.com/other"
    widget.go_home()
    assert widget.web_view.url().toString() == "https://example.com/home"


def test_browser_audio_mute_toggle(qapp, tmp_path):
    from linux_game_bar.widgets.browser import HAS_WEBENGINE
    if not HAS_WEBENGINE:
        pytest.skip("QtWebEngine not available")

    cfg_file = tmp_path / "test_config.json"
    cfg = ConfigManager(config_path=cfg_file)
    widget = BrowserWidget(cfg)

    # Initial state should not be muted
    assert widget.is_audio_muted() is False

    # Toggle mute on
    widget.toggle_audio_mute()
    assert widget.is_audio_muted() is True
    assert "Unmute" in widget.btn_audio_mute.toolTip()

    # Toggle mute off
    widget.toggle_audio_mute()
    assert widget.is_audio_muted() is False
    assert "Mute" in widget.btn_audio_mute.toolTip()


def test_browser_zoom_controls(qapp, tmp_path):
    from linux_game_bar.widgets.browser import HAS_WEBENGINE
    if not HAS_WEBENGINE:
        pytest.skip("QtWebEngine not available")

    cfg_file = tmp_path / "test_config.json"
    cfg = ConfigManager(config_path=cfg_file)
    widget = BrowserWidget(cfg)

    assert widget.zoom_factor == 1.0
    assert widget.web_view.zoomFactor() == 1.0
    assert widget.lbl_zoom.text() == "100%"

    # Zoom in
    widget.zoom_in()
    assert round(widget.zoom_factor, 1) == 1.1
    assert widget.lbl_zoom.text() == "110%"

    # Zoom out
    widget.zoom_out()
    assert round(widget.zoom_factor, 1) == 1.0
    assert widget.lbl_zoom.text() == "100%"

    # Reset zoom
    widget.set_zoom(1.5)
    assert widget.zoom_factor == 1.5
    widget.reset_zoom()
    assert widget.zoom_factor == 1.0


def test_browser_in_page_search(qapp, tmp_path):
    from linux_game_bar.widgets.browser import HAS_WEBENGINE
    if not HAS_WEBENGINE:
        pytest.skip("QtWebEngine not available")

    cfg_file = tmp_path / "test_config.json"
    cfg = ConfigManager(config_path=cfg_file)
    widget = BrowserWidget(cfg)

    assert widget.search_frame.isHidden() is True

    # Show search
    widget.show_search()
    assert widget.search_frame.isHidden() is False

    # Toggle search hides
    widget.toggle_search()
    assert widget.search_frame.isHidden() is True

    # Show again, set query and perform forward search
    widget.show_search()
    assert widget.search_frame.isHidden() is False
    widget.search_input.setText("keyword")
    widget._perform_search(forward=True)
    widget._perform_search(forward=False)

    # Hide search
    widget.hide_search()
    assert widget.search_frame.isHidden() is True


def test_browser_bookmarks(qapp, tmp_path):
    from linux_game_bar.widgets.browser import HAS_WEBENGINE, DEFAULT_BOOKMARKS
    cfg_file = tmp_path / "test_config.json"
    cfg = ConfigManager(config_path=cfg_file)
    widget = BrowserWidget(cfg)

    # Initial default bookmarks
    bookmarks = widget.get_bookmarks()
    assert len(bookmarks) == len(DEFAULT_BOOKMARKS)
    assert any(b["name"] == "ChatGPT" for b in bookmarks)

    # Bookmark current page
    widget.url_bar.setText("https://customgameguide.com")
    assert widget.is_bookmarked("https://customgameguide.com") is False

    widget.toggle_bookmark_current_page()
    assert widget.is_bookmarked("https://customgameguide.com") is True

    # Check persistence in config
    saved_bms = cfg.get("browser.bookmarks")
    assert any(b["url"] == "https://customgameguide.com" for b in saved_bms)

    # Toggle again should remove it
    widget.toggle_bookmark_current_page()
    assert widget.is_bookmarked("https://customgameguide.com") is False


