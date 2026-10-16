"""
Hotkey capture field matching Windows Auto-Typer-Game-Bar PreviewKeyDown logic.
Listens for keyboard input when focused, formats key combination, and ignores solitary modifiers.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QLineEdit
from linux_game_bar.ui.theme import Theme


class HotKeyCaptureBox(QLineEdit):
    """Interactive hotkey box where clicking and pressing keys sets the shortcut."""

    hotkey_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Click & press keys (e.g. F8, Ctrl+T)")
        self.setReadOnly(True)
        self.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 4px;
                padding: 4px 6px;
                color: #FFFFFF;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid {Theme.ACCENT_GREEN};
                background-color: #2e2e34;
            }}
        """)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        modifiers = event.modifiers()

        # Ignore solitary modifier keypresses
        if key in (
            Qt.Key_Control,
            Qt.Key_Shift,
            Qt.Key_Alt,
            Qt.Key_Meta,
            Qt.Key_AltGr,
            Qt.Key_Super_L,
            Qt.Key_Super_R,
        ):
            return

        # Clear on Backspace, Delete, or Escape
        if key in (Qt.Key_Backspace, Qt.Key_Delete, Qt.Key_Escape):
            self.setText("None")
            self.hotkey_changed.emit("None")
            event.accept()
            return

        mods_str = []
        if modifiers & Qt.ControlModifier:
            mods_str.append("Control")
        if modifiers & Qt.ShiftModifier:
            mods_str.append("Shift")
        if modifiers & Qt.AltModifier:
            mods_str.append("Alt")
        if modifiers & Qt.MetaModifier:
            mods_str.append("Windows")

        key_name = ""
        # Function keys F1 - F24
        if Qt.Key_F1 <= key <= Qt.Key_F24:
            f_num = key - Qt.Key_F1 + 1
            key_name = f"F{f_num}"
        # Number keys
        elif Qt.Key_0 <= key <= Qt.Key_9:
            num = key - Qt.Key_0
            key_name = f"D{num}"
        # Letters A - Z
        elif Qt.Key_A <= key <= Qt.Key_Z:
            key_name = chr(key)
        # Common controls matching Windows AutoTyper naming
        elif key == Qt.Key_Space:
            key_name = "Space"
        elif key == Qt.Key_Tab:
            key_name = "Tab"
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            key_name = "Return"
        elif key == Qt.Key_Insert:
            key_name = "Insert"
        elif key == Qt.Key_Home:
            key_name = "Home"
        elif key == Qt.Key_End:
            key_name = "End"
        elif key == Qt.Key_PageUp:
            key_name = "PageUp"
        elif key == Qt.Key_PageDown:
            key_name = "PageDown"
        else:
            text = event.text().upper()
            if text and text.isalnum():
                key_name = text
            else:
                key_name = f"Key_{key}"

        if mods_str:
            res = ", ".join(mods_str) + " + " + key_name
        else:
            res = key_name

        self.setText(res)
        self.hotkey_changed.emit(res)
        event.accept()
