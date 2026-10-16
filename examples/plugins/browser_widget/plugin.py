"""
Sample In-Game Browser Widget Plugin for Microsoft.Gaming.XboxGameBar.
Demonstrates packaging an embedded web companion widget using the 1:1 SDK.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton
from PySide6.QtCore import Qt, QUrl
from linux_game_bar.sdk import (
    XboxGameBarWidgetPlugin,
    WidgetMetadata,
    XboxGameBarWidgetActivatedEventArgs,
)
from linux_game_bar.ui import icons

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False


class InGameBrowserPlugin(XboxGameBarWidgetPlugin):
    METADATA = WidgetMetadata(
        id="com.microsoft.gaming.browser",
        title="WEB BROWSER",
        version="1.0.0",
        author="Linux Game Bar Team",
        description="In-game phone/tab companion browser for game wikis, maps, and guides.",
        icon_name="globe",
        default_width=400,
        default_height=580,
        min_width=320,
        min_height=400,
    )

    def on_navigated_to(self, args: XboxGameBarWidgetActivatedEventArgs) -> QWidget:
        self.widget = args.widget
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Nav bar
        nav = QHBoxLayout()
        self.url_input = QLineEdit("https://duckduckgo.com")
        self.url_input.setStyleSheet("background-color: #1e1e22; color: #fff; padding: 4px; border-radius: 4px;")
        nav.addWidget(self.url_input)

        btn_go = QPushButton("Go")
        btn_go.setFixedWidth(40)
        nav.addWidget(btn_go)
        layout.addLayout(nav)

        if HAS_WEBENGINE:
            self.view = QWebEngineView()
            self.view.setUrl(QUrl("https://duckduckgo.com"))
            btn_go.clicked.connect(lambda: self.view.setUrl(QUrl(self.url_input.text())))
            self.url_input.returnPressed.connect(lambda: self.view.setUrl(QUrl(self.url_input.text())))
            layout.addWidget(self.view, 1)

        return container
