"""
Embedded Web Browser Widget for Linux Game Bar.
Provides a lightweight, phone/small-tab aspect ratio Chromium browser (via QtWebEngine)
integrated directly into the overlay without background daemon processes.
"""

import os
import re
import shutil
import logging
import urllib.parse
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QClipboard
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
        self._init_browser_ui()

    def _init_browser_ui(self) -> None:
        self.content_layout.setContentsMargins(6, 6, 6, 6)
        self.content_layout.setSpacing(6)

        # 1. Navigation / Address Bar
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
        nav_layout.setSpacing(4)

        # Back Button
        self.btn_back = QPushButton()
        self.btn_back.setFixedSize(28, 28)
        self.btn_back.setIcon(icons.get_icon("arrow_left", color="#CCCCCC", size=14))
        self.btn_back.setToolTip("Back")
        self.btn_back.setCursor(Qt.PointingHandCursor)
        self.btn_back.setStyleSheet("QPushButton { background: transparent; border: none; border-radius: 4px; } QPushButton:hover { background: rgba(255,255,255,0.12); }")
        nav_layout.addWidget(self.btn_back)

        # Forward Button
        self.btn_forward = QPushButton()
        self.btn_forward.setFixedSize(28, 28)
        self.btn_forward.setIcon(icons.get_icon("arrow_right", color="#CCCCCC", size=14))
        self.btn_forward.setToolTip("Forward")
        self.btn_forward.setCursor(Qt.PointingHandCursor)
        self.btn_forward.setStyleSheet("QPushButton { background: transparent; border: none; border-radius: 4px; } QPushButton:hover { background: rgba(255,255,255,0.12); }")
        nav_layout.addWidget(self.btn_forward)

        # Reload / Refresh Button
        self.btn_refresh = QPushButton()
        self.btn_refresh.setFixedSize(28, 28)
        self.btn_refresh.setIcon(icons.get_icon("refresh", color="#CCCCCC", size=14))
        self.btn_refresh.setToolTip("Reload")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setStyleSheet("QPushButton { background: transparent; border: none; border-radius: 4px; } QPushButton:hover { background: rgba(255,255,255,0.12); }")
        nav_layout.addWidget(self.btn_refresh)

        # URL / Search Bar
        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Search web or enter address...")
        self.url_bar.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Theme.BG_INPUT};
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }}
            QLineEdit:focus {{
                border-color: {Theme.ACCENT_GREEN};
            }}
        """)
        self.url_bar.returnPressed.connect(self._navigate_url)
        nav_layout.addWidget(self.url_bar, 1)

        # Pop-out to Desktop Browser Button (Brave / Chrome / Firefox)
        self.btn_popout = QPushButton()
        self.btn_popout.setFixedSize(28, 28)
        self.btn_popout.setIcon(icons.get_icon("external_link", color="#CCCCCC", size=14))
        self.btn_popout.setToolTip("Open in external desktop browser (Brave / Chrome / Firefox)")
        self.btn_popout.setCursor(Qt.PointingHandCursor)
        self.btn_popout.setStyleSheet("QPushButton { background: transparent; border: none; border-radius: 4px; } QPushButton:hover { background: rgba(255,255,255,0.12); }")
        self.btn_popout.clicked.connect(self._open_in_external_browser)
        nav_layout.addWidget(self.btn_popout)

        # Clear Browsing Data Button (Trash icon to wipe cookies, logins, and cache if desired)
        self.btn_clear_data = QPushButton()
        self.btn_clear_data.setFixedSize(28, 28)
        self.btn_clear_data.setIcon(icons.get_icon("trash", color="#CCCCCC", size=14))
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

        # 2. Embedded Browser View or Fallback
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

            # Wire navigation actions
            self.btn_back.clicked.connect(self.web_view.back)
            self.btn_forward.clicked.connect(self.web_view.forward)
            self.btn_refresh.clicked.connect(self.web_view.reload)

            # Signals
            self.web_view.urlChanged.connect(self._on_url_changed)
            self.web_view.loadProgress.connect(self._on_load_progress)
            self.web_view.loadFinished.connect(self._on_load_finished)

            # Initial Homepage
            start_url = self.config_manager.get("browser.start_url", "https://duckduckgo.com")
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

    def clear_browsing_data(self) -> None:
        """Clears all session cookies, cache, and history to protect user privacy."""
        if hasattr(self, "_profile") and self._profile:
            self._profile.clearAllVisitedLinks()
            self._profile.clearHttpCache()
            if self._profile.cookieStore():
                self._profile.cookieStore().deleteAllCookies()
            if self.web_view:
                start_url = self.config_manager.get("browser.start_url", "https://duckduckgo.com")
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
        current_url = self.url_bar.text().strip() or "https://duckduckgo.com"
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
            # Launch in app/compact window mode if supported, or standard new tab
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
        # Avoid duplicate injection
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

    // Permissions API query hook so navigator.permissions.query({name: 'clipboard-write'}) succeeds
    if (navigator.permissions && navigator.permissions.query) {
        const origQuery = navigator.permissions.query.bind(navigator.permissions);
        navigator.permissions.query = function(param) {
            if (param && (param.name === "clipboard-write" || param.name === "clipboard-read")) {
                return Promise.resolve({ state: "granted", onchange: null });
            }
            return origQuery(param);
        };
    }

    // DataTransfer.prototype.setData hook
    if (typeof DataTransfer !== "undefined" && DataTransfer.prototype) {
        const origSetData = DataTransfer.prototype.setData;
        DataTransfer.prototype.setData = function(format, data) {
            if (format === "text/plain" || format === "text") {
                sendToHost(data);
            }
            return origSetData.apply(this, arguments);
        };
    }

    // Document copy event listener fallback
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

