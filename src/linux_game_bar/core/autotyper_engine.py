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

            # Wait for physical modifiers (e.g. Ctrl, Shift) to release from hotkey press
            try:
                from linux_game_bar.core.hotkey_service import get_hotkey_service
                hotkey_svc = get_hotkey_service()
                hotkey_svc.wait_for_modifiers_released(timeout_sec=1.2)
                hotkey_svc.release_modifiers()
            except Exception as ex:
                logger.warning(f"Failed releasing modifiers: {ex}")
            self.msleep(100)

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

    def _send_ydotool_type(self, chunk: str, delay_char: int = 15) -> None:
        if not chunk:
            return
        env = dict(os.environ)
        if os.path.exists(self._socket_path):
            env["YDOTOOL_SOCKET"] = self._socket_path
        cmd = ["ydotool", "type"]
        if delay_char > 0:
            cmd.extend(["-d", str(delay_char), "-H", "10"])
        cmd.extend(["--", chunk])
        subprocess.run(
            cmd,
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
        tokens = TokenParser.parse(self.text)
        processed = 0

        for token in tokens:
            if not self._wait_if_paused():
                return

            if token.token_type == TokenType.TEXT:
                parts = re.findall(r"\S+|\s+", token.text_value)
                for part in parts:
                    if not self._wait_if_paused():
                        return
                    if "\n" in part:
                        for c in part:
                            if c == "\n":
                                self._send_ydotool_key("28")
                                self.msleep(max(self.delay_word, 20))
                            elif c == "\t":
                                self._send_ydotool_key("15")
                                self.msleep(max(self.delay_char, 15))
                            else:
                                self._send_ydotool_type(c, delay_char=max(1, self.delay_char))
                            processed += 1
                    else:
                        self._send_ydotool_type(part, delay_char=max(1, self.delay_char))
                        if part.isspace() and self.delay_word > 0:
                            self.msleep(self.delay_word)
                        processed += len(part)

                    self.progress_updated.emit(min(processed, total_len), total_len)

            elif token.token_type == TokenType.KEY_PRESS:
                self._send_ydotool_key(token.key_name)
                self.msleep(20)
                processed += 1
                self.progress_updated.emit(min(processed, total_len), total_len)

            elif token.token_type == TokenType.DELAY:
                self.msleep(max(10, token.delay_ms))

    def _execute_human_like(self, total_len: int) -> None:
        tokens = TokenParser.parse(self.text)
        processed = 0

        for token in tokens:
            if not self._wait_if_paused():
                return

            if token.token_type == TokenType.TEXT:
                parts = re.findall(r"\S+|\s+", token.text_value)
                for part in parts:
                    if not self._wait_if_paused():
                        return

                    if "\n" in part:
                        for c in part:
                            if c == "\n":
                                self._send_ydotool_key("28")
                                self.msleep(self.delay_word if self.delay_word > 0 else random.randint(120, 220))
                            elif c == "\t":
                                self._send_ydotool_key("15")
                                self.msleep(random.randint(40, 80))
                            else:
                                self._send_ydotool_type(c, delay_char=self.delay_char)
                            processed += 1
                    elif part.isspace():
                        self._send_ydotool_type(part, delay_char=self.delay_char)
                        space_delay = self.delay_word if self.delay_word > 0 else random.randint(30, 80)
                        self.msleep(space_delay)
                        processed += len(part)
                    else:
                        jitter = max(2, self.delay_char + random.randint(-4, 10))
                        self._send_ydotool_type(part, delay_char=jitter)
                        processed += len(part)

                    self.progress_updated.emit(min(processed, total_len), total_len)

            elif token.token_type == TokenType.KEY_PRESS:
                self._send_ydotool_key(token.key_name)
                self.msleep(40)
                processed += 1
                self.progress_updated.emit(min(processed, total_len), total_len)

            elif token.token_type == TokenType.DELAY:
                self.msleep(max(10, token.delay_ms))

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
                        self._send_ydotool_type(c, delay_char=self.delay_char)
                    processed += 1
                    self.progress_updated.emit(min(processed, total_len), total_len)

            elif token.token_type == TokenType.KEY_PRESS:
                self._send_ydotool_key(token.key_name)
                self.msleep(30)
                processed += 1
                self.progress_updated.emit(min(processed, total_len), total_len)

            elif token.token_type == TokenType.DELAY:
                self.msleep(max(10, token.delay_ms))
