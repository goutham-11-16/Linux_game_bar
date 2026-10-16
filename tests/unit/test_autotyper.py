"""Unit tests for AutoTyper core engine, snippet persistence, and widget."""

import os
import pytest
from PySide6.QtWidgets import QApplication

from linux_game_bar.core.autotyper_engine import (
    TokenParser,
    TokenType,
    Snippet,
    TypingMode,
    AutoTyperWorker,
)
from linux_game_bar.widgets.autotyper import AutoTyperWidget


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def test_token_parser_tags():
    raw = "Hello{ENTER}World{TAB}{DELAY 250}{BS}"
    tokens = TokenParser.parse(raw)
    assert len(tokens) == 6
    assert tokens[0].token_type == TokenType.TEXT
    assert tokens[0].text_value == "Hello"
    assert tokens[1].token_type == TokenType.KEY_PRESS
    assert tokens[1].key_name == "28"  # Enter
    assert tokens[2].token_type == TokenType.TEXT
    assert tokens[2].text_value == "World"
    assert tokens[3].token_type == TokenType.KEY_PRESS
    assert tokens[3].key_name == "15"  # Tab
    assert tokens[4].token_type == TokenType.DELAY
    assert tokens[4].delay_ms == 250
    assert tokens[5].token_type == TokenType.KEY_PRESS
    assert tokens[5].key_name == "14"  # Backspace


def test_snippet_serialization():
    snip = Snippet(
        id="s1",
        name="Test Snippet",
        text="Quick test {ENTER}",
        mode=TypingMode.MACRO.value,
        delay_per_char=20,
        delay_per_word=60,
        hotkey="F8",
    )
    data = snip.to_dict()
    restored = Snippet.from_dict(data)
    assert restored.id == "s1"
    assert restored.name == "Test Snippet"
    assert restored.text == "Quick test {ENTER}"
    assert restored.mode == TypingMode.MACRO.value
    assert restored.delay_per_char == 20
    assert restored.delay_per_word == 60
    assert restored.hotkey == "F8"


def test_autotyper_worker_lifecycle(qapp):
    worker = AutoTyperWorker(
        text="Testing",
        mode=TypingMode.FAST.value,
        delay_char=1,
        delay_word=1,
        countdown=0,
    )
    # Pause & Resume test
    assert not worker._is_paused
    worker.pause()
    assert worker._is_paused
    worker.resume()
    assert not worker._is_paused
    # Cancel test
    assert not worker._is_cancelled
    worker.cancel()
    assert worker._is_cancelled


def test_autotyper_widget_ui(qapp, tmp_path):
    widget = AutoTyperWidget(config_manager=None)
    widget._storage_path = tmp_path / "autotyper_snippets.json"
    widget._create_new_snippet()

    assert len(widget.snippets) >= 1
    widget.input_name.setText("Gaming GG")
    widget.editor.setPlainText("Well played!")
    widget._save_current_snippet()

    assert widget.current_snippet is not None
    assert widget.current_snippet.name == "Gaming GG"
    assert widget.current_snippet.text == "Well played!"

def test_hotkey_capture_box(qapp):
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import Qt
    from linux_game_bar.widgets.hotkey_capture import HotKeyCaptureBox

    box = HotKeyCaptureBox()
    # Press F8
    ev_f8 = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_F8, Qt.NoModifier)
    box.keyPressEvent(ev_f8)
    assert box.text() == "F8"

    # Press Ctrl + Alt + T
    ev_combo = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_T, Qt.ControlModifier | Qt.AltModifier)
    box.keyPressEvent(ev_combo)
    assert "Control" in box.text()
    assert "Alt" in box.text()
    assert "T" in box.text()

    # Clear with Backspace
    ev_bs = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Backspace, Qt.NoModifier)
    box.keyPressEvent(ev_bs)
    assert box.text() == "None"


def test_hotkey_service_normalization():
    from linux_game_bar.core.hotkey_service import GlobalHotKeyService

    assert GlobalHotKeyService.normalize_hotkey("F8") == "f8"
    assert GlobalHotKeyService.normalize_hotkey("Control, Shift + F8") == "ctrl+shift+f8"
    assert GlobalHotKeyService.normalize_hotkey("Windows, Alt + D1") == "alt+super+1"
