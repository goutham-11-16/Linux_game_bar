"""Performance monitor widget displaying CPU, RAM, Intel GPU metrics, and graphs."""

import os
from typing import Dict, Any
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QCheckBox,
    QGridLayout,
    QScrollArea,
    QFrame,
)

from linux_game_bar.ui.widget_base import WidgetBase
from linux_game_bar.ui.components.sparkline import SparklineGraph
from linux_game_bar.ui.theme import Theme
from linux_game_bar.ui import icons


class PerformanceWidget(WidgetBase):
    """Real-time performance overlay widget inspired by Windows 11 Xbox Game Bar."""

    def __init__(self, parent: QWidget = None):
        super().__init__("performance", "PERFORMANCE", "performance", parent)
        self.setMinimumSize(320, 420)
        self.resize(340, 480)
        self._paused = False

        self._build_content()

    def _build_content(self) -> None:
        # 1. Graphs Section (CPU & RAM)
        self.cpu_graph = SparklineGraph(title="CPU Utilization", unit="%", max_val=100.0, accent=Theme.ACCENT_GREEN)
        self.content_layout.addWidget(self.cpu_graph)

        self.ram_graph = SparklineGraph(title="RAM Utilization", unit="%", max_val=100.0, accent="#00B4D8")
        self.content_layout.addWidget(self.ram_graph)

        # 2. Key Summary Cards
        card_summary = QFrame()
        card_summary.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.BG_CARD};
                border-radius: 8px;
                border: 1px solid {Theme.BORDER_SUBTLE};
            }}
        """)
        summary_grid = QGridLayout(card_summary)
        summary_grid.setContentsMargins(10, 10, 10, 10)
        summary_grid.setHorizontalSpacing(8)
        summary_grid.setVerticalSpacing(6)

        # CPU label
        self.lbl_cpu_detail = QLabel("CPU: 0.0% @ 0.0 GHz")
        self.lbl_cpu_detail.setStyleSheet("font-weight: 600; font-size: 12px; color: #ffffff;")
        summary_grid.addWidget(self.lbl_cpu_detail, 0, 0)

        # RAM label
        self.lbl_ram_detail = QLabel("RAM: 0.0 / 0.0 GiB (0%)")
        self.lbl_ram_detail.setStyleSheet("font-weight: 600; font-size: 12px; color: #ffffff;")
        summary_grid.addWidget(self.lbl_ram_detail, 0, 1)

        # GPU label
        self.lbl_gpu_detail = QLabel("GPU: Telemetry Initializing...")
        self.lbl_gpu_detail.setStyleSheet("font-size: 11px; color: #A0A0A5;")
        summary_grid.addWidget(self.lbl_gpu_detail, 1, 0, 1, 2)

        # Swap label
        self.lbl_swap_detail = QLabel("Swap: 0.0 / 0.0 GiB")
        self.lbl_swap_detail.setStyleSheet("font-size: 11px; color: #707075;")
        summary_grid.addWidget(self.lbl_swap_detail, 2, 0)

        # FPS / Overlay note
        self.lbl_fps = QLabel("FPS: In-Game (MangoHud)")
        self.lbl_fps.setStyleSheet("font-size: 11px; color: #707075;")
        summary_grid.addWidget(self.lbl_fps, 2, 1)

        self.content_layout.addWidget(card_summary)

        # 3. Per-Core Utilization (Collapsible)
        self.chk_cores = QCheckBox("Show per-core meters (16 cores)")
        self.chk_cores.setStyleSheet("font-size: 11px; color: #A0A0A5; margin-top: 4px;")
        self.chk_cores.toggled.connect(self._toggle_cores_view)
        self.content_layout.addWidget(self.chk_cores)

        self.cores_scroll = QScrollArea()
        self.cores_scroll.setWidgetResizable(True)
        self.cores_scroll.setFixedHeight(120)
        self.cores_scroll.setVisible(False)
        self.cores_scroll.setStyleSheet("background: transparent; border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 6px;")

        self.cores_widget = QWidget()
        self.cores_layout = QGridLayout(self.cores_widget)
        self.cores_layout.setContentsMargins(6, 6, 6, 6)
        self.cores_layout.setSpacing(4)
        self.core_bars = []

        for i in range(16):
            lbl = QLabel(f"C{i}")
            lbl.setStyleSheet("font-size: 10px; color: #707075;")
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setFixedHeight(6)
            bar.setTextVisible(False)
            bar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: #25252a;
                    border-radius: 3px;
                }}
                QProgressBar::chunk {{
                    background-color: {Theme.ACCENT_GREEN};
                    border-radius: 3px;
                }}
            """)
            row = i // 2
            col = (i % 2) * 2
            self.cores_layout.addWidget(lbl, row, col)
            self.cores_layout.addWidget(bar, row, col + 1)
            self.core_bars.append(bar)

        self.cores_scroll.setWidget(self.cores_widget)
        self.content_layout.addWidget(self.cores_scroll)

    def _toggle_cores_view(self, visible: bool) -> None:
        self.cores_scroll.setVisible(visible)
        if visible:
            self.resize(self.width(), self.height() + 120)
        else:
            self.resize(self.width(), max(420, self.height() - 120))

    def update_metrics(self, data: Dict[str, Any]) -> None:
        """Slot called whenever MetricsWorker emits fresh telemetry."""
        if self._paused:
            return

        cpu = data.get("cpu", {})
        ram = data.get("ram", {})
        gpu = data.get("gpu", {})

        # Update graphs
        self.cpu_graph.set_data(cpu.get("history", []))
        self.ram_graph.set_data(ram.get("history", []))

        # Update labels
        cpu_pct = cpu.get("percent", 0.0)
        cpu_ghz = cpu.get("freq_ghz", 0.0)
        self.lbl_cpu_detail.setText(f"CPU: {cpu_pct:.1f}% @ {cpu_ghz:.2f} GHz")

        used_ram = ram.get("used_gb", 0.0)
        tot_ram = ram.get("total_gb", 0.0)
        ram_pct = ram.get("percent", 0.0)
        self.lbl_ram_detail.setText(f"RAM: {used_ram:.1f}/{tot_ram:.1f} GiB ({ram_pct:.0f}%)")

        # Swap
        swap_used = ram.get("swap_used_gb", 0.0)
        swap_tot = ram.get("swap_total_gb", 0.0)
        self.lbl_swap_detail.setText(f"Swap: {swap_used:.1f}/{swap_tot:.1f} GiB")

        # GPU
        if gpu.get("available"):
            act_freq = gpu.get("act_freq_mhz", 0)
            max_freq = gpu.get("max_freq_mhz", 1500)
            pct = gpu.get("percent", 0.0)
            self.lbl_gpu_detail.setText(f"GPU: Intel Iris Xe @ {act_freq} MHz / {max_freq} MHz ({pct:.0f}%)")
        else:
            self.lbl_gpu_detail.setText("GPU: Intel Iris Xe (No Telemetry Sysfs)")

        # Per core bars
        if self.chk_cores.isChecked():
            per_core = cpu.get("per_core", [])
            for i, val in enumerate(per_core):
                if i < len(self.core_bars):
                    self.core_bars[i].setValue(int(val))
