"""
Embedded Web Browser Widget for Linux Game Bar.
Provides a lightweight, phone/small-tab aspect ratio Chromium browser (via QtWebEngine)
integrated directly into the overlay without background daemon processes.
Features:
- Companion Quick Bookmarks Bar (ChatGPT, YouTube, Discord, Reddit, Wikis + custom bookmarks)
- In-Page Search (Ctrl+F)
- Audio Mute/Unmute Toggle (Ctrl+M)
- Zoom Controls (Ctrl +, Ctrl -, Ctrl 0)
- Home Button
- Universal Clipboard Bridge (ChatGPT code copy & Web Clipboard API)
- External Browser handoff (Brave, Chrome, Firefox)
"""

import os
import re
import shutil
import logging
import urllib.parse
from pathlib import Path
from typing import Optional, List, Dict

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QClipboard, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QLabel,
    QFrame,
    QScrollArea,
    QMenu,
)

from linux_game_bar.ui.widget_base import WidgetBase
from linux_game_bar.ui.theme import Theme
from linux_game_bar.ui import icons
from linux_game_bar.config_manager import ConfigManager

logger = logging.getLogger("linux_game_bar.browser")

# Check QtWebEngine availability
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import (
        QWebEngineProfile,
        QWebEnginePage,
        QWebEngineScript,
        QWebEngineSettings,
    )
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False


DEFAULT_START_URL = "https://duckduckgo.com"
DEFAULT_BOOKMARKS: List[Dict[str, str]] = [
    {"name": "ChatGPT", "url": "https://chatgpt.com"},
    {"name": "YouTube", "url": "https://youtube.com"},
    {"name": "Discord", "url": "https://discord.com/app"},
    {"name": "Reddit", "url": "https://reddit.com"},
    {"name": "Fandom", "url": "https://www.fandom.com"},
]


class SearchLineEdit(QLineEdit):
    """Custom QLineEdit that captures Escape and Shift+Enter for page search."""

    def __init__(self, on_escape, on_shift_enter, parent=None):
        super().__init__(parent)
        self._on_escape = on_escape
        self._on_shift_enter = on_shift_enter

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._on_escape()
            event.accept()
            return
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter) and (event.modifiers() & Qt.ShiftModifier):
            self._on_shift_enter()
            event.accept()
            return
        super().keyPressEvent(event)


if HAS_WEBENGINE:
    class BrowserWebPage(QWebEnginePage):
        """Custom QWebEnginePage with enhanced clipboard bridge and security permissions."""

        def __init__(self, profile: QWebEngineProfile, parent=None):
            super().__init__(profile, parent)
            if hasattr(self, "permissionRequested"):
                self.permissionRequested.connect(self._on_permission_requested)
            if hasattr(self, "featurePermissionRequested"):
                self.featurePermissionRequested.connect(self._on_feature_permission_requested)

        def _on_permission_requested(self, permission) -> None:
            logger.info(f"Browser permission granted: {permission.permissionType()} for {permission.origin().toString()}")
            try:
                permission.grant()
            except Exception as e:
                logger.warning(f"Error granting browser permission: {e}")

        def _on_feature_permission_requested(self, security_origin: QUrl, feature: QWebEnginePage.Feature) -> None:
            logger.info(f"Browser feature permission granted for {security_origin.toString()}: {feature}")
            try:
                self.setFeaturePermission(
                    security_origin,
                    feature,
                    QWebEnginePage.PermissionPolicy.PermissionGrantedByUser,
                )
            except Exception as e:
                logger.warning(f"Error granting feature permission: {e}")

        def javaScriptConsoleMessage(self, level, message, line_number, source_id):
            if message.startswith("__GAMEBAR_CLIPBOARD__:"):
                payload = message.split(":", 1)[1]
                try:
                    text = urllib.parse.unquote(payload)
                    clipboard = QApplication.clipboard()
                    if clipboard:
                        clipboard.setText(text, QClipboard.Mode.Clipboard)
                        clipboard.setText(text, QClipboard.Mode.Selection)
                    logger.info(f"Browser clipboard bridge captured {len(text)} chars to system clipboard.")
                except Exception as e:
                    logger.warning(f"Failed to decode browser clipboard payload: {e}")
                return
            super().javaScriptConsoleMessage(level, message, line_number, source_id)
else:
    class BrowserWebPage:
        pass


