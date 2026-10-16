"""Battery and Temperature monitoring widget."""

from typing import Dict, Any
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QFrame,
    QGridLayout,
)

from linux_game_bar.ui.widget_base import WidgetBase
from linux_game_bar.ui.theme import Theme


class BatteryWidget(WidgetBase):
    """Battery state and system thermal status widget."""

    def __init__(self, parent: QWidget = None):
        super().__init__("battery", "BATTERY & THERMALS", "performance", parent)
        self.setMinimumSize(300, 340)
        self.resize(320, 360)

        self._build_ui()

    def _build_ui(self) -> None:
        # 1. Battery Card
        card_batt = QFrame()
        card_batt.setStyleSheet(f"background-color: {Theme.BG_CARD}; border-radius: 8px; padding: 10px;")
        vbox_batt = QVBoxLayout(card_batt)
        vbox_batt.setSpacing(6)

        hdr_batt = QHBoxLayout()
        lbl_batt_title = QLabel("🔋 Battery Level")
        lbl_batt_title.setStyleSheet("font-weight: 600; color: #ffffff;")
        hdr_batt.addWidget(lbl_batt_title)
        hdr_batt.addStretch()

        self.lbl_batt_status = QLabel("Plugged In")
        self.lbl_batt_status.setStyleSheet("font-size: 11px; font-weight: 600; color: #A0A0A5;")
        hdr_batt.addWidget(self.lbl_batt_status)
        vbox_batt.addLayout(hdr_batt)

        self.lbl_batt_pct = QLabel("80%")
        self.lbl_batt_pct.setStyleSheet("font-size: 28px; font-weight: 700; color: #ffffff; margin: 2px 0;")
        vbox_batt.addWidget(self.lbl_batt_pct)

        self.bar_batt = QProgressBar()
        self.bar_batt.setRange(0, 100)
        self.bar_batt.setValue(80)
        self.bar_batt.setFixedHeight(10)
        self.bar_batt.setTextVisible(False)
        self.bar_batt.setStyleSheet(f"""
            QProgressBar {{
                background-color: #1e1e22;
                border-radius: 5px;
            }}
            QProgressBar::chunk {{
                background-color: {Theme.ACCENT_GREEN};
                border-radius: 5px;
            }}
        """)
        vbox_batt.addWidget(self.bar_batt)

        self.lbl_batt_time = QLabel("AC Power Connected (Charging)")
        self.lbl_batt_time.setStyleSheet("font-size: 12px; color: #A0A0A5;")
        vbox_batt.addWidget(self.lbl_batt_time)

        self.content_layout.addWidget(card_batt)

        # 2. Thermals Card
        card_temp = QFrame()
        card_temp.setStyleSheet(f"background-color: {Theme.BG_CARD}; border-radius: 8px; padding: 10px;")
        vbox_temp = QVBoxLayout(card_temp)
        vbox_temp.setSpacing(8)

        lbl_temp_title = QLabel("🌡️ System Thermals & Fans")
        lbl_temp_title.setStyleSheet("font-weight: 600; color: #ffffff;")
        vbox_temp.addWidget(lbl_temp_title)

        grid_temp = QGridLayout()
        grid_temp.setHorizontalSpacing(10)
        grid_temp.setVerticalSpacing(6)

        grid_temp.addWidget(QLabel("CPU Package:"), 0, 0)
        self.lbl_temp_cpu = QLabel("55.0 °C")
        self.lbl_temp_cpu.setStyleSheet("font-weight: 700; color: #ffffff;")
        grid_temp.addWidget(self.lbl_temp_cpu, 0, 1)

        grid_temp.addWidget(QLabel("Fan Speed:"), 1, 0)
        self.lbl_fan_rpm = QLabel("4200 RPM")
        self.lbl_fan_rpm.setStyleSheet("font-weight: 700; color: #ffffff;")
        grid_temp.addWidget(self.lbl_fan_rpm, 1, 1)

        grid_temp.addWidget(QLabel("Thermal Status:"), 2, 0)
        self.lbl_thermal_status = QLabel("Normal")
        self.lbl_thermal_status.setStyleSheet(f"font-weight: 700; color: {Theme.ACCENT_GREEN};")
        grid_temp.addWidget(self.lbl_thermal_status, 2, 1)

        vbox_temp.addLayout(grid_temp)
        self.content_layout.addWidget(card_temp)

    def update_metrics(self, data: Dict[str, Any]) -> None:
        """Slot to update battery and thermal telemetry."""
        batt = data.get("battery", {})
        thermal = data.get("thermal", {})

        # Battery
        if batt.get("available"):
            pct = batt.get("percent", 0.0)
            status = batt.get("status", "Unknown")
            plugged = batt.get("power_plugged", False)
            time_str = batt.get("time_remaining_str", "")

            self.lbl_batt_pct.setText(f"{pct:.0f}%")
            self.bar_batt.setValue(int(pct))
            self.lbl_batt_status.setText(status)
            self.lbl_batt_time.setText(time_str or ("Plugged In" if plugged else "Discharging"))

            # Coloring
            if pct <= 20 and not plugged:
                self.bar_batt.setStyleSheet(f"""
                    QProgressBar {{ background-color: #1e1e22; border-radius: 5px; }}
                    QProgressBar::chunk {{ background-color: {Theme.COLOR_DANGER}; border-radius: 5px; }}
                """)
            else:
                self.bar_batt.setStyleSheet(f"""
                    QProgressBar {{ background-color: #1e1e22; border-radius: 5px; }}
                    QProgressBar::chunk {{ background-color: {Theme.ACCENT_GREEN}; border-radius: 5px; }}
                """)
        else:
            self.lbl_batt_pct.setText("N/A")
            self.lbl_batt_status.setText("No Battery")
            self.lbl_batt_time.setText("Desktop / Direct AC power")

        # Thermals
        cpu_temp = thermal.get("cpu_temp_c")
        fan_rpm = thermal.get("fan_rpm")

        if cpu_temp is not None:
            self.lbl_temp_cpu.setText(f"{cpu_temp:.1f} °C")
            if cpu_temp >= 85.0:
                self.lbl_thermal_status.setText("HOT (Throttling Risk)")
                self.lbl_thermal_status.setStyleSheet(f"font-weight: 700; color: {Theme.COLOR_DANGER};")
            elif cpu_temp >= 70.0:
                self.lbl_thermal_status.setText("Warm")
                self.lbl_thermal_status.setStyleSheet(f"font-weight: 700; color: {Theme.COLOR_WARNING};")
            else:
                self.lbl_thermal_status.setText("Normal")
                self.lbl_thermal_status.setStyleSheet(f"font-weight: 700; color: {Theme.ACCENT_GREEN};")
        else:
            self.lbl_temp_cpu.setText("Unavailable")

        if fan_rpm is not None:
            self.lbl_fan_rpm.setText(f"{fan_rpm} RPM")
        else:
            self.lbl_fan_rpm.setText("N/A")
