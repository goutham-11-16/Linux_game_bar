"""
Core AutoTyper Engine for Linux Game Bar.
Translates Auto-Typer-Game-Bar keystrokes and macros into Linux input actions using ydotool and Qt.
"""

import os
import re
import time
import random
import logging
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from PySide6.QtCore import QObject, Signal, QThread
from PySide6.QtGui import QGuiApplication

logger = logging.getLogger("linux_game_bar.autotyper")


class TypingMode(str, Enum):
    HUMAN_LIKE = "HumanLike"
    PASTE = "Paste"
    FAST = "Fast"
    MACRO = "Macro"


class TokenType(Enum):
    TEXT = 1
    KEY_PRESS = 2
    DELAY = 3


@dataclass
class TypingToken:
    token_type: TokenType
    text_value: str = ""
    key_name: str = ""
    delay_ms: int = 0


@dataclass
class Snippet:
    id: str
    name: str = "New Snippet"
    text: str = ""
    mode: str = TypingMode.HUMAN_LIKE.value
    delay_per_char: int = 15
    delay_per_word: int = 50
    hotkey: str = ""
    is_enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "text": self.text,
            "mode": self.mode,
            "delay_per_char": self.delay_per_char,
            "delay_per_word": self.delay_per_word,
            "hotkey": self.hotkey,
            "is_enabled": self.is_enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Snippet":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", "New Snippet"),
            text=data.get("text", ""),
            mode=data.get("mode", TypingMode.HUMAN_LIKE.value),
            delay_per_char=int(data.get("delay_per_char", 15)),
            delay_per_word=int(data.get("delay_per_word", 50)),
            hotkey=data.get("hotkey", ""),
            is_enabled=bool(data.get("is_enabled", True)),
        )


class TokenParser:
    """Parses macro syntax like {ENTER}, {TAB}, {DELAY 500}, {BACKSPACE} matching the C# TokenParserService."""

    TAG_KEY_MAP = {
        "ENTER": "28",        # KEY_ENTER in Linux input event codes
        "RETURN": "28",
        "TAB": "15",          # KEY_TAB
        "BS": "14",           # KEY_BACKSPACE
        "BACKSPACE": "14",
        "ESC": "1",           # KEY_ESC
        "ESCAPE": "1",
        "SPACE": "57",        # KEY_SPACE
    }

    @classmethod
    def parse(cls, input_text: str) -> List[TypingToken]:
        tokens: List[TypingToken] = []
        if not input_text:
            return tokens

        parts = re.split(r"(\{[^}]+\})", input_text)
        for part in parts:
            if not part:
                continue

            if part.startswith("{") and part.endswith("}"):
                content = part[1:-1].strip().upper()
                if content.startswith("DELAY "):
                    try:
                        ms = int(content[6:].strip())
                        tokens.append(TypingToken(token_type=TokenType.DELAY, delay_ms=ms))
                        continue
                    except ValueError:
                        pass

                if content in cls.TAG_KEY_MAP:
                    tokens.append(
                        TypingToken(
                            token_type=TokenType.KEY_PRESS,
                            key_name=cls.TAG_KEY_MAP[content],
                        )
                    )
                else:
                    tokens.append(TypingToken(token_type=TokenType.TEXT, text_value=part))
            else:
                tokens.append(TypingToken(token_type=TokenType.TEXT, text_value=part))

        return tokens