class BrowserWidget(WidgetBase):
    """
    Lightweight, compact browser widget pre-proportioned to a phone/small-tab size.
    Allows searching game guides, maps, discord, wikis, or watching videos while gaming.
    """

    DEFAULT_WIDTH = 400
    DEFAULT_HEIGHT = 580

    def __init__(self, config_manager: ConfigManager, parent: Optional[QWidget] = None):
        super().__init__(
            widget_id="browser",
            title="BROWSER",
            icon_str="globe",
            parent=parent,
        )
        self.config_manager = config_manager
        self.setMinimumSize(320, 400)
        self.resize(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)

        self.web_view: Optional[QWebEngineView] = None
        self.web_page: Optional[BrowserWebPage] = None
        self.zoom_factor: float = float(self.config_manager.get("browser.zoom_factor", 1.0))

        self._init_browser_ui()
        self._init_shortcuts()

    def _init_browser_ui(self) -> None:
        self.content_layout.setContentsMargins(6, 6, 6, 6)
        self.content_layout.setSpacing(4)

        # -------------------------------------------------------------
        # 1. Navigation / Address Bar (Row 1)
        # -------------------------------------------------------------
        nav_frame = QFrame()
        nav_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.BG_CARD};
                border-radius: 6px;
                padding: 2px 4px;
            }}
        """)
        nav_layout = QHBoxLayout(nav_frame)
        nav_layout.setContentsMargins(4, 2, 4, 2)
        nav_layout.setSpacing(3)

        btn_style = (
            "QPushButton { background: transparent; border: none; border-radius: 4px; } "
            "QPushButton:hover { background: rgba(255,255,255,0.12); }"
        )

        # Back Button
        self.btn_back = QPushButton()
        self.btn_back.setFixedSize(26, 26)
        self.btn_back.setIcon(icons.get_icon("arrow_left", color="#CCCCCC", size=13))
        self.btn_back.setToolTip("Back")
        self.btn_back.setCursor(Qt.PointingHandCursor)
        self.btn_back.setStyleSheet(btn_style)
        nav_layout.addWidget(self.btn_back)

        # Forward Button
        self.btn_forward = QPushButton()
        self.btn_forward.setFixedSize(26, 26)
        self.btn_forward.setIcon(icons.get_icon("arrow_right", color="#CCCCCC", size=13))
        self.btn_forward.setToolTip("Forward")
        self.btn_forward.setCursor(Qt.PointingHandCursor)
        self.btn_forward.setStyleSheet(btn_style)
        nav_layout.addWidget(self.btn_forward)

        # Reload / Refresh Button
        self.btn_refresh = QPushButton()
        self.btn_refresh.setFixedSize(26, 26)
        self.btn_refresh.setIcon(icons.get_icon("refresh", color="#CCCCCC", size=13))
        self.btn_refresh.setToolTip("Reload (Ctrl+R / F5)")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setStyleSheet(btn_style)
        self.btn_refresh.clicked.connect(self.reload_page)
        nav_layout.addWidget(self.btn_refresh)

        # Home Button
        self.btn_home = QPushButton()
        self.btn_home.setFixedSize(26, 26)
        self.btn_home.setIcon(icons.get_icon("home", color="#CCCCCC", size=13))
        self.btn_home.setToolTip("Home")
        self.btn_home.setCursor(Qt.PointingHandCursor)
        self.btn_home.setStyleSheet(btn_style)
        self.btn_home.clicked.connect(self.go_home)
        nav_layout.addWidget(self.btn_home)

        # URL / Search Bar
        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Search web or enter address...")
        self.url_bar.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Theme.BG_INPUT};
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 3px 6px;
                font-size: 11px;
            }}
            QLineEdit:focus {{
                border-color: {Theme.ACCENT_GREEN};
            }}
        """)
        self.url_bar.returnPressed.connect(self._navigate_url)
        nav_layout.addWidget(self.url_bar, 1)

        # Bookmark Button (Star)
        self.btn_bookmark = QPushButton()
        self.btn_bookmark.setFixedSize(26, 26)
        self.btn_bookmark.setIcon(icons.get_icon("star_outline", color="#CCCCCC", size=13))
        self.btn_bookmark.setToolTip("Bookmark current page (Ctrl+D)")
        self.btn_bookmark.setCursor(Qt.PointingHandCursor)
        self.btn_bookmark.setStyleSheet(btn_style)
        self.btn_bookmark.clicked.connect(self.toggle_bookmark_current_page)
        nav_layout.addWidget(self.btn_bookmark)

        # Audio Mute / Unmute Button
        self.btn_audio_mute = QPushButton()
        self.btn_audio_mute.setFixedSize(26, 26)
        self.btn_audio_mute.setIcon(icons.get_icon("speaker", color="#CCCCCC", size=13))
        self.btn_audio_mute.setToolTip("Mute browser audio (Ctrl+M)")
        self.btn_audio_mute.setCursor(Qt.PointingHandCursor)
        self.btn_audio_mute.setStyleSheet(btn_style)
        self.btn_audio_mute.clicked.connect(self.toggle_audio_mute)
        nav_layout.addWidget(self.btn_audio_mute)

        # Pop-out to Desktop Browser Button (Brave / Chrome / Firefox)
        self.btn_popout = QPushButton()
        self.btn_popout.setFixedSize(26, 26)
        self.btn_popout.setIcon(icons.get_icon("external_link", color="#CCCCCC", size=13))
        self.btn_popout.setToolTip("Open in external desktop browser (Brave / Chrome / Firefox)")
        self.btn_popout.setCursor(Qt.PointingHandCursor)
        self.btn_popout.setStyleSheet(btn_style)
        self.btn_popout.clicked.connect(self._open_in_external_browser)
        nav_layout.addWidget(self.btn_popout)

        # Clear Browsing Data Button (Trash icon to wipe cookies, logins, and cache if desired)
        self.btn_clear_data = QPushButton()
        self.btn_clear_data.setFixedSize(26, 26)
        self.btn_clear_data.setIcon(icons.get_icon("trash", color="#CCCCCC", size=13))
        self.btn_clear_data.setToolTip("Clear Browsing Data (Cookies, Logins & Cache)")
        self.btn_clear_data.setCursor(Qt.PointingHandCursor)
        self.btn_clear_data.setStyleSheet("QPushButton { background: transparent; border: none; border-radius: 4px; } QPushButton:hover { background: rgba(239,83,80,0.2); }")
        self.btn_clear_data.clicked.connect(self.clear_browsing_data)
        nav_layout.addWidget(self.btn_clear_data)

        self.content_layout.addWidget(nav_frame)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(2)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                background: transparent;
            }}
            QProgressBar::chunk {{
                background-color: {Theme.ACCENT_GREEN};
            }}
        """)
        self.progress_bar.hide()
        self.content_layout.addWidget(self.progress_bar)

        # -------------------------------------------------------------
        # 2. Bookmarks & Quick Actions Toolbar (Row 2)
        # -------------------------------------------------------------
        bar_frame = QFrame()
        bar_frame.setStyleSheet("background: transparent; border: none;")
        bar_layout = QHBoxLayout(bar_frame)
        bar_layout.setContentsMargins(2, 0, 2, 0)
        bar_layout.setSpacing(6)

        # Bookmarks scroll container
        self.bookmarks_scroll = QScrollArea()
        self.bookmarks_scroll.setFixedHeight(26)
        self.bookmarks_scroll.setWidgetResizable(True)
        self.bookmarks_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.bookmarks_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.bookmarks_scroll.setFrameShape(QFrame.NoFrame)
        self.bookmarks_scroll.setStyleSheet("background: transparent; border: none;")

        self.bookmarks_container = QWidget()
        self.bookmarks_container.setStyleSheet("background: transparent;")
        self.bookmarks_layout = QHBoxLayout(self.bookmarks_container)
        self.bookmarks_layout.setContentsMargins(0, 0, 0, 0)
        self.bookmarks_layout.setSpacing(5)
        self.bookmarks_scroll.setWidget(self.bookmarks_container)
        bar_layout.addWidget(self.bookmarks_scroll, 1)

        # Zoom Controls Pill
        zoom_frame = QFrame()
        zoom_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.06);
                border-radius: 11px;
                padding: 1px 3px;
            }
        """)
        zoom_layout = QHBoxLayout(zoom_frame)
        zoom_layout.setContentsMargins(2, 0, 2, 0)
        zoom_layout.setSpacing(1)

        self.btn_zoom_out = QPushButton("-")
        self.btn_zoom_out.setFixedSize(16, 20)
        self.btn_zoom_out.setToolTip("Zoom Out (Ctrl -)")
        self.btn_zoom_out.setCursor(Qt.PointingHandCursor)
        self.btn_zoom_out.setStyleSheet("QPushButton { background: transparent; color: #CCCCCC; border: none; font-size: 13px; font-weight: bold; } QPushButton:hover { color: #FFFFFF; }")
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        zoom_layout.addWidget(self.btn_zoom_out)

        self.lbl_zoom = QPushButton(f"{int(round(self.zoom_factor * 100))}%")
        self.lbl_zoom.setFixedHeight(20)
        self.lbl_zoom.setCursor(Qt.PointingHandCursor)
        self.lbl_zoom.setToolTip(f"Zoom: {int(round(self.zoom_factor * 100))}% (Click to reset to 100%)")
        self.lbl_zoom.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #CCCCCC;
                border: none;
                font-size: 10px;
                font-weight: 500;
                padding: 0 2px;
            }
            QPushButton:hover {
                color: #107C41;
            }
        """)
        self.lbl_zoom.clicked.connect(self.reset_zoom)
        zoom_layout.addWidget(self.lbl_zoom)

        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setFixedSize(16, 20)
        self.btn_zoom_in.setToolTip("Zoom In (Ctrl +)")
        self.btn_zoom_in.setCursor(Qt.PointingHandCursor)
        self.btn_zoom_in.setStyleSheet("QPushButton { background: transparent; color: #CCCCCC; border: none; font-size: 13px; font-weight: bold; } QPushButton:hover { color: #FFFFFF; }")
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        zoom_layout.addWidget(self.btn_zoom_in)

        bar_layout.addWidget(zoom_frame)

        # Find in Page Toggle Button
        self.btn_find_toggle = QPushButton()
        self.btn_find_toggle.setFixedSize(22, 22)
        self.btn_find_toggle.setIcon(icons.get_icon("search", color="#CCCCCC", size=13))
        self.btn_find_toggle.setToolTip("Find in page (Ctrl+F)")
        self.btn_find_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_find_toggle.setStyleSheet(btn_style)
        self.btn_find_toggle.clicked.connect(self.toggle_search)
        bar_layout.addWidget(self.btn_find_toggle)

        self.content_layout.addWidget(bar_frame)

        # -------------------------------------------------------------
        # 3. In-Page Search Frame (Hidden by default)
        # -------------------------------------------------------------
        self.search_frame = QFrame()
        self.search_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.BG_CARD};
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 6px;
                padding: 2px 4px;
            }}
        """)
        search_layout = QHBoxLayout(self.search_frame)
        search_layout.setContentsMargins(4, 2, 4, 2)
        search_layout.setSpacing(4)

        self.search_input = SearchLineEdit(
            on_escape=self.hide_search,
            on_shift_enter=lambda: self._perform_search(forward=False),
        )
        self.search_input.setPlaceholderText("Find in page...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                color: #FFFFFF;
                border: none;
                font-size: 11px;
                padding: 2px;
            }}
        """)
        self.search_input.textChanged.connect(lambda: self._perform_search(forward=True))
        self.search_input.returnPressed.connect(lambda: self._perform_search(forward=True))
        search_layout.addWidget(self.search_input, 1)

        # Find Previous Button
        self.btn_find_prev = QPushButton()
        self.btn_find_prev.setFixedSize(22, 22)
        self.btn_find_prev.setIcon(icons.get_icon("chevron_up", color="#CCCCCC", size=12))
        self.btn_find_prev.setToolTip("Previous match (Shift+Enter)")
        self.btn_find_prev.setCursor(Qt.PointingHandCursor)
        self.btn_find_prev.setStyleSheet(btn_style)
        self.btn_find_prev.clicked.connect(lambda: self._perform_search(forward=False))
        search_layout.addWidget(self.btn_find_prev)

        # Find Next Button
        self.btn_find_next = QPushButton()
        self.btn_find_next.setFixedSize(22, 22)
        self.btn_find_next.setIcon(icons.get_icon("chevron_down", color="#CCCCCC", size=12))
        self.btn_find_next.setToolTip("Next match (Enter)")
        self.btn_find_next.setCursor(Qt.PointingHandCursor)
        self.btn_find_next.setStyleSheet(btn_style)
        self.btn_find_next.clicked.connect(lambda: self._perform_search(forward=True))
        search_layout.addWidget(self.btn_find_next)

        # Close Search Button
        self.btn_close_search = QPushButton()
        self.btn_close_search.setFixedSize(22, 22)
        self.btn_close_search.setIcon(icons.get_icon("close", color="#CCCCCC", size=12))
        self.btn_close_search.setToolTip("Close search (Esc)")
        self.btn_close_search.setCursor(Qt.PointingHandCursor)
        self.btn_close_search.setStyleSheet(btn_style)
        self.btn_close_search.clicked.connect(self.hide_search)
        search_layout.addWidget(self.btn_close_search)

        self.search_frame.hide()
        self.content_layout.addWidget(self.search_frame)

        # Build initial bookmarks bar
        self._rebuild_bookmarks_bar()

        # -------------------------------------------------------------
        # 4. Embedded Browser View or Fallback
        # -------------------------------------------------------------
        if HAS_WEBENGINE:
            self.web_view = QWebEngineView()
            self.web_view.setStyleSheet("background: #1e1e22; border-radius: 4px;")

            # Configure Persistent Profile (persists logins, Google accounts, cookies, cache)
            profile_dir = Path.home() / ".local" / "share" / "linux-game-bar" / "browser_profile"
            profile_dir.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(profile_dir, 0o700)
            except Exception:
                pass

            self._profile = QWebEngineProfile("linux_game_bar_browser", self)
            self._profile.setPersistentStoragePath(str(profile_dir / "storage"))
            self._profile.setCachePath(str(profile_dir / "cache"))
            self._profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)

            # Web Settings for Profile
            prof_settings = self._profile.settings()
            prof_settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
            prof_settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanPaste, True)
            prof_settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
            prof_settings.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)
            prof_settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
            prof_settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)

            # Install universal clipboard bridge script into profile
            self._install_clipboard_bridge(self._profile)

            self.web_page = BrowserWebPage(self._profile, self.web_view)
            self.web_view.setPage(self.web_page)

            page_settings = self.web_page.settings()
            page_settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
            page_settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanPaste, True)
            page_settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
            page_settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)

            # Apply initial zoom factor
            self.web_view.setZoomFactor(self.zoom_factor)

            # Wire navigation actions
            self.btn_back.clicked.connect(self.web_view.back)
            self.btn_forward.clicked.connect(self.web_view.forward)

            # Signals
            self.web_view.urlChanged.connect(self._on_url_changed)
            self.web_view.loadProgress.connect(self._on_load_progress)
            self.web_view.loadFinished.connect(self._on_load_finished)
            self.web_page.audioMutedChanged.connect(self._on_audio_muted_changed)

            # Initial Homepage
            start_url = self.config_manager.get("browser.start_url", DEFAULT_START_URL)
            self.web_view.setUrl(QUrl(start_url))
            self.content_layout.addWidget(self.web_view, 1)
        else:
            fallback = QWidget()
            f_layout = QVBoxLayout(fallback)
            lbl_err = QLabel("QtWebEngine is not installed in the environment.\nClick below to open links in Brave, Chrome, or Firefox.")
            lbl_err.setAlignment(Qt.AlignCenter)
            lbl_err.setStyleSheet("color: #A0A0A5; font-size: 12px;")
            f_layout.addWidget(lbl_err)
            self.content_layout.addWidget(fallback, 1)

    def _init_shortcuts(self) -> None:
        """Register handy keyboard shortcuts scoped to the browser widget."""
        QShortcut(QKeySequence("Ctrl+F"), self, self.show_search)
        QShortcut(QKeySequence("Ctrl+="), self, self.zoom_in)
        QShortcut(QKeySequence("Ctrl++"), self, self.zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, self.zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self, self.reset_zoom)
        QShortcut(QKeySequence("Ctrl+M"), self, self.toggle_audio_mute)
        QShortcut(QKeySequence("Ctrl+R"), self, self.reload_page)
        QShortcut(QKeySequence("F5"), self, self.reload_page)
        QShortcut(QKeySequence("Ctrl+D"), self, self.toggle_bookmark_current_page)

    # -------------------------------------------------------------
    # Navigation & Core Actions
    # -------------------------------------------------------------
    def go_home(self) -> None:
        """Navigate to the configured or default homepage."""
        start_url = self.config_manager.get("browser.start_url", DEFAULT_START_URL)
        if self.web_view:
            self.web_view.setUrl(QUrl(start_url))

    def reload_page(self) -> None:
        """Reload the current webpage."""
        if self.web_view:
            self.web_view.reload()

    def toggle_audio_mute(self) -> None:
        """Toggle audio playback mute state."""
        if hasattr(self, "web_page") and self.web_page:
            try:
                current_muted = self.web_page.isAudioMuted()
                self.web_page.setAudioMuted(not current_muted)
            except Exception as e:
                logger.warning(f"Failed to toggle audio mute: {e}")

    def is_audio_muted(self) -> bool:
        """Return True if audio playback is currently muted."""
        if hasattr(self, "web_page") and self.web_page:
            return self.web_page.isAudioMuted()
        return False

    def _on_audio_muted_changed(self, muted: bool) -> None:
        """Update audio mute icon when mute state changes."""
        if muted:
            self.btn_audio_mute.setIcon(icons.get_icon("speaker_mute", color="#EF5350", size=13))
            self.btn_audio_mute.setToolTip("Unmute browser audio (Ctrl+M)")
        else:
            self.btn_audio_mute.setIcon(icons.get_icon("speaker", color="#CCCCCC", size=13))
            self.btn_audio_mute.setToolTip("Mute browser audio (Ctrl+M)")

    # -------------------------------------------------------------
    # Zoom Controls
    # -------------------------------------------------------------
    def zoom_in(self) -> None:
        """Increase zoom factor by 10% (up to 300%)."""
        self.set_zoom(min(3.0, self.zoom_factor + 0.1))

    def zoom_out(self) -> None:
        """Decrease zoom factor by 10% (down to 50%)."""
        self.set_zoom(max(0.5, self.zoom_factor - 0.1))

    def reset_zoom(self) -> None:
        """Reset zoom factor to 100%."""
        self.set_zoom(1.0)

    def set_zoom(self, factor: float) -> None:
        """Apply zoom factor and persist in config."""
        self.zoom_factor = round(factor, 2)
        if self.web_view:
            self.web_view.setZoomFactor(self.zoom_factor)
        zoom_pct = int(round(self.zoom_factor * 100))
        self.lbl_zoom.setText(f"{zoom_pct}%")
        self.lbl_zoom.setToolTip(f"Zoom: {zoom_pct}% (Click to reset to 100%)")
        self.config_manager.set("browser.zoom_factor", self.zoom_factor)

    # -------------------------------------------------------------
    # In-Page Search
    # -------------------------------------------------------------
    def show_search(self) -> None:
        """Open in-page search bar and focus input."""
        self.search_frame.show()
        self.search_input.selectAll()
        self.search_input.setFocus()
        if self.search_input.text().strip():
            self._perform_search(forward=True)

    def hide_search(self) -> None:
        """Close in-page search bar and clear highlighted occurrences."""
        self.search_frame.hide()
        if self.web_view:
            self.web_view.findText("")
            self.web_view.setFocus()

    def toggle_search(self) -> None:
        """Toggle in-page search bar visibility."""
        if not self.search_frame.isHidden():
            self.hide_search()
        else:
            self.show_search()

    def _perform_search(self, forward: bool = True) -> None:
        """Execute text search on the active page."""
        query = self.search_input.text().strip()
        if not query:
            if self.web_view:
                self.web_view.findText("")
            return
        if self.web_view:
            if forward:
                self.web_view.findText(query)
            else:
                if hasattr(QWebEnginePage, "FindFlag") and hasattr(QWebEnginePage.FindFlag, "FindBackward"):
                    self.web_view.findText(query, QWebEnginePage.FindFlag.FindBackward)
                else:
                    self.web_view.findText(query)

    # -------------------------------------------------------------
    # Bookmarks
    # -------------------------------------------------------------
    def get_bookmarks(self) -> List[Dict[str, str]]:
        """Retrieve list of saved bookmarks from config."""
        bms = self.config_manager.get("browser.bookmarks")
        if not isinstance(bms, list):
            return list(DEFAULT_BOOKMARKS)
        return bms

    def is_bookmarked(self, url: str) -> bool:
        """Check if given URL is bookmarked."""
        if not url:
            return False
        clean = url.rstrip("/")
        for b in self.get_bookmarks():
            if b.get("url", "").rstrip("/") == clean:
                return True
        return False

    def _update_bookmark_icon(self) -> None:
        """Update bookmark star icon according to whether current URL is bookmarked."""
        current_url = self.url_bar.text().strip()
        if self.is_bookmarked(current_url):
            self.btn_bookmark.setIcon(icons.get_icon("star", color=Theme.ACCENT_GREEN, size=13))
            self.btn_bookmark.setToolTip("Remove bookmark (Ctrl+D)")
        else:
            self.btn_bookmark.setIcon(icons.get_icon("star_outline", color="#CCCCCC", size=13))
            self.btn_bookmark.setToolTip("Bookmark current page (Ctrl+D)")

    def toggle_bookmark_current_page(self) -> None:
        """Add or remove current page from bookmarks."""
        current_url = self.url_bar.text().strip()
        if not current_url or current_url.startswith("about:"):
            return
        bookmarks = list(self.get_bookmarks())
        clean_url = current_url.rstrip("/")
        existing = [b for b in bookmarks if b.get("url", "").rstrip("/") == clean_url]
        if existing:
            bookmarks = [b for b in bookmarks if b.get("url", "").rstrip("/") != clean_url]
        else:
            title = "Page"
            if self.web_view:
                title = self.web_view.title().strip() or "Page"
            if len(title) > 20:
                title = title[:18] + "…"
            bookmarks.append({"name": title, "url": current_url})

        self.config_manager.set("browser.bookmarks", bookmarks)
        self._rebuild_bookmarks_bar()
        self._update_bookmark_icon()

    def _rebuild_bookmarks_bar(self) -> None:
        """Re-render bookmark pill buttons."""
        while self.bookmarks_layout.count():
            item = self.bookmarks_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        bookmarks = self.get_bookmarks()
        for bm in bookmarks:
            name = bm.get("name", "Link")
            url = bm.get("url", "")
            btn = QPushButton(name)
            btn.setFixedHeight(22)
            btn.setToolTip(f"{name}\n{url}\n(Right-click for options)")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.08);
                    color: #D8D8DC;
                    border: 1px solid rgba(255, 255, 255, 0.05);
                    border-radius: 11px;
                    padding: 2px 8px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.16);
                    color: #FFFFFF;
                    border-color: rgba(255, 255, 255, 0.15);
                }
                QPushButton:pressed {
                    background-color: rgba(16, 124, 65, 0.35);
                }
            """)
            btn.clicked.connect(lambda checked=False, target=url: self._navigate_to_url(target))
            btn.setContextMenuPolicy(Qt.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda pos, b=bm, w=btn: self._show_bookmark_menu(w, b)
            )
            self.bookmarks_layout.addWidget(btn)

        self.bookmarks_layout.addStretch()

    def _show_bookmark_menu(self, widget: QWidget, bookmark: Dict[str, str]) -> None:
        """Display context menu for bookmark pill."""
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {Theme.BG_CARD};
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 4px 12px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: rgba(255, 255, 255, 0.12);
            }}
        """)
        act_open = menu.addAction("Open")
        act_copy = menu.addAction("Copy URL")
        act_delete = menu.addAction("Delete Bookmark")

        selected = menu.exec(widget.mapToGlobal(widget.rect().bottomLeft()))
        if selected == act_open:
            self._navigate_to_url(bookmark.get("url", ""))
        elif selected == act_copy:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(bookmark.get("url", ""))
        elif selected == act_delete:
            bookmarks = [b for b in self.get_bookmarks() if b.get("url") != bookmark.get("url")]
            self.config_manager.set("browser.bookmarks", bookmarks)
            self._rebuild_bookmarks_bar()
            self._update_bookmark_icon()

    def _navigate_to_url(self, target_url: str) -> None:
        """Navigate to a specified URL string."""
        if not target_url:
            return
        self.url_bar.setText(target_url)
        if self.web_view:
            self.web_view.setUrl(QUrl(target_url))

    # -------------------------------------------------------------
    # Data & External Browser Handlers
    # -------------------------------------------------------------
    def clear_browsing_data(self) -> None:
        """Clears all session cookies, cache, and history to protect user privacy."""
        if hasattr(self, "_profile") and self._profile:
            self._profile.clearAllVisitedLinks()
            self._profile.clearHttpCache()
            if self._profile.cookieStore():
                self._profile.cookieStore().deleteAllCookies()
            if self.web_view:
                start_url = self.config_manager.get("browser.start_url", DEFAULT_START_URL)
                self.web_view.setUrl(QUrl(start_url))
            logger.info("Cleared browser cookies, cache, and visited links.")

    def _navigate_url(self) -> None:
        raw_text = self.url_bar.text().strip()
        if not raw_text:
            return

        target_url = self.format_url_or_search(raw_text)
        if self.web_view:
            self.web_view.setUrl(QUrl(target_url))

    @staticmethod
    def format_url_or_search(text: str) -> str:
        """Determines whether input is a URL or search query and formats appropriately."""
        text = text.strip()
        # Has protocol scheme
        if text.startswith("http://") or text.startswith("https://"):
            return text

        # Looks like a domain (e.g. google.com, youtube.com, localhost:3000)
        domain_pattern = r"^([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(/.*)?$|^localhost(:\d+)?(/.*)?$"
        if re.match(domain_pattern, text) and " " not in text:
            return f"https://{text}"

        # Otherwise treat as search query
        from urllib.parse import quote_plus
        return f"https://duckduckgo.com/?q={quote_plus(text)}"

    def _on_url_changed(self, qurl: QUrl) -> None:
        url_str = qurl.toString()
        if not self.url_bar.hasFocus():
            self.url_bar.setText(url_str)
        if self.web_view:
            self.btn_back.setEnabled(self.web_view.history().canGoBack())
            self.btn_forward.setEnabled(self.web_view.history().canGoForward())
        self._update_bookmark_icon()

    def _on_load_progress(self, progress: int) -> None:
        if progress < 100:
            self.progress_bar.show()
            self.progress_bar.setValue(progress)
        else:
            self.progress_bar.hide()

    def _on_load_finished(self, success: bool) -> None:
        self.progress_bar.hide()

    def _open_in_external_browser(self) -> None:
        """Open the current address in user's external browser (Brave, Chrome, Firefox)."""
        current_url = self.url_bar.text().strip() or DEFAULT_START_URL
        target_url = self.format_url_or_search(current_url)

        # Priority order of browsers
        candidates = ["brave-browser", "brave-browser-nightly", "google-chrome", "firefox", "chromium"]
        browser_bin = None
        for b in candidates:
            path = shutil.which(b)
            if path:
                browser_bin = path
                break

        if not browser_bin and os.path.isfile(os.path.expanduser("~/.local/bin/google-chrome")):
            browser_bin = os.path.expanduser("~/.local/bin/google-chrome")

        if browser_bin:
            from PySide6.QtCore import QProcess
            logger.info(f"Opening external browser: {browser_bin} {target_url}")
            QProcess.startDetached(browser_bin, [f"--app={target_url}"] if "chrome" in browser_bin or "brave" in browser_bin else [target_url])
        else:
            import webbrowser
            webbrowser.open(target_url)

    @staticmethod
    def _install_clipboard_bridge(profile: QWebEngineProfile) -> None:
        """Inject universal clipboard bridge into profile to handle modern web clipboard API (e.g. ChatGPT, Claude, GitHub)."""
        if not HAS_WEBENGINE:
            return
        if profile.scripts().find("gamebar_clipboard_bridge"):
            return

        js_bridge = """
(function() {
    function sendToHost(text) {
        if (typeof text === "string" && text.length > 0) {
            console.log("__GAMEBAR_CLIPBOARD__:" + encodeURIComponent(text));
        }
    }

    function hookClipboard(target) {
        if (!target) return;
        try {
            Object.defineProperty(target, "writeText", {
                value: function(text) {
                    sendToHost(text);
                    return Promise.resolve();
                },
                writable: true,
                configurable: true
            });

            Object.defineProperty(target, "write", {
                value: async function(items) {
                    try {
                        for (const item of items) {
                            if (item.types && item.types.includes("text/plain")) {
                                const blob = await item.getType("text/plain");
                                const text = await blob.text();
                                sendToHost(text);
                            }
                        }
                    } catch (e) {}
                    return Promise.resolve();
                },
                writable: true,
                configurable: true
            });
        } catch (e) {}
    }

    if (navigator.clipboard) {
        hookClipboard(navigator.clipboard);
    } else {
        const dummyClipboard = {};
        hookClipboard(dummyClipboard);
        try {
            Object.defineProperty(navigator, "clipboard", {
                value: dummyClipboard,
                writable: true,
                configurable: true
            });
        } catch (e) {}
    }

    if (navigator.permissions && navigator.permissions.query) {
        const origQuery = navigator.permissions.query.bind(navigator.permissions);
        navigator.permissions.query = function(param) {
            if (param && (param.name === "clipboard-write" || param.name === "clipboard-read")) {
                return Promise.resolve({ state: "granted", onchange: null });
            }
            return origQuery(param);
        };
    }

    if (typeof DataTransfer !== "undefined" && DataTransfer.prototype) {
        const origSetData = DataTransfer.prototype.setData;
        DataTransfer.prototype.setData = function(format, data) {
            if (format === "text/plain" || format === "text") {
                sendToHost(data);
            }
            return origSetData.apply(this, arguments);
        };
    }

    document.addEventListener("copy", function(e) {
        const sel = window.getSelection();
        if (sel && sel.toString()) {
            sendToHost(sel.toString());
        }
    }, true);
})();
"""
        script = QWebEngineScript()
        script.setName("gamebar_clipboard_bridge")
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        script.setRunsOnSubFrames(True)
        script.setSourceCode(js_bridge)
        profile.scripts().insert(script)
