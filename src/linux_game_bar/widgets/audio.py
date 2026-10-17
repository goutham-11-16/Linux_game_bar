"""Audio mixer widget controlling PipeWire/WirePlumber and PulseAudio."""

import re
import shutil
import logging
import subprocess
from dataclasses import dataclass
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QPushButton,
    QComboBox,
    QScrollArea,
    QFrame,
    QTabWidget,
)

from linux_game_bar.ui.widget_base import WidgetBase
from linux_game_bar.ui.theme import Theme
from linux_game_bar.ui import icons

logger = logging.getLogger("linux_game_bar.audio")


@dataclass
class AudioEndpoint:
    id: str
    name: str
    volume: float = 1.0
    is_muted: bool = False
    is_default: bool = False


@dataclass
class AudioStream:
    id: str
    name: str
    app_name: str
    volume: float = 1.0
    is_muted: bool = False


class AudioBackend:
    """Interface to wpctl / pactl."""

    def __init__(self):
        self.has_wpctl = shutil.which("wpctl") is not None
        self.has_pactl = shutil.which("pactl") is not None

    def get_volume(self, target: str = "@DEFAULT_AUDIO_SINK@") -> tuple[float, bool]:
        """Return (volume_float 0.0-1.0, is_muted)."""
        if self.has_wpctl:
            try:
                res = subprocess.run(["wpctl", "get-volume", target], stdout=subprocess.PIPE, text=True, timeout=2)
                if res.returncode == 0:
                    text = res.stdout.strip()
                    match = re.search(r"Volume:\s+([0-9.]+)", text)
                    vol = float(match.group(1)) if match else 1.0
                    muted = "[MUTED]" in text
                    return vol, muted
            except Exception as e:
                logger.debug(f"wpctl get-volume error: {e}")
        return 1.0, False

    def set_volume(self, target: str, volume: float) -> bool:
        """Set volume (0.0 to 1.5)."""
        clamped = max(0.0, min(1.5, volume))
        if self.has_wpctl:
            try:
                subprocess.run(["wpctl", "set-volume", target, f"{clamped:.2f}"], timeout=2)
                return True
            except Exception as e:
                logger.error(f"wpctl set-volume error: {e}")
        return False

    def set_mute(self, target: str, mute: Optional[bool] = None) -> bool:
        """Set or toggle mute."""
        if self.has_wpctl:
            arg = "toggle" if mute is None else ("1" if mute else "0")
            try:
                subprocess.run(["wpctl", "set-mute", target, arg], timeout=2)
                return True
            except Exception as e:
                logger.error(f"wpctl set-mute error: {e}")
        return False

    def get_endpoints(self) -> tuple[List[AudioEndpoint], List[AudioEndpoint]]:
        """Parse sinks and sources from wpctl status."""
        sinks: List[AudioEndpoint] = []
        sources: List[AudioEndpoint] = []

        if not self.has_wpctl:
            return sinks, sources

        try:
            res = subprocess.run(["wpctl", "status"], stdout=subprocess.PIPE, text=True, timeout=2)
            if res.returncode != 0:
                return sinks, sources

            lines = res.stdout.splitlines()
            current_section = None

            for line in lines:
                stripped = line.strip()
                if "Sinks:" in stripped:
                    current_section = "sinks"
                    continue
                elif "Sources:" in stripped:
                    current_section = "sources"
                    continue
                elif "Filters:" in stripped or "Streams:" in stripped:
                    current_section = None
                    continue

                if current_section in ("sinks", "sources"):
                    # Example: "│  *   48. Built-in Audio Analog Stereo        [vol: 0.96]"
                    # Or:      "│      49. HDMI / DisplayPort                  [vol: 1.00]"
                    m = re.search(r"(\*?)\s+(\d+)\.\s+(.*?)(?:\s+\[vol:\s+([0-9.]+)\])?$", stripped)
                    if m:
                        is_default = m.group(1) == "*"
                        node_id = m.group(2)
                        name = m.group(3).strip()
                        vol = float(m.group(4)) if m.group(4) else 1.0

                        ep = AudioEndpoint(id=node_id, name=name, volume=vol, is_default=is_default)
                        if current_section == "sinks":
                            sinks.append(ep)
                        else:
                            sources.append(ep)

            # If PipeWire configured default sink via a filter or virtual node,
            # ensure at least one active hardware sink is designated as default
            if sinks and not any(s.is_default for s in sinks):
                sinks[0].is_default = True
            if sources and not any(s.is_default for s in sources):
                sources[0].is_default = True
        except Exception as e:
            logger.error(f"Error parsing wpctl status: {e}")

        return sinks, sources

    def set_default(self, node_id: str) -> bool:
        if self.has_wpctl:
            try:
                subprocess.run(["wpctl", "set-default", str(node_id)], timeout=2)
                return True
            except Exception as e:
                logger.error(f"wpctl set-default error: {e}")
        return False


