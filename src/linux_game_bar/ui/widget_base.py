"""Base floating widget window with Xbox styling, dragging, pinning, and resizing."""

from PySide6.QtCore import Qt, QPoint, Signal, QRect, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QCursor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QSizeGrip,
    QScrollArea,
)

from linux_game_bar.ui.theme import Theme
from linux_game_bar.ui import icons


class WidgetBase(QFrame):
    """Base container for dashboard widgets."""

    closed = Signal(str)  # widget_id
    pinned_changed = Signal(str, bool)  # widget_id, is_pinned
    geometry_changed = Signal(str, int, int, int, int)  # widget_id, x, y, w, h

    def __init__(
        self,
        widget_id: str,
        title: str,
        icon_str: str = "plugin",
        parent: QWidget = None,
    ):
        super().__init__(parent)
        self.widget_id = widget_id
        self.widget_title = title
        self.icon_name = icon_str
        self.is_pinned = False

        self._drag_pos = QPoint()
        self._dragging = False

        self._init_window_flags()
        self._init_ui()

    def _init_window_flags(self) -> None:
        # Frameless window so we have full control over custom styling
        self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def _init_ui(self) -> None:
        self.setObjectName("WidgetBase")
        self.setStyleSheet(f"""
            QFrame#WidgetBase {{
                background-color: {Theme.BG_WIDGET};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 8px;
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(1, 1, 1, 1)
        main_layout.setSpacing(0)

        # Header Bar
        self.header = QWidget()
        self.header.setObjectName("WidgetHeader")
        self.header.setFixedHeight(34)
        self.header.setStyleSheet(f"""
            QWidget#WidgetHeader {{
                background-color: rgba(255, 255, 255, 0.03);
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
                border-bottom: 1px solid {Theme.BORDER_SUBTLE};
            }}
        """)

        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(10, 0, 6, 0)
        header_layout.setSpacing(8)

        # Icon
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(16, 16)
        self.icon_label.setStyleSheet("background: transparent;")
        self._update_header_icon()
        header_layout.addWidget(self.icon_label)

        # Title (UPPERCASE Xbox style, 11px semi-bold)
        self.title_label = QLabel(self.widget_title.upper())
        self.title_label.setStyleSheet(
            "font-weight: 700; font-size: 11px; letter-spacing: 0.8px; color: #E5E5E5; background: transparent;"
        )
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        # Pin Button
        self.btn_pin = QPushButton()
        self.btn_pin.setFixedSize(26, 26)
        self.btn_pin.setIconSize(QSize(14, 14))
        self.btn_pin.setToolTip("Pin widget to screen (keep visible when Game Bar closes)")
        self.btn_pin.setCursor(Qt.PointingHandCursor)
        self._update_pin_button_style()
        self.btn_pin.clicked.connect(self._toggle_pin)
        header_layout.addWidget(self.btn_pin)

        # Close Button
        self.btn_close = QPushButton()
        self.btn_close.setFixedSize(26, 26)
        self.btn_close.setIconSize(QSize(12, 12))
        self.btn_close.setIcon(icons.get_icon("close", color="#CCCCCC", size=14))
        self.btn_close.setToolTip("Close widget")
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #E81123;
            }
        """)
        self.btn_close.clicked.connect(self.close_widget)
        header_layout.addWidget(self.btn_close)

        main_layout.addWidget(self.header)

        # Body Content Area with ScrollArea protection against squashed layouts
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: rgba(255, 255, 255, 0.03);
                width: 6px;
                border-radius: 3px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.2);
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255, 255, 255, 0.35);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self.body_container = QWidget()
        self.body_container.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.body_container)
        self.content_layout.setContentsMargins(10, 8, 10, 8)
        self.content_layout.setSpacing(8)

        self.scroll_area.setWidget(self.body_container)
        main_layout.addWidget(self.scroll_area, 1)

        # Footer with Resize Grip
        footer = QWidget()
        footer.setFixedHeight(12)
        footer.setStyleSheet("background: transparent;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 2, 2)
        footer_layout.addStretch()

        self.size_grip = QSizeGrip(footer)
        self.size_grip.setFixedSize(10, 10)
        self.size_grip.setStyleSheet("background: transparent;")
        footer_layout.addWidget(self.size_grip)

        main_layout.addWidget(footer)

    def _update_header_icon(self) -> None:
        """Update header icon using SVG vector graphics."""
        # Check if icon_name matches an SVG template name
        icon_key = self.icon_name
        # Fallback mappings for old emoji strings if passed
        emoji_map = {
            "🎮": "launcher",
            "🔊": "audio",
            "📸": "camera",
            "📊": "performance",
            "🚀": "launcher",
            "📝": "notes",
            "⏱️": "timer",
            "⚙️": "settings",
        }
        if icon_key in emoji_map:
            icon_key = emoji_map[icon_key]

        pixmap = icons.get_pixmap(icon_key, color="#CCCCCC", size=16)
        if not pixmap.isNull():
            self.icon_label.setPixmap(pixmap)
        else:
            self.icon_label.setPixmap(icons.get_pixmap("plugin", color="#CCCCCC", size=16))

    def _update_pin_button_style(self) -> None:
        if self.is_pinned:
            self.btn_pin.setIcon(icons.get_icon("pin_filled", color="#FFFFFF", size=14))
            self.btn_pin.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Theme.ACCENT_GREEN};
                    border: none;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    background-color: {Theme.ACCENT_GREEN_HOVER};
                }}
            """)
        else:
            self.btn_pin.setIcon(icons.get_icon("pin", color="#CCCCCC", size=14))
            self.btn_pin.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.12);
                }
            """)

    def _toggle_pin(self) -> None:
        self.is_pinned = not self.is_pinned
        self._update_pin_button_style()
        self.pinned_changed.emit(self.widget_id, self.is_pinned)

    def set_pinned(self, pinned: bool) -> None:
        if self.is_pinned != pinned:
            self._toggle_pin()

    def close_widget(self) -> None:
        self.hide()
        self.closed.emit(self.widget_id)

    # Mouse dragging support via header
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            header_rect = QRect(0, 0, self.width(), self.header.height())
            if header_rect.contains(event.position().toPoint()):
                self._dragging = True
                self._drag_pos = event.globalPosition().toPoint() - self.pos()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._dragging and event.buttons() & Qt.LeftButton:
            new_pos = event.globalPosition().toPoint() - self._drag_pos
            self.move(new_pos)
            self._emit_geometry()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._dragging = False
        self._emit_geometry()
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._emit_geometry()

    def _emit_geometry(self) -> None:
        pos = self.pos()
        self.geometry_changed.emit(self.widget_id, pos.x(), pos.y(), self.width(), self.height())
