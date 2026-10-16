"""
Sample Custom Widget Plugin for Linux Game Bar SDK.
Demonstrates the 1:1 Microsoft.Gaming.XboxGameBar developer contract.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QCheckBox
from PySide6.QtCore import Qt
from linux_game_bar.sdk import (
    XboxGameBarWidgetPlugin,
    WidgetMetadata,
    XboxGameBarWidgetActivatedEventArgs,
    XboxGameBarDisplayMode,
)


class SampleQuickLinksWidget(XboxGameBarWidgetPlugin):
    METADATA = WidgetMetadata(
        id="com.example.quick_links",
        title="QUICK LINKS",
        version="1.0.0",
        author="Community Developer",
        description="Quick access links and shortcuts for gaming sessions.",
        icon_name="external_link",
        default_width=320,
        default_height=300,
    )

    def on_navigated_to(self, args: XboxGameBarWidgetActivatedEventArgs) -> QWidget:
        # Save reference to the 1:1 XboxGameBarWidget instance
        self.widget = args.widget
        self.widget.pinned_changed.connect(self._on_pinned_changed)
        self.widget.settings_supported = True
        self.widget.settings_clicked.connect(self._on_settings_clicked)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        lbl = QLabel("Microsoft.Gaming.XboxGameBar Plugin")
        lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #FFFFFF;")
        layout.addWidget(lbl)

        self.lbl_pin_status = QLabel(f"Pinned State: {self.widget.pinned}")
        self.lbl_pin_status.setStyleSheet("font-size: 11px; color: #107C41; font-weight: 600;")
        layout.addWidget(self.lbl_pin_status)

        # Click-through toggle (Xbox Game Bar authentic feature)
        self.chk_clickthrough = QCheckBox("Enable Click-Through (when pinned)")
        self.chk_clickthrough.setStyleSheet("font-size: 11px; color: #A0A0A5;")
        self.chk_clickthrough.toggled.connect(self._on_clickthrough_toggled)
        layout.addWidget(self.chk_clickthrough)

        btn_notify = QPushButton("Send In-Game Notification")
        btn_notify.setCursor(Qt.PointingHandCursor)
        btn_notify.clicked.connect(self._send_notification)
        layout.addWidget(btn_notify)

        layout.addStretch()
        return container

    def _on_pinned_changed(self, widget, is_pinned: bool) -> None:
        if hasattr(self, "lbl_pin_status"):
            self.lbl_pin_status.setText(f"Pinned State: {is_pinned}")

    def _on_clickthrough_toggled(self, checked: bool) -> None:
        if self.widget:
            self.widget.click_through_enabled = checked

    def _on_settings_clicked(self, widget) -> None:
        self.widget.notification_manager.show_notification_async(
            "Quick Links", "Settings clicked on widget!"
        )

    def _send_notification(self) -> None:
        if self.widget:
            self.widget.notification_manager.show_notification_async(
                "Xbox Game Bar", "Achievement / In-game event notification!"
            )
