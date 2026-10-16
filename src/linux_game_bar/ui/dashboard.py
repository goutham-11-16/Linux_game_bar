"""Top floating dashboard navigation bar inspired by Windows 11 Xbox Game Bar."""

import time
from typing import Dict, List, Optional
from PySide6.QtCore import Qt, Signal, QTimer, QPoint, QRect, QSize
from PySide6.QtGui import QColor, QCursor, QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QScrollArea,
)

from linux_game_bar.ui.theme import Theme
from linux_game_bar.ui import icons


class WidgetMenuItem(QFrame):
    """An entry row in the Widget Menu flyout."""

    toggled = Signal(str)  # widget_id
    favorite_toggled = Signal(str, bool)  # widget_id, is_favorite

    def __init__(
        self,
        widget_id: str,
        display_name: str,
        icon_name: str,
        shortcut: str = "",
        is_favorite: bool = True,
        parent: QWidget = None,
    ):
        super().__init__(parent)
        self.widget_id = widget_id
        self.display_name = display_name
        self.icon_name = icon_name
        self.is_favorite = is_favorite

        self.setFixedHeight(38)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: transparent;
                border-radius: 6px;
            }}
            QFrame:hover {{
                background-color: {Theme.BG_CARD_HOVER};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(10)

        # Icon
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(18, 18)
        self.icon_label.setPixmap(icons.get_pixmap(icon_name, color="#CCCCCC", size=18))
        self.icon_label.setStyleSheet("background: transparent;")
        layout.addWidget(self.icon_label)

        # Name & Shortcut
        text_layout = QVBoxLayout()
        text_layout.setSpacing(0)
        text_layout.setAlignment(Qt.AlignVCenter)

        self.name_label = QLabel(display_name)
        self.name_label.setStyleSheet("font-weight: 500; font-size: 13px; color: #FFFFFF; background: transparent;")
        text_layout.addWidget(self.name_label)

        if shortcut:
            self.sc_label = QLabel(shortcut)
            self.sc_label.setStyleSheet("font-size: 10px; color: #888888; background: transparent;")
            text_layout.addWidget(self.sc_label)

        layout.addLayout(text_layout, 1)

        # Favorite / Star button
        self.btn_fav = QPushButton()
        self.btn_fav.setFixedSize(24, 24)
        self.btn_fav.setIconSize(QSize(14, 14))
        self.btn_fav.setCursor(Qt.PointingHandCursor)
        self._update_star()
        self.btn_fav.clicked.connect(self._toggle_star)
        layout.addWidget(self.btn_fav)

    def _update_star(self) -> None:
        if self.is_favorite:
            self.btn_fav.setIcon(icons.get_icon("star", color="#FFD700", size=14))
            self.btn_fav.setToolTip("Remove from Home Bar favorites")
            self.btn_fav.setStyleSheet("background: transparent; border: none;")
        else:
            self.btn_fav.setIcon(icons.get_icon("star_outline", color="#777777", size=14))
            self.btn_fav.setToolTip("Add to Home Bar favorites")
            self.btn_fav.setStyleSheet("background: transparent; border: none;")

    def _toggle_star(self) -> None:
        self.is_favorite = not self.is_favorite
        self._update_star()
        self.favorite_toggled.emit(self.widget_id, self.is_favorite)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            # Check if clicked on star button area
            if not self.btn_fav.geometry().contains(event.position().toPoint()):
                self.toggled.emit(self.widget_id)
                event.accept()
                return
        super().mousePressEvent(event)


class WidgetMenuFlyout(QFrame):
    """Dropdown flyout displayed when clicking the Xbox button on the Home Bar."""

    widget_toggled = Signal(str)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("WidgetMenuFlyout")
        self.setFixedWidth(280)
        self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.setStyleSheet(f"""
            QFrame#WidgetMenuFlyout {{
                background-color: {Theme.BG_WIDGET};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 8px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Header
        header = QLabel("WIDGET MENU")
        header.setStyleSheet("font-size: 11px; font-weight: 700; letter-spacing: 0.8px; color: #8E8E93; padding: 2px 4px;")
        layout.addWidget(header)

        # Scrollable items list
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("background: transparent; border: none;")

        self.items_container = QWidget()
        self.items_container.setStyleSheet("background: transparent;")
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(2)

        self.scroll.setWidget(self.items_container)
        layout.addWidget(self.scroll, 1)

        self._items: Dict[str, WidgetMenuItem] = {}

    def add_widget_entry(
        self,
        widget_id: str,
        display_name: str,
        icon_name: str,
        shortcut: str = "",
        is_favorite: bool = True,
    ) -> None:
        item = WidgetMenuItem(
            widget_id=widget_id,
            display_name=display_name,
            icon_name=icon_name,
            shortcut=shortcut,
            is_favorite=is_favorite,
            parent=self.items_container,
        )
        item.toggled.connect(self.widget_toggled.emit)
        self._items[widget_id] = item
        self.items_layout.addWidget(item)

        # Dynamically size flyout
        total_items = len(self._items)
        flyout_h = min(420, 48 + total_items * 40)
        self.setFixedHeight(flyout_h)


class DashboardBar(QFrame):
    """Top floating controller bar matching Windows 11 Xbox Game Bar."""

    widget_toggled = Signal(str, bool)  # widget_id, active
    settings_clicked = Signal()
    quit_clicked = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._buttons: Dict[str, QPushButton] = {}
        self._dragging = False
        self._drag_pos = QPoint()

        self._init_window_flags()
        self._init_ui()
        self._start_clock()

    def _init_window_flags(self) -> None:
        self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def _init_ui(self) -> None:
        self.setObjectName("DashboardBar")
        self.setFixedHeight(44)
        self.setStyleSheet(f"""
            QFrame#DashboardBar {{
                background-color: {Theme.BG_DASHBOARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 8px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(4)

        # 1. Xbox Orb Button (Home Bar anchor)
        self.btn_xbox = QPushButton()
        self.btn_xbox.setFixedSize(36, 36)
        self.btn_xbox.setIconSize(QSize(22, 22))
        self.btn_xbox.setIcon(icons.get_icon("xbox", color="#FFFFFF", active_color="#107C41", size=22))
        self.btn_xbox.setToolTip("Widget Menu (Super + G)")
        self.btn_xbox.setCursor(Qt.PointingHandCursor)
        self.btn_xbox.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.12);
            }}
            QPushButton:pressed {{
                background-color: {Theme.ACCENT_GREEN_ACTIVE};
            }}
        """)
        self.btn_xbox.clicked.connect(self._toggle_widget_menu)
        layout.addWidget(self.btn_xbox)

        # Widget Menu Button (Grid icon)
        self.btn_widget_menu = QPushButton()
        self.btn_widget_menu.setFixedSize(32, 34)
        self.btn_widget_menu.setIconSize(QSize(16, 16))
        self.btn_widget_menu.setIcon(icons.get_icon("menu", color="#CCCCCC", size=16))
        self.btn_widget_menu.setToolTip("All Widgets")
        self.btn_widget_menu.setCursor(Qt.PointingHandCursor)
        self.btn_widget_menu.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.08);
            }
        """)
        self.btn_widget_menu.clicked.connect(self._toggle_widget_menu)
        layout.addWidget(self.btn_widget_menu)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setStyleSheet("background-color: rgba(255, 255, 255, 0.1); width: 1px; margin: 8px 3px;")
        layout.addWidget(sep1)

        # 2. Middle Widget Quick-Toggle Buttons (Clean Fluent vector icons)
        widgets_info = [
            ("performance", "performance", "Performance (CPU, RAM, GPU)"),
            ("audio", "audio", "Audio Mixer"),
            ("capture", "camera", "Capture (Screenshot & Recording)"),
            ("browser", "globe", "Web Browser"),
            ("launcher", "launcher", "Game & App Launcher"),
            ("battery", "performance", "Battery & Thermals"),
            ("notes", "notes", "Notes"),
            ("timer", "timer", "Game Timer"),
        ]

        for w_id, icon_name, tooltip in widgets_info:
            btn = QPushButton()
            btn.setFixedSize(36, 36)
            btn.setIconSize(QSize(18, 18))
            btn.setIcon(icons.get_icon(icon_name, color="#CCCCCC", active_color="#FFFFFF", size=18))
            btn.setToolTip(tooltip)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            self._apply_button_style(btn, active=False)
            btn.clicked.connect(lambda checked, wid=w_id: self.widget_toggled.emit(wid, checked))
            self._buttons[w_id] = btn
            layout.addWidget(btn)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setStyleSheet("background-color: rgba(255, 255, 255, 0.1); width: 1px; margin: 8px 3px;")
        layout.addWidget(sep2)

        # 3. Digital Clock
        self.clock_label = QLabel("12:00")
        self.clock_label.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: #D5D5D5; padding: 0 6px; background: transparent;"
        )
        layout.addWidget(self.clock_label)

        # 4. Settings Button (Gear vector icon)
        self.btn_settings = QPushButton()
        self.btn_settings.setFixedSize(32, 34)
        self.btn_settings.setIconSize(QSize(16, 16))
        self.btn_settings.setIcon(icons.get_icon("settings", color="#CCCCCC", size=16))
        self.btn_settings.setToolTip("Settings")
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self._apply_icon_button_style(self.btn_settings)
        self.btn_settings.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self.btn_settings)

        # 5. Close / Dismiss Button (Fluent vector cross)
        self.btn_close = QPushButton()
        self.btn_close.setFixedSize(32, 34)
        self.btn_close.setIconSize(QSize(13, 13))
        self.btn_close.setIcon(icons.get_icon("close", color="#CCCCCC", active_color="#FFFFFF", size=13))
        self.btn_close.setToolTip("Close Overlay (Super + G)")
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #E81123;
            }
        """)
        self.btn_close.clicked.connect(self.quit_clicked.emit)
        layout.addWidget(self.btn_close)

        # Create the widget menu flyout
        self.menu_flyout = WidgetMenuFlyout(self.parentWidget() or self)
        self.menu_flyout.hide()
        self.menu_flyout.widget_toggled.connect(self._on_flyout_widget_toggled)

        # Populate default entries in flyout
        for w_id, icon_name, tooltip in widgets_info:
            name = w_id.capitalize()
            self.menu_flyout.add_widget_entry(w_id, name, icon_name, is_favorite=True)

    def _toggle_widget_menu(self) -> None:
        if self.menu_flyout.isVisible():
            self.menu_flyout.hide()
        else:
            # Position flyout right under the Xbox button
            global_pos = self.mapToGlobal(QPoint(self.btn_xbox.x(), self.height() + 8))
            parent_pos = self.parentWidget().mapFromGlobal(global_pos) if self.parentWidget() else global_pos
            self.menu_flyout.move(parent_pos)
            self.menu_flyout.show()
            self.menu_flyout.raise_()

    def _on_flyout_widget_toggled(self, widget_id: str) -> None:
        # Toggle widget state
        btn = self._buttons.get(widget_id)
        if btn:
            new_checked = not btn.isChecked()
            btn.setChecked(new_checked)
            self.set_widget_active(widget_id, new_checked)
            self.widget_toggled.emit(widget_id, new_checked)
        else:
            self.widget_toggled.emit(widget_id, True)

    def _start_clock(self) -> None:
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._update_clock()

    def _update_clock(self) -> None:
        self.clock_label.setText(time.strftime("%H:%M"))

    def set_widget_active(self, widget_id: str, is_active: bool) -> None:
        if widget_id in self._buttons:
            btn = self._buttons[widget_id]
            btn.blockSignals(True)
            btn.setChecked(is_active)
            self._apply_button_style(btn, is_active)
            btn.blockSignals(False)

    def _apply_button_style(self, btn: QPushButton, active: bool) -> None:
        if active:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba(255, 255, 255, 0.12);
                    border-bottom: 2.5px solid {Theme.ACCENT_GREEN};
                    border-top: none;
                    border-left: none;
                    border-right: none;
                    border-radius: 4px;
                }}
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.08);
                }
            """)

    def _apply_icon_button_style(self, btn: QPushButton) -> None:
        btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.08);
            }
        """)

    # Dragging support
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._dragging and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._dragging = False
        super().mouseReleaseEvent(event)
