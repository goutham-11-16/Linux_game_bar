"""Game timer widget using monotonic time tracking."""

import time
import logging
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QFrame,
)

from linux_game_bar.ui.widget_base import WidgetBase
from linux_game_bar.ui.theme import Theme

logger = logging.getLogger("linux_game_bar.timer")


class TimerWidget(WidgetBase):
    """Accurate monotonic countdown game timer."""

    def __init__(self, parent: QWidget = None):
        super().__init__("timer", "TIMER", "timer", parent)
        self.setMinimumSize(300, 320)
        self.resize(320, 340)

        self._total_duration_secs: float = 25 * 60  # Default 25 min Pomodoro
        self._remaining_secs: float = self._total_duration_secs
        self._target_monotonic: float = 0.0
        self._is_running: bool = False
        self._is_paused: bool = False

        self._build_ui()

        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self._on_tick)

    def _build_ui(self) -> None:
        card_timer = QFrame()
        card_timer.setStyleSheet(f"background-color: {Theme.BG_CARD}; border-radius: 8px; padding: 12px;")
        vbox = QVBoxLayout(card_timer)
        vbox.setSpacing(10)

        # Big Countdown Display
        self.lbl_digits = QLabel("25:00")
        self.lbl_digits.setAlignment(Qt.AlignCenter)
        self.lbl_digits.setStyleSheet(f"""
            font-size: 42px;
            font-weight: 800;
            color: #ffffff;
            font-family: 'Monospace', 'Courier New', monospace;
            padding: 8px 0;
        """)
        vbox.addWidget(self.lbl_digits)

        # Controls Row (Start/Pause, Reset)
        btn_row = QHBoxLayout()
        self.btn_start_pause = QPushButton("Start")
        self.btn_start_pause.setProperty("class", "accent")
        self.btn_start_pause.setCursor(Qt.PointingHandCursor)
        self.btn_start_pause.clicked.connect(self._toggle_start_pause)
        btn_row.addWidget(self.btn_start_pause)

        self.btn_reset = QPushButton("Reset")
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.clicked.connect(self._reset_timer)
        btn_row.addWidget(self.btn_reset)
        vbox.addLayout(btn_row)

        self.content_layout.addWidget(card_timer)

        # Presets Card
        card_presets = QFrame()
        card_presets.setStyleSheet(f"background-color: {Theme.BG_CARD}; border-radius: 8px; padding: 10px;")
        vbox_pre = QVBoxLayout(card_presets)
        vbox_pre.setSpacing(6)

        lbl_pre = QLabel("Presets:")
        lbl_pre.setStyleSheet("font-size: 11px; font-weight: 600; color: #A0A0A5;")
        vbox_pre.addWidget(lbl_pre)

        grid = QHBoxLayout()
        presets = [("5m", 5), ("10m", 10), ("15m", 15), ("25m", 25), ("45m", 45)]
        for label, minutes in presets:
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, m=minutes: self._set_preset(m))
            grid.addWidget(btn)
        vbox_pre.addLayout(grid)

        # Custom Minutes Input
        row_custom = QHBoxLayout()
        lbl_custom = QLabel("Custom minutes:")
        lbl_custom.setStyleSheet("font-size: 11px; color: #A0A0A5;")
        row_custom.addWidget(lbl_custom)

        self.spin_mins = QSpinBox()
        self.spin_mins.setRange(1, 300)
        self.spin_mins.setValue(25)
        self.spin_mins.setStyleSheet(f"""
            QSpinBox {{
                background-color: {Theme.BG_INPUT};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 4px;
                padding: 2px 6px;
                color: #ffffff;
            }}
        """)
        self.spin_mins.valueChanged.connect(lambda v: self._set_preset(v))
        row_custom.addWidget(self.spin_mins)
        vbox_pre.addLayout(row_custom)

        self.content_layout.addWidget(card_presets)

    def _format_time(self, seconds: float) -> str:
        s = max(0, int(seconds))
        mins = s // 60
        secs = s % 60
        return f"{mins:02d}:{secs:02d}"

    def _set_preset(self, minutes: int) -> None:
        self._reset_timer()
        self._total_duration_secs = minutes * 60
        self._remaining_secs = self._total_duration_secs
        self.lbl_digits.setText(self._format_time(self._remaining_secs))
        self.lbl_digits.setStyleSheet(f"""
            font-size: 42px; font-weight: 800; color: #ffffff;
            font-family: 'Monospace', 'Courier New', monospace; padding: 8px 0;
        """)

    def _toggle_start_pause(self) -> None:
        if not self._is_running:
            # Start
            self._is_running = True
            self._is_paused = False
            self._target_monotonic = time.monotonic() + self._remaining_secs
            self.tick_timer.start(200)
            self.btn_start_pause.setText("Pause")
            self.btn_start_pause.setStyleSheet(f"background-color: {Theme.COLOR_WARNING}; color: white; font-weight: 600;")
        elif not self._is_paused:
            # Pause
            self._is_paused = True
            self._remaining_secs = max(0.0, self._target_monotonic - time.monotonic())
            self.tick_timer.stop()
            self.btn_start_pause.setText("Resume")
            self.btn_start_pause.setStyleSheet(f"background-color: {Theme.ACCENT_GREEN}; color: white; font-weight: 600;")
        else:
            # Resume
            self._is_paused = False
            self._target_monotonic = time.monotonic() + self._remaining_secs
            self.tick_timer.start(200)
            self.btn_start_pause.setText("Pause")
            self.btn_start_pause.setStyleSheet(f"background-color: {Theme.COLOR_WARNING}; color: white; font-weight: 600;")

    def _reset_timer(self) -> None:
        self._is_running = False
        self._is_paused = False
        self.tick_timer.stop()
        self._remaining_secs = self._total_duration_secs
        self.lbl_digits.setText(self._format_time(self._remaining_secs))
        self.lbl_digits.setStyleSheet(f"""
            font-size: 42px; font-weight: 800; color: #ffffff;
            font-family: 'Monospace', 'Courier New', monospace; padding: 8px 0;
        """)
        self.btn_start_pause.setText("Start")
        self.btn_start_pause.setStyleSheet("")

    def _on_tick(self) -> None:
        now = time.monotonic()
        remaining = self._target_monotonic - now
        if remaining <= 0:
            self._remaining_secs = 0.0
            self.lbl_digits.setText("00:00")
            self.lbl_digits.setStyleSheet(f"""
                font-size: 42px; font-weight: 800; color: {Theme.COLOR_DANGER};
                font-family: 'Monospace', 'Courier New', monospace; padding: 8px 0;
            """)
            self.tick_timer.stop()
            self._is_running = False
            self.btn_start_pause.setText("Start")
            self.btn_start_pause.setStyleSheet("")
            # Play bell sound
            self._notify_done()
        else:
            self._remaining_secs = remaining
            self.lbl_digits.setText(self._format_time(remaining))

    def _notify_done(self) -> None:
        logger.info("Timer countdown finished!")
        try:
            # Terminal bell / system bell
            print("\a", flush=True)
        except Exception:
            pass
