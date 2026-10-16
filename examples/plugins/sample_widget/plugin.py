"""
Sample Custom Widget Plugin for Linux Game Bar SDK.
Demonstrates how third-party developers build widgets with zero boilerplate.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt
from linux_game_bar.sdk import GameBarWidgetPlugin, WidgetMetadata, WidgetContext


class SampleWidget(GameBarWidgetPlugin):
    METADATA = WidgetMetadata(
        id="com.example.quick_links",
        title="QUICK LINKS",
        version="1.0.0",
        author="Community Developer",
        description="Quick access links and shortcuts for gaming sessions.",
        icon_name="external_link",
        default_width=300,
        default_height=260,
    )

    def build_widget(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        lbl = QLabel("Custom SDK Widget")
        lbl.setStyleSheet("font-size: 14px; font-weight: 700; color: #FFFFFF;")
        layout.addWidget(lbl)

        desc = QLabel("Built using linux_game_bar.sdk GameBarWidgetPlugin.")
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 11px; color: #A0A0A5;")
        layout.addWidget(desc)

        btn = QPushButton("Ping Host Notification")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: self.context.show_notification("Quick Links", "Hello from custom SDK widget!"))
        layout.addWidget(btn)

        layout.addStretch()
        return container
