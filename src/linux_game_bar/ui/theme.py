"""Xbox Game Bar-inspired dark theme and Windows Fluent QSS styles."""

class Theme:
    # Windows 11 Fluent Acrylic Palette
    BG_OVERLAY = "rgba(12, 12, 14, 0.65)"
    BG_DASHBOARD = "rgba(28, 28, 30, 0.96)"
    BG_WIDGET = "rgba(32, 32, 36, 0.96)"
    BG_CARD = "#27272b"
    BG_CARD_HOVER = "#36363c"
    BG_INPUT = "#1e1e22"

    # Microsoft Official Xbox Green Accents
    ACCENT_GREEN = "#107C41"
    ACCENT_GREEN_HOVER = "#138A4B"
    ACCENT_GREEN_ACTIVE = "#0D6535"
    ACCENT_GREEN_MUTED = "rgba(16, 124, 65, 0.25)"

    # Status colors
    COLOR_DANGER = "#E81123"
    COLOR_WARNING = "#FF8C00"
    COLOR_SUCCESS = "#107C41"

    # Text & Borders
    TEXT_PRIMARY = "#FFFFFF"
    TEXT_SECONDARY = "#CCCCCC"
    TEXT_MUTED = "#8E8E93"
    BORDER_SUBTLE = "rgba(255, 255, 255, 0.08)"
    BORDER_FOCUS = "#107C41"

    @classmethod
    def get_stylesheet(cls, accent: str = ACCENT_GREEN) -> str:
        return f"""
        /* Global Base */
        QWidget {{
            color: {cls.TEXT_PRIMARY};
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI Variable Display", "Segoe UI", Cantarell, "Ubuntu", sans-serif;
            font-size: 13px;
        }}

        /* Tooltips */
        QToolTip {{
            background-color: #202022;
            color: #ffffff;
            border: 1px solid rgba(255, 255, 255, 0.12);
            padding: 5px 9px;
            border-radius: 5px;
            font-size: 11px;
        }}

        /* Scrollbars */
        QScrollBar:vertical {{
            background: transparent;
            width: 6px;
            margin: 0px;
            border-radius: 3px;
        }}
        QScrollBar::handle:vertical {{
            background: rgba(255, 255, 255, 0.18);
            min-height: 24px;
            border-radius: 3px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: rgba(255, 255, 255, 0.32);
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}

        /* Buttons */
        QPushButton {{
            background-color: #2e2e34;
            color: {cls.TEXT_PRIMARY};
            border: 1px solid {cls.BORDER_SUBTLE};
            border-radius: 6px;
            padding: 6px 12px;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: #3b3b44;
            border-color: rgba(255, 255, 255, 0.18);
        }}
        QPushButton:pressed {{
            background-color: #24242a;
        }}
        QPushButton:disabled {{
            background-color: #1f1f23;
            color: {cls.TEXT_MUTED};
            border-color: transparent;
        }}

        /* Accent Buttons */
        QPushButton.accent {{
            background-color: {accent};
            color: #ffffff;
            border: none;
            font-weight: 600;
        }}
        QPushButton.accent:hover {{
            background-color: {cls.ACCENT_GREEN_HOVER};
        }}
        QPushButton.accent:pressed {{
            background-color: {cls.ACCENT_GREEN_ACTIVE};
        }}

        /* Flat Icon Action Buttons (Xbox round/pill buttons) */
        QPushButton.actionRound {{
            background-color: #2c2c32;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 20px;
            min-width: 40px;
            max-width: 40px;
            min-height: 40px;
            max-height: 40px;
            padding: 0px;
        }}
        QPushButton.actionRound:hover {{
            background-color: #3a3a42;
            border-color: rgba(255, 255, 255, 0.22);
        }}
        QPushButton.actionRound:pressed {{
            background-color: #202024;
        }}

        /* Sliders */
        QSlider::groove:horizontal {{
            height: 4px;
            background: #3e3e44;
            border-radius: 2px;
        }}
        QSlider::sub-page:horizontal {{
            background: {accent};
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background: #ffffff;
            width: 14px;
            margin-top: -5px;
            margin-bottom: -5px;
            border-radius: 7px;
        }}
        QSlider::handle:horizontal:hover {{
            background: #eaeaea;
        }}

        /* Inputs & Textboxes */
        QLineEdit, QTextEdit, QPlainTextEdit {{
            background-color: {cls.BG_INPUT};
            color: {cls.TEXT_PRIMARY};
            border: 1px solid {cls.BORDER_SUBTLE};
            border-radius: 6px;
            padding: 6px 10px;
            selection-background-color: {accent};
        }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
            border: 1px solid {accent};
        }}

        /* List views */
        QListWidget {{
            background-color: transparent;
            border: none;
            outline: none;
        }}
        QListWidget::item {{
            padding: 8px 12px;
            border-radius: 6px;
            margin-bottom: 3px;
        }}
        QListWidget::item:hover {{
            background-color: {cls.BG_CARD_HOVER};
        }}
        QListWidget::item:selected {{
            background-color: {cls.ACCENT_GREEN_MUTED};
            border-left: 3px solid {accent};
        }}

        /* Checkboxes */
        QCheckBox {{
            spacing: 8px;
            color: {cls.TEXT_PRIMARY};
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border-radius: 4px;
            border: 1px solid rgba(255, 255, 255, 0.25);
            background: #242428;
        }}
        QCheckBox::indicator:hover {{
            border-color: rgba(255, 255, 255, 0.45);
        }}
        QCheckBox::indicator:checked {{
            background-color: {accent};
            border-color: {accent};
        }}

        /* Tab Widget (Xbox Game Bar [MIX] [VOICE] style) */
        QTabBar::tab {{
            background: transparent;
            color: {cls.TEXT_MUTED};
            padding: 6px 14px;
            margin-right: 4px;
            font-weight: 600;
            font-size: 11px;
            letter-spacing: 0.5px;
            border-bottom: 2px solid transparent;
        }}
        QTabBar::tab:hover {{
            color: {cls.TEXT_PRIMARY};
        }}
        QTabBar::tab:selected {{
            color: #ffffff;
            border-bottom: 2px solid {accent};
        }}
        QTabWidget::pane {{
            border: none;
            background: transparent;
        }}

        /* Combo Box */
        QComboBox {{
            background-color: #29292e;
            border: 1px solid {cls.BORDER_SUBTLE};
            border-radius: 6px;
            padding: 5px 10px;
            color: {cls.TEXT_PRIMARY};
        }}
        QComboBox:hover {{
            background-color: #33333a;
        }}
        QComboBox::drop-down {{
            border: none;
            width: 20px;
        }}
        QComboBox QAbstractItemView {{
            background-color: #222226;
            border: 1px solid rgba(255, 255, 255, 0.15);
            selection-background-color: {cls.BG_CARD_HOVER};
            color: {cls.TEXT_PRIMARY};
        }}
        """