class AudioWidget(WidgetBase):
    """Audio mixer widget with Windows 11 Xbox Game Bar [MIX] and [VOICE] tabs."""

    def __init__(self, parent: QWidget = None):
        super().__init__("audio", "AUDIO", "audio", parent)
        self.setMinimumSize(320, 360)
        self.resize(340, 390)

        self.backend = AudioBackend()
        self._updating = False

        self._build_ui()
        self._sync_state()

        # Periodic refresh
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._sync_state)
        self.timer.start(2000)

    def _build_ui(self) -> None:
        # Tabs matching Windows 11 Xbox Game Bar: [MIX] and [VOICE]
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: transparent;
            }
        """)

        # Tab 1: MIX (Output devices & app volume)
        tab_mix = QWidget()
        vbox_mix = QVBoxLayout(tab_mix)
        vbox_mix.setContentsMargins(4, 8, 4, 4)
        vbox_mix.setSpacing(10)

        # Output Card
        card_out = QFrame()
        card_out.setStyleSheet(f"background-color: {Theme.BG_CARD}; border-radius: 8px; border: 1px solid {Theme.BORDER_SUBTLE};")
        vbox_card_out = QVBoxLayout(card_out)
        vbox_card_out.setContentsMargins(10, 10, 10, 10)
        vbox_card_out.setSpacing(8)

        # Header with Output device selector
        lbl_out_title = QLabel("OUTPUT DEVICE")
        lbl_out_title.setStyleSheet("font-size: 10px; font-weight: 700; letter-spacing: 0.6px; color: #8E8E93;")
        vbox_card_out.addWidget(lbl_out_title)

        self.combo_sinks = QComboBox()
        self.combo_sinks.currentIndexChanged.connect(self._on_sink_changed)
        vbox_card_out.addWidget(self.combo_sinks)

        # Master Slider & Mute
        lbl_sys = QLabel("System Sounds")
        lbl_sys.setStyleSheet("font-size: 12px; font-weight: 500; color: #FFFFFF;")
        vbox_card_out.addWidget(lbl_sys)

        row_out = QHBoxLayout()
        row_out.setSpacing(8)

        self.btn_mute_out = QPushButton()
        self.btn_mute_out.setFixedSize(30, 30)
        self.btn_mute_out.setIconSize(QSize(16, 16))
        self.btn_mute_out.setIcon(icons.get_icon("speaker", color="#FFFFFF", size=16))
        self.btn_mute_out.setCursor(Qt.PointingHandCursor)
        self.btn_mute_out.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
        """)
        self.btn_mute_out.clicked.connect(self._on_toggle_mute_out)
        row_out.addWidget(self.btn_mute_out)

        self.slider_out = QSlider(Qt.Horizontal)
        self.slider_out.setRange(0, 100)
        self.slider_out.valueChanged.connect(self._on_out_slider_changed)
        row_out.addWidget(self.slider_out, 1)

        self.lbl_out_pct = QLabel("100")
        self.lbl_out_pct.setFixedWidth(28)
        self.lbl_out_pct.setStyleSheet("font-size: 12px; font-weight: 600; color: #CCCCCC;")
        row_out.addWidget(self.lbl_out_pct)

        vbox_card_out.addLayout(row_out)
        vbox_mix.addWidget(card_out)
        vbox_mix.addStretch()
        self.tabs.addTab(tab_mix, "MIX")

        # Tab 2: VOICE (Microphone Input)
        tab_voice = QWidget()
        vbox_voice = QVBoxLayout(tab_voice)
        vbox_voice.setContentsMargins(4, 8, 4, 4)
        vbox_voice.setSpacing(10)

        card_in = QFrame()
        card_in.setStyleSheet(f"background-color: {Theme.BG_CARD}; border-radius: 8px; border: 1px solid {Theme.BORDER_SUBTLE};")
        vbox_card_in = QVBoxLayout(card_in)
        vbox_card_in.setContentsMargins(10, 10, 10, 10)
        vbox_card_in.setSpacing(8)

        lbl_in_title = QLabel("INPUT DEVICE")
        lbl_in_title.setStyleSheet("font-size: 10px; font-weight: 700; letter-spacing: 0.6px; color: #8E8E93;")
        vbox_card_in.addWidget(lbl_in_title)

        self.combo_sources = QComboBox()
        self.combo_sources.currentIndexChanged.connect(self._on_source_changed)
        vbox_card_in.addWidget(self.combo_sources)

        lbl_mic = QLabel("Microphone")
        lbl_mic.setStyleSheet("font-size: 12px; font-weight: 500; color: #FFFFFF;")
        vbox_card_in.addWidget(lbl_mic)

        row_in = QHBoxLayout()
        row_in.setSpacing(8)

        self.btn_mute_in = QPushButton()
        self.btn_mute_in.setFixedSize(30, 30)
        self.btn_mute_in.setIconSize(QSize(16, 16))
        self.btn_mute_in.setIcon(icons.get_icon("mic", color="#FFFFFF", size=16))
        self.btn_mute_in.setCursor(Qt.PointingHandCursor)
        self.btn_mute_in.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
        """)
        self.btn_mute_in.clicked.connect(self._on_toggle_mute_in)
        row_in.addWidget(self.btn_mute_in)

        self.slider_in = QSlider(Qt.Horizontal)
        self.slider_in.setRange(0, 100)
        self.slider_in.valueChanged.connect(self._on_in_slider_changed)
        row_in.addWidget(self.slider_in, 1)

        self.lbl_in_pct = QLabel("50")
        self.lbl_in_pct.setFixedWidth(28)
        self.lbl_in_pct.setStyleSheet("font-size: 12px; font-weight: 600; color: #CCCCCC;")
        row_in.addWidget(self.lbl_in_pct)

        vbox_card_in.addLayout(row_in)
        vbox_voice.addWidget(card_in)
        vbox_voice.addStretch()
        self.tabs.addTab(tab_voice, "VOICE")

        self.content_layout.addWidget(self.tabs)

        # Subtle backend footer
        lbl_backend = QLabel("PipeWire / WirePlumber")
        lbl_backend.setStyleSheet("font-size: 10px; color: #6E6E73; padding-left: 4px;")
        self.content_layout.addWidget(lbl_backend)

    def _sync_state(self) -> None:
        """Read state from backend without triggering loop callbacks."""
        self._updating = True
        try:
            # 1. Output volume
            out_vol, out_muted = self.backend.get_volume("@DEFAULT_AUDIO_SINK@")
            pct_out = int(round(out_vol * 100))
            self.slider_out.setValue(pct_out)
            self.lbl_out_pct.setText(str(pct_out))
            if out_muted:
                self.btn_mute_out.setIcon(icons.get_icon("speaker_mute", color="#E81123", size=16))
            else:
                self.btn_mute_out.setIcon(icons.get_icon("speaker", color="#FFFFFF", size=16))

            # 2. Input volume
            in_vol, in_muted = self.backend.get_volume("@DEFAULT_AUDIO_SOURCE@")
            pct_in = int(round(in_vol * 100))
            self.slider_in.setValue(pct_in)
            self.lbl_in_pct.setText(str(pct_in))
            if in_muted:
                self.btn_mute_in.setIcon(icons.get_icon("mic_off", color="#E81123", size=16))
            else:
                self.btn_mute_in.setIcon(icons.get_icon("mic", color="#FFFFFF", size=16))

            # 3. Endpoints
            sinks, sources = self.backend.get_endpoints()
            self._update_combo(self.combo_sinks, sinks)
            self._update_combo(self.combo_sources, sources)

        finally:
            self._updating = False

    def _update_combo(self, combo: QComboBox, endpoints: List[AudioEndpoint]) -> None:
        current_data = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        selected_idx = 0
        for idx, ep in enumerate(endpoints):
            name_display = f"{ep.name}"
            combo.addItem(name_display, ep.id)
            if ep.is_default or (current_data and current_data == ep.id):
                selected_idx = idx
        if combo.count() > 0:
            combo.setCurrentIndex(selected_idx)
        combo.blockSignals(False)

    def _on_sink_changed(self, index: int) -> None:
        if self._updating:
            return
        node_id = self.combo_sinks.itemData(index)
        if node_id:
            self.backend.set_default(node_id)
            self._sync_state()

    def _on_source_changed(self, index: int) -> None:
        if self._updating:
            return
        node_id = self.combo_sources.itemData(index)
        if node_id:
            self.backend.set_default(node_id)
            self._sync_state()

    def _on_out_slider_changed(self, value: int) -> None:
        self.lbl_out_pct.setText(str(value))
        if not self._updating:
            self.backend.set_volume("@DEFAULT_AUDIO_SINK@", value / 100.0)

    def _on_in_slider_changed(self, value: int) -> None:
        self.lbl_in_pct.setText(str(value))
        if not self._updating:
            self.backend.set_volume("@DEFAULT_AUDIO_SOURCE@", value / 100.0)

    def _on_toggle_mute_out(self) -> None:
        self.backend.set_mute("@DEFAULT_AUDIO_SINK@")
        self._sync_state()

    def _on_toggle_mute_in(self) -> None:
        self.backend.set_mute("@DEFAULT_AUDIO_SOURCE@")
        self._sync_state()
