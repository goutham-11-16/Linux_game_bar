"""
AutoTyper widget for Linux Game Bar.
Rebuild of Windows Auto-Typer-Game-Bar (C++/WinRT + C# worker) into native PySide6.
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QComboBox,
    QProgressBar,
    QFrame,
    QScrollArea,
)

from linux_game_bar.ui.widget_base import WidgetBase
from linux_game_bar.ui.theme import Theme
from linux_game_bar.ui import icons
from linux_game_bar.core.autotyper_engine import (
    AutoTyperWorker,
    Snippet,
    TypingMode,
)
from linux_game_bar.core.hotkey_service import get_hotkey_service
from linux_game_bar.widgets.hotkey_capture import HotKeyCaptureBox

logger = logging.getLogger("linux_game_bar.widgets.autotyper")


class AutoTyperWidget(WidgetBase):
    """
    Standalone Auto Typer Widget matching Microsoft Xbox Game Bar layout & features.
    """

    trigger_hotkey_signal = Signal(object)
    esc_pressed_signal = Signal()

    def __init__(self, config_manager=None, parent: Optional[QWidget] = None):
        super().__init__("autotyper", "AUTO TYPER", "keyboard", parent)
        self.config_manager = config_manager
        self.trigger_hotkey_signal.connect(self._trigger_snippet_by_hotkey)
        self.esc_pressed_signal.connect(self._handle_esc_pressed)
        self.setMinimumSize(400, 520)
        self.resize(410, 560)

        # Snippets storage path
        data_home = os.environ.get("XDG_DATA_HOME")
        base = Path(data_home) if data_home else Path.home() / ".local" / "share"
        self._storage_path = base / "linux-game-bar" / "autotyper_snippets.json"
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

        self.snippets: List[Snippet] = []
        self.current_snippet: Optional[Snippet] = None
        self._worker: Optional[AutoTyperWorker] = None
        self._active_running_snippet_id: Optional[str] = None

        self._build_ui()
        self._load_snippets()

    def _build_ui(self) -> None:
        layout = self.content_layout
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)

        # -------------------------------------------------------------
        # Row 0: Status & Connection Header
        # -------------------------------------------------------------
        header_row = QHBoxLayout()
        title_lbl = QLabel("AUTO TYPER FOR GAME BAR")
        title_lbl.setStyleSheet(f"font-weight: bold; font-size: 11px; color: {Theme.ACCENT_GREEN}; background: transparent;")
        header_row.addWidget(title_lbl)
        header_row.addStretch()

        self.dot_lbl = QLabel("●")
        self.dot_lbl.setStyleSheet("color: #4CAF50; font-size: 14px; background: transparent;")
        header_row.addWidget(self.dot_lbl)

        self.status_lbl = QLabel("Ready")
        self.status_lbl.setStyleSheet("font-size: 11px; color: #CCCCCC; background: transparent;")
        header_row.addWidget(self.status_lbl)

        layout.addLayout(header_row)

        # -------------------------------------------------------------
        # Row 1: Snippet Selector + Add + Delete
        # -------------------------------------------------------------
        snip_row = QHBoxLayout()
        snip_row.setSpacing(6)

        self.combo_snippets = QComboBox()
        self.combo_snippets.setStyleSheet(f"""
            QComboBox {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 4px;
                padding: 4px 8px;
                color: #FFFFFF;
                font-size: 12px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {Theme.BG_CARD};
                color: #FFFFFF;
                selection-background-color: {Theme.ACCENT_GREEN};
            }}
        """)
        self.combo_snippets.currentIndexChanged.connect(self._on_snippet_selected)
        snip_row.addWidget(self.combo_snippets, 1)

        self.btn_add = QPushButton("+ Add")
        self.btn_add.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                color: #E5E5E5;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.12);
            }}
        """)
        self.btn_add.clicked.connect(self._create_new_snippet)
        snip_row.addWidget(self.btn_add)

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid rgba(239, 83, 80, 0.4);
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                color: #EF5350;
            }
            QPushButton:hover {
                background-color: rgba(239, 83, 80, 0.2);
            }
        """)
        self.btn_delete.clicked.connect(self._delete_current_snippet)
        snip_row.addWidget(self.btn_delete)

        layout.addLayout(snip_row)

        # -------------------------------------------------------------
        # Row 2: Name & Hotkey Trigger
        # -------------------------------------------------------------
        name_hot_row = QHBoxLayout()
        name_hot_row.setSpacing(8)

        # Name field
        name_col = QVBoxLayout()
        name_col.setSpacing(2)
        lbl_name = QLabel("Name")
        lbl_name.setStyleSheet("font-size: 11px; color: #AAAAAA; background: transparent;")
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("Snippet name")
        self.input_name.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 4px;
                padding: 4px 6px;
                color: #FFFFFF;
                font-size: 12px;
            }}
        """)
        name_col.addWidget(lbl_name)
        name_col.addWidget(self.input_name)
        name_hot_row.addLayout(name_col, 1)

        # Hotkey field (interactive key press capture matching Windows WidgetView)
        hot_col = QVBoxLayout()
        hot_col.setSpacing(2)
        lbl_hot = QLabel("Hotkey Trigger")
        lbl_hot.setStyleSheet("font-size: 11px; color: #AAAAAA; background: transparent;")
        self.input_hotkey = HotKeyCaptureBox()
        hot_col.addWidget(lbl_hot)
        hot_col.addWidget(self.input_hotkey)
        name_hot_row.addLayout(hot_col, 1)

        layout.addLayout(name_hot_row)

        # -------------------------------------------------------------
        # Row 3: Mode & Delays
        # -------------------------------------------------------------
        mode_delay_row = QHBoxLayout()
        mode_delay_row.setSpacing(8)

        # Mode dropdown
        mode_col = QVBoxLayout()
        mode_col.setSpacing(2)
        lbl_mode = QLabel("Typing Mode")
        lbl_mode.setStyleSheet("font-size: 11px; color: #AAAAAA; background: transparent;")
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["HumanLike", "Paste", "Fast", "Macro"])
        self.combo_mode.setStyleSheet(f"""
            QComboBox {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 4px;
                padding: 4px 6px;
                color: #FFFFFF;
                font-size: 12px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {Theme.BG_CARD};
                color: #FFFFFF;
                selection-background-color: {Theme.ACCENT_GREEN};
            }}
        """)
        mode_col.addWidget(lbl_mode)
        mode_col.addWidget(self.combo_mode)
        mode_delay_row.addLayout(mode_col, 1)

        # Delays
        delay_col = QVBoxLayout()
        delay_col.setSpacing(2)
        lbl_delay = QLabel("Delays: Char / Word (ms)")
        lbl_delay.setStyleSheet("font-size: 11px; color: #AAAAAA; background: transparent;")
        
        delay_inputs = QHBoxLayout()
        delay_inputs.setSpacing(4)
        self.input_char_delay = QLineEdit("15")
        self.input_char_delay.setFixedWidth(55)
        self.input_char_delay.setStyleSheet(f"background-color: {Theme.BG_CARD}; border: 1px solid {Theme.BORDER_SUBTLE}; border-radius: 4px; padding: 4px; color: #FFF; font-size: 12px;")
        
        self.input_word_delay = QLineEdit("50")
        self.input_word_delay.setFixedWidth(55)
        self.input_word_delay.setStyleSheet(f"background-color: {Theme.BG_CARD}; border: 1px solid {Theme.BORDER_SUBTLE}; border-radius: 4px; padding: 4px; color: #FFF; font-size: 12px;")
        
        delay_inputs.addWidget(self.input_char_delay)
        delay_inputs.addWidget(self.input_word_delay)
        delay_col.addWidget(lbl_delay)
        delay_col.addLayout(delay_inputs)
        mode_delay_row.addLayout(delay_col, 1)

        layout.addLayout(mode_delay_row)

        # -------------------------------------------------------------
        # Row 4: Macro Buttons & Clipboard/Clear
        # -------------------------------------------------------------
        macro_row = QHBoxLayout()
        lbl_macros = QLabel("Macros:")
        lbl_macros.setStyleSheet("font-size: 11px; color: #AAAAAA; background: transparent;")
        macro_row.addWidget(lbl_macros)

        btn_style = f"""
            QPushButton {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 3px;
                padding: 2px 6px;
                font-size: 10px;
                color: #CCCCCC;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.15);
                color: #FFFFFF;
            }}
        """

        self.btn_enter = QPushButton("{ENTER}")
        self.btn_enter.setStyleSheet(btn_style)
        self.btn_enter.clicked.connect(lambda: self._insert_macro("{ENTER}"))
        macro_row.addWidget(self.btn_enter)

        self.btn_tab = QPushButton("{TAB}")
        self.btn_tab.setStyleSheet(btn_style)
        self.btn_tab.clicked.connect(lambda: self._insert_macro("{TAB}"))
        macro_row.addWidget(self.btn_tab)

        self.btn_delay = QPushButton("{DELAY}")
        self.btn_delay.setStyleSheet(btn_style)
        self.btn_delay.clicked.connect(lambda: self._insert_macro("{DELAY 500}"))
        macro_row.addWidget(self.btn_delay)

        macro_row.addStretch()

        self.btn_clipboard = QPushButton("Clipboard")
        self.btn_clipboard.setStyleSheet(btn_style)
        self.btn_clipboard.clicked.connect(self._paste_clipboard)
        macro_row.addWidget(self.btn_clipboard)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setStyleSheet(btn_style)
        self.btn_clear.clicked.connect(lambda: self.editor.clear())
        macro_row.addWidget(self.btn_clear)

        layout.addLayout(macro_row)

        # -------------------------------------------------------------
        # Row 5: Content Text Area
        # -------------------------------------------------------------
        self.editor = QTextEdit()
        self.editor.setPlaceholderText("Snippet content / text or macros to type...")
        self.editor.setFixedHeight(120)
        font = QFont("Consolas, monospace")
        font.setStyleHint(QFont.Monospace)
        self.editor.setFont(font)
        self.editor.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 6px;
                color: #FFFFFF;
                font-size: 12px;
            }}
        """)
        layout.addWidget(self.editor)

        # -------------------------------------------------------------
        # Row 6: Save Snippet Button & Start Button
        # -------------------------------------------------------------
        action_row = QHBoxLayout()
        action_row.setSpacing(6)

        self.btn_save = QPushButton("Save Snippet")
        self.btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: #0078D7;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
                color: #FFFFFF;
            }}
            QPushButton:hover {{
                background-color: #1a88e0;
            }}
        """)
        self.btn_save.clicked.connect(self._save_current_snippet)
        action_row.addWidget(self.btn_save, 1)

        self.btn_start = QPushButton("Start Typing (3s)")
        self.btn_start.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.ACCENT_GREEN};
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 700;
                color: #FFFFFF;
            }}
            QPushButton:hover {{
                background-color: #149c53;
            }}
        """)
        self.btn_start.clicked.connect(self._start_typing)
        action_row.addWidget(self.btn_start, 1)

        layout.addLayout(action_row)

        # -------------------------------------------------------------
        # Row 7: Active Session Controls (Pause & STOP)
        # -------------------------------------------------------------
        self.session_controls = QWidget()
        session_row = QHBoxLayout(self.session_controls)
        session_row.setContentsMargins(0, 0, 0, 0)
        session_row.setSpacing(6)

        self.btn_pause = QPushButton("Pause")
        self.btn_pause.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 4px;
                padding: 5px;
                font-size: 11px;
                color: #FFFFFF;
            }}
        """)
        self.btn_pause.clicked.connect(self._toggle_pause)
        session_row.addWidget(self.btn_pause, 1)

        self.btn_stop = QPushButton("STOP")
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #C62828;
                border: none;
                border-radius: 4px;
                padding: 5px;
                font-size: 11px;
                font-weight: bold;
                color: #FFFFFF;
            }
            QPushButton:hover {
                background-color: #D32F2F;
            }
        """)
        self.btn_stop.clicked.connect(self._stop_typing)
        session_row.addWidget(self.btn_stop, 1)

        self.session_controls.setVisible(False)
        layout.addWidget(self.session_controls)

        # -------------------------------------------------------------
        # Row 8: Progress Bar & Detailed Status
        # -------------------------------------------------------------
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {Theme.BG_CARD};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {Theme.ACCENT_GREEN};
                border-radius: 2px;
            }}
        """)
        layout.addWidget(self.progress_bar)

        self.lbl_progress_desc = QLabel("Ready. Select or save a snippet, then click Start Typing.")
        self.lbl_progress_desc.setStyleSheet("font-size: 11px; color: #888888; background: transparent;")
        layout.addWidget(self.lbl_progress_desc)

    def _insert_macro(self, tag: str) -> None:
        cursor = self.editor.textCursor()
        cursor.insertText(tag)

    def _paste_clipboard(self) -> None:
        app = QGuiApplication.instance()
        if app:
            cb_text = app.clipboard().text()
            if cb_text:
                self.editor.insertPlainText(cb_text)

    def _load_snippets(self) -> None:
        if not self._storage_path.exists():
            default_snippet = Snippet(
                id="default_gg",
                name="GG Quick Chat",
                text="Good game everyone! Well played. {ENTER}",
                mode=TypingMode.HUMAN_LIKE.value,
                delay_per_char=15,
                delay_per_word=50,
            )
            self.snippets = [default_snippet]
            self._save_snippets_to_file()
        else:
            try:
                with open(self._storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.snippets = [Snippet.from_dict(d) for d in data]
            except Exception as ex:
                logger.error("Failed to load snippets: %s", ex)
                self.snippets = []

        self._refresh_combo()
        self._register_global_hotkeys()

    def _save_snippets_to_file(self) -> None:
        try:
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump([s.to_dict() for s in self.snippets], f, indent=2)
        except Exception as ex:
            logger.error("Failed to save snippets: %s", ex)
        self._register_global_hotkeys()

    def _register_global_hotkeys(self) -> None:
        """Register all snippets with assigned hotkeys in GlobalHotKeyService."""
        hotkey_svc = get_hotkey_service()
        hotkey_svc.unregister_all()

        for snippet in self.snippets:
            if not snippet.hotkey or snippet.hotkey.strip().lower() in ("none", ""):
                continue

            # Capture snippet in closure and safely emit Qt signal to GUI thread
            def make_trigger(s=snippet):
                logger.info(f"[AutoTyperWidget] Hotkey triggered for snippet '{s.name}'")
                self.trigger_hotkey_signal.emit(s)

            hotkey_svc.register(snippet.hotkey, make_trigger)

        if self.is_typing_active():
            hotkey_svc.register("esc", self._on_esc_hotkey_pressed)

    def _trigger_snippet_by_hotkey(self, snippet: Snippet) -> None:
        """Executed when global hotkey fires anywhere in Linux OS.
        If already typing this snippet, stops typing (toggle off).
        If idle, starts typing (toggle on).
        """
        if self._worker and self._worker.isRunning():
            # If same snippet (or any active session) is triggered again, stop it
            if self._active_running_snippet_id == snippet.id or self._active_running_snippet_id is not None:
                logger.info(f"[AutoTyperWidget] Stopping snippet '{snippet.name}' via hotkey toggle.")
                self._stop_typing()
                self.status_lbl.setText("Stopped")
                self.lbl_progress_desc.setText(f"Stopped typing '{snippet.name}' (hotkey toggled off).")
                return

        # Start typing this snippet
        self._active_running_snippet_id = snippet.id
        self.session_controls.setVisible(True)
        self.btn_pause.setText("Pause")
        self.progress_bar.setValue(0)
        self.status_lbl.setText("Typing")

        # Register global ESC key for pause/continue while typing
        hotkey_svc = get_hotkey_service()
        hotkey_svc.register("esc", self._on_esc_hotkey_pressed)

        self._worker = AutoTyperWorker(
            text=snippet.text,
            mode=snippet.mode,
            delay_char=snippet.delay_per_char,
            delay_word=snippet.delay_per_word,
            countdown=0,  # Hotkey triggers immediately
            parent=self,
        )
        self._worker.status_changed.connect(self.lbl_progress_desc.setText)
        self._worker.progress_updated.connect(self._on_progress)
        self._worker.finished_operation.connect(self._on_worker_finished)
        self._worker.start()

    def _refresh_combo(self, select_id: Optional[str] = None) -> None:
        self.combo_snippets.blockSignals(True)
        self.combo_snippets.clear()
        self.combo_snippets.addItem("[ + Custom / New ]", "")

        selected_idx = 0
        for idx, snip in enumerate(self.snippets):
            self.combo_snippets.addItem(snip.name, snip.id)
            if select_id and snip.id == select_id:
                selected_idx = idx + 1

        self.combo_snippets.setCurrentIndex(selected_idx)
        self.combo_snippets.blockSignals(False)
        self._on_snippet_selected(selected_idx)

    def _on_snippet_selected(self, index: int) -> None:
        if index <= 0 or index - 1 >= len(self.snippets):
            self.current_snippet = None
            self.input_name.setText("Custom Snippet")
            self.input_hotkey.clear()
            self.combo_mode.setCurrentText(TypingMode.HUMAN_LIKE.value)
            self.input_char_delay.setText("15")
            self.input_word_delay.setText("50")
            self.editor.clear()
        else:
            snip = self.snippets[index - 1]
            self.current_snippet = snip
            self.input_name.setText(snip.name)
            self.input_hotkey.setText(snip.hotkey)
            self.combo_mode.setCurrentText(snip.mode)
            self.input_char_delay.setText(str(snip.delay_per_char))
            self.input_word_delay.setText(str(snip.delay_per_word))
            self.editor.setPlainText(snip.text)

    def _create_new_snippet(self) -> None:
        import uuid
        new_snip = Snippet(
            id=str(uuid.uuid4())[:8],
            name="New Snippet",
            text="",
            mode=TypingMode.HUMAN_LIKE.value,
            delay_per_char=15,
            delay_per_word=50,
        )
        self.snippets.append(new_snip)
        self._save_snippets_to_file()
        self._refresh_combo(select_id=new_snip.id)

    def _delete_current_snippet(self) -> None:
        if not self.current_snippet:
            return
        self.snippets = [s for s in self.snippets if s.id != self.current_snippet.id]
        self._save_snippets_to_file()
        self._refresh_combo()

    def _save_current_snippet(self) -> None:
        import uuid
        name = self.input_name.text().strip() or "Untitled Snippet"
        text = self.editor.toPlainText()
        mode = self.combo_mode.currentText()
        hotkey = self.input_hotkey.text().strip()

        try:
            delay_char = int(self.input_char_delay.text())
        except ValueError:
            delay_char = 15
        try:
            delay_word = int(self.input_word_delay.text())
        except ValueError:
            delay_word = 50

        if not self.current_snippet:
            snip = Snippet(
                id=str(uuid.uuid4())[:8],
                name=name,
                text=text,
                mode=mode,
                delay_per_char=delay_char,
                delay_per_word=delay_word,
                hotkey=hotkey,
            )
            self.snippets.append(snip)
            self.current_snippet = snip
        else:
            self.current_snippet.name = name
            self.current_snippet.text = text
            self.current_snippet.mode = mode
            self.current_snippet.delay_per_char = delay_char
            self.current_snippet.delay_per_word = delay_word
            self.current_snippet.hotkey = hotkey

        self._save_snippets_to_file()
        self._refresh_combo(select_id=self.current_snippet.id)
        self.status_lbl.setText("Saved")

    def _start_typing(self) -> None:
        text = self.editor.toPlainText()
        if not text:
            self.lbl_progress_desc.setText("Cannot type empty snippet!")
            return

        mode = self.combo_mode.currentText()
        try:
            char_delay = int(self.input_char_delay.text())
        except ValueError:
            char_delay = 15
        try:
            word_delay = int(self.input_word_delay.text())
        except ValueError:
            word_delay = 50

        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait()

        self._active_running_snippet_id = self.current_snippet.id if self.current_snippet else "custom"
        self.session_controls.setVisible(True)
        self.btn_pause.setText("Pause")
        self.progress_bar.setValue(0)
        self.status_lbl.setText("Starting")

        # Register global ESC key for pause/continue while typing
        hotkey_svc = get_hotkey_service()
        hotkey_svc.register("esc", self._on_esc_hotkey_pressed)

        # 3 seconds countdown to give user time to focus target window or game
        self._worker = AutoTyperWorker(
            text=text,
            mode=mode,
            delay_char=char_delay,
            delay_word=word_delay,
            countdown=3,
            parent=self,
        )

        self._worker.status_changed.connect(self.lbl_progress_desc.setText)
        self._worker.progress_updated.connect(self._on_progress)
        self._worker.finished_operation.connect(self._on_worker_finished)
        self._worker.start()

    def _toggle_pause(self) -> bool:
        if self._worker and self._worker.isRunning():
            is_paused = self._worker.toggle_pause()
            self.btn_pause.setText("Resume" if is_paused else "Pause")
            if is_paused:
                self.status_lbl.setText("Paused")
                self.lbl_progress_desc.setText("Paused (Press Esc to continue typing)")
            else:
                self.status_lbl.setText("Typing")
                self.lbl_progress_desc.setText("Continuing typing...")
            return is_paused
        return False

    def _stop_typing(self) -> None:
        self._active_running_snippet_id = None
        hotkey_svc = get_hotkey_service()
        hotkey_svc.unregister("esc")

        if self._worker:
            self._worker.cancel()
            self._worker.wait(1000)
        self.session_controls.setVisible(False)
        self.status_lbl.setText("Stopped")
        self.lbl_progress_desc.setText("Typing cancelled.")

    def _on_progress(self, current: int, total: int) -> None:
        if total > 0:
            pct = int((current / total) * 100)
            self.progress_bar.setValue(pct)
            if self._worker and getattr(self._worker, "_is_paused", False):
                self.status_lbl.setText(f"{pct}% (Paused)")
            else:
                self.status_lbl.setText(f"{pct}%")

    def _on_worker_finished(self, success: bool, message: str) -> None:
        self._active_running_snippet_id = None
        hotkey_svc = get_hotkey_service()
        hotkey_svc.unregister("esc")

        self.session_controls.setVisible(False)
        self.status_lbl.setText("Ready")
        self.lbl_progress_desc.setText(message)

    def _on_esc_hotkey_pressed(self) -> None:
        """Callback from GlobalHotKeyService on evdev background thread."""
        logger.info("[AutoTyperWidget] Global Esc key pressed -> toggling pause/continue")
        self.esc_pressed_signal.emit()

    def _handle_esc_pressed(self) -> None:
        """Executed on Qt GUI thread when Esc is pressed."""
        if not self.is_typing_active():
            return
        self._toggle_pause()

    def is_typing_active(self) -> bool:
        """Return True if an auto-typing session is currently running or paused."""
        return bool(self._worker and self._worker.isRunning())

    def handle_esc_toggle(self) -> None:
        """Called when Esc is pressed within the UI overlay."""
        self._handle_esc_pressed()