class AutoTyperWorker(QThread):
    """Background execution worker for typing operations without freezing the overlay UI."""

    progress_updated = Signal(int, int)    # current, total
    status_changed = Signal(str)           # status text
    state_changed = Signal(str)            # "Ready", "Countdown", "Typing", "Paused", "Stopped"
    finished_operation = Signal(bool, str) # success, message

    def __init__(
        self,
        text: str,
        mode: str = TypingMode.HUMAN_LIKE.value,
        delay_char: int = 15,
        delay_word: int = 50,
        countdown: int = 0,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.text = text
        self.mode = mode
        self.delay_char = max(1, delay_char)
        self.delay_word = max(1, delay_word)
        self.countdown = countdown

        self._is_paused = False
        self._is_cancelled = False
        self._socket_path = os.environ.get("YDOTOOL_SOCKET", "/tmp/.ydotool_socket")

    def pause(self) -> None:
        self._is_paused = True
        self.state_changed.emit("Paused")
        self.status_changed.emit("Paused")

    def resume(self) -> None:
        self._is_paused = False
        self.state_changed.emit("Typing")
        self.status_changed.emit("Resumed typing...")

    def toggle_pause(self) -> bool:
        if self._is_paused:
            self.resume()
            return False
        else:
            self.pause()
            return True

    def cancel(self) -> None:
        self._is_cancelled = True
        self.state_changed.emit("Stopped")
        self.status_changed.emit("Typing stopped.")

    def run(self) -> None:
        try:
            total_len = len(self.text)
            if total_len == 0:
                self.finished_operation.emit(True, "Empty text.")
                return

            # 1. Countdown Phase
            if self.countdown > 0:
                self.state_changed.emit("Countdown")
                for sec in range(self.countdown, 0, -1):
                    if self._is_cancelled:
                        self.finished_operation.emit(False, "Cancelled during countdown.")
                        return
                    self.status_changed.emit(f"Starting in {sec}s... focus target window!")
                    self.msleep(1000)

            if self._is_cancelled:
                self.finished_operation.emit(False, "Cancelled.")
                return

            self.state_changed.emit("Typing")
            self.status_changed.emit("Typing in progress...")

            # 2. Execution Phase
            if self.mode == TypingMode.PASTE.value:
                self._execute_paste()
            elif self.mode == TypingMode.FAST.value:
                self._execute_fast(total_len)
            elif self.mode == TypingMode.MACRO.value:
                self._execute_macro(total_len)
            else:  # Default: HumanLike
                self._execute_human_like(total_len)

            if self._is_cancelled:
                self.state_changed.emit("Stopped")
                self.finished_operation.emit(False, "Typing stopped.")
            else:
                self.progress_updated.emit(total_len, total_len)
                self.state_changed.emit("Ready")
                self.finished_operation.emit(True, "Typing completed successfully!")

        except Exception as ex:
            logger.exception("Error during AutoTyper execution: %s", ex)
            self.state_changed.emit("Error")
            self.finished_operation.emit(False, f"Error: {str(ex)}")

    def _wait_if_paused(self) -> bool:
        while self._is_paused and not self._is_cancelled:
            self.msleep(100)
        return not self._is_cancelled

    def _send_ydotool_type(self, chunk: str) -> None:
        env = dict(os.environ)
        if os.path.exists(self._socket_path):
            env["YDOTOOL_SOCKET"] = self._socket_path
        subprocess.run(
            ["ydotool", "type", "--", chunk],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    def _send_ydotool_key(self, key_code: str) -> None:
        env = dict(os.environ)
        if os.path.exists(self._socket_path):
            env["YDOTOOL_SOCKET"] = self._socket_path
        subprocess.run(
            ["ydotool", "key", f"{key_code}:1", f"{key_code}:0"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    def _execute_paste(self) -> None:
        app = QGuiApplication.instance()
        if app:
            clipboard = app.clipboard()
            clipboard.setText(self.text)
        self.msleep(150)
        # Ctrl+V via ydotool
        env = dict(os.environ)
        if os.path.exists(self._socket_path):
            env["YDOTOOL_SOCKET"] = self._socket_path
        subprocess.run(
            ["ydotool", "key", "29:1", "47:1", "47:0", "29:0"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    def _execute_fast(self, total_len: int) -> None:
        for idx, char in enumerate(self.text):
            if not self._wait_if_paused():
                return

            if char == "\n":
                self._send_ydotool_key("28")
                self.msleep(max(self.delay_word, 20))
            elif char == "\t":
                self._send_ydotool_key("15")
                self.msleep(max(self.delay_char, 15))
            else:
                self._send_ydotool_type(char)
                if char == " ":
                    self.msleep(self.delay_word)
                else:
                    self.msleep(self.delay_char)

            if idx % 5 == 0 or idx == total_len - 1:
                self.progress_updated.emit(idx + 1, total_len)

    def _execute_human_like(self, total_len: int) -> None:
        for idx, char in enumerate(self.text):
            if not self._wait_if_paused():
                return

            if char == "\n":
                self._send_ydotool_key("28")
                enter_delay = self.delay_word if self.delay_word > 0 else random.randint(120, 240)
                self.msleep(enter_delay)
            elif char == "\t":
                self._send_ydotool_key("15")
                self.msleep(random.randint(40, 90))
            else:
                self._send_ydotool_type(char)
                if char == " ":
                    space_delay = self.delay_word if self.delay_word > 0 else random.randint(35, 90)
                    self.msleep(space_delay)
                else:
                    char_jitter = max(2, self.delay_char + random.randint(-5, 15))
                    self.msleep(char_jitter)

            if idx % 5 == 0 or idx == total_len - 1:
                self.progress_updated.emit(idx + 1, total_len)

    def _execute_macro(self, total_len: int) -> None:
        tokens = TokenParser.parse(self.text)
        processed = 0

        for token in tokens:
            if not self._wait_if_paused():
                return

            if token.token_type == TokenType.TEXT:
                for c in token.text_value:
                    if not self._wait_if_paused():
                        return
                    if c == "\n":
                        self._send_ydotool_key("28")
                        self.msleep(max(self.delay_word, 20))
                    elif c == "\t":
                        self._send_ydotool_key("15")
                        self.msleep(max(self.delay_char, 15))
                    else:
                        self._send_ydotool_type(c)
                        self.msleep(self.delay_char)

                    processed += 1
                    self.progress_updated.emit(min(processed, total_len), total_len)

            elif token.token_type == TokenType.KEY_PRESS:
                self._send_ydotool_key(token.key_name)
                self.msleep(30)
                processed += 1
                self.progress_updated.emit(min(processed, total_len), total_len)

            elif token.token_type == TokenType.DELAY:
                self.msleep(max(10, token.delay_ms))
