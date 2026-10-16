"""Background metrics collector thread emitting telemetry signals."""

import time
import logging
from collections import deque
from pathlib import Path
from typing import Dict, Any, Optional

import psutil
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger("linux_game_bar.metrics")


class MetricsWorker(QThread):
    """Periodically samples system, GPU, battery, and thermal telemetry."""

    metrics_updated = Signal(dict)

    def __init__(self, interval_ms: int = 1000, history_len: int = 60, intel_sysfs_path: Optional[str] = None):
        super().__init__()
        self.interval_ms = interval_ms
        self.history_len = history_len
        self.intel_sysfs_path = intel_sysfs_path or "/sys/class/drm/card1"
        self._running = True

        self.cpu_history = deque(maxlen=history_len)
        self.ram_history = deque(maxlen=history_len)
        self.gpu_history = deque(maxlen=history_len)

        # Initial call to prime psutil cpu_percent
        psutil.cpu_percent(interval=None)
        psutil.cpu_percent(interval=None, percpu=True)

    def set_interval(self, interval_ms: int) -> None:
        self.interval_ms = max(200, interval_ms)

    def stop(self) -> None:
        self._running = False
        self.wait(1500)

    def run(self) -> None:
        while self._running:
            start_time = time.monotonic()
            data = self._collect_metrics()
            self.metrics_updated.emit(data)

            elapsed = (time.monotonic() - start_time) * 1000
            sleep_ms = max(50, self.interval_ms - elapsed)
            self.msleep(int(sleep_ms))

    def _collect_metrics(self) -> Dict[str, Any]:
        # 1. CPU
        cpu_percent = psutil.cpu_percent(interval=None)
        per_core = psutil.cpu_percent(interval=None, percpu=True)
        freq = psutil.cpu_freq()
        cpu_cur_freq_ghz = round(freq.current / 1000.0, 2) if freq else 0.0

        self.cpu_history.append(cpu_percent)

        # 2. RAM & Swap
        vmem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        self.ram_history.append(vmem.percent)

        # 3. GPU Telemetry (Intel Iris Xe)
        gpu_data = self._sample_intel_gpu()
        if gpu_data["available"]:
            self.gpu_history.append(gpu_data["percent"])
        else:
            self.gpu_history.append(0.0)

        # 4. Temperatures & Fans
        thermal_data = self._sample_thermals()

        # 5. Battery
        batt_data = self._sample_battery()

        return {
            "timestamp": time.time(),
            "cpu": {
                "percent": cpu_percent,
                "per_core": per_core,
                "freq_ghz": cpu_cur_freq_ghz,
                "history": list(self.cpu_history),
            },
            "ram": {
                "total_gb": round(vmem.total / (1024**3), 2),
                "used_gb": round(vmem.used / (1024**3), 2),
                "available_gb": round(vmem.available / (1024**3), 2),
                "percent": vmem.percent,
                "swap_total_gb": round(swap.total / (1024**3), 2),
                "swap_used_gb": round(swap.used / (1024**3), 2),
                "swap_percent": swap.percent,
                "history": list(self.ram_history),
            },
            "gpu": gpu_data,
            "thermal": thermal_data,
            "battery": batt_data,
        }

    def _sample_intel_gpu(self) -> Dict[str, Any]:
        """Read real Intel GT sysfs frequencies."""
        res = {
            "available": False,
            "model": "Intel Iris Xe",
            "act_freq_mhz": 0,
            "cur_freq_mhz": 0,
            "min_freq_mhz": 100,
            "max_freq_mhz": 1500,
            "percent": 0.0,
            "history": list(self.gpu_history),
        }

        base = Path(self.intel_sysfs_path)
        if not base.exists():
            return res

        try:
            act_path = base / "gt_act_freq_mhz"
            cur_path = base / "gt_cur_freq_mhz"
            min_path = base / "gt_min_freq_mhz"
            max_path = base / "gt_max_freq_mhz"

            if act_path.exists():
                with open(act_path, "r") as f:
                    res["act_freq_mhz"] = int(f.read().strip())
                res["available"] = True

            if cur_path.exists():
                with open(cur_path, "r") as f:
                    res["cur_freq_mhz"] = int(f.read().strip())

            if min_path.exists():
                with open(min_path, "r") as f:
                    res["min_freq_mhz"] = int(f.read().strip())

            if max_path.exists():
                with open(max_path, "r") as f:
                    res["max_freq_mhz"] = int(f.read().strip())

            # Estimate load percentage based on active clock frequency scaling
            cur_active = max(res["act_freq_mhz"], res["cur_freq_mhz"])
            span = max(1, res["max_freq_mhz"] - res["min_freq_mhz"])
            pct = max(0.0, min(100.0, (cur_active - res["min_freq_mhz"]) / span * 100.0))
            res["percent"] = round(pct, 1)

        except Exception as e:
            logger.debug(f"Error reading Intel GPU sysfs: {e}")

        return res

    def _sample_thermals(self) -> Dict[str, Any]:
        res = {
            "cpu_temp_c": None,
            "package_temp_c": None,
            "fan_rpm": None,
            "core_temps": {},
        }
        try:
            temps = psutil.sensors_temperatures()
            if "coretemp" in temps:
                for entry in temps["coretemp"]:
                    if entry.label.startswith("Package"):
                        res["package_temp_c"] = entry.current
                        res["cpu_temp_c"] = entry.current
                    elif entry.label.startswith("Core"):
                        res["core_temps"][entry.label] = entry.current

            # If coretemp didn't provide cpu_temp, check dell_ddv
            if res["cpu_temp_c"] is None and "dell_ddv" in temps:
                for entry in temps["dell_ddv"]:
                    if entry.label == "CPU":
                        res["cpu_temp_c"] = entry.current

            # Fans
            fans = psutil.sensors_fans()
            if fans:
                for fan_list in fans.values():
                    if fan_list:
                        res["fan_rpm"] = fan_list[0].current
                        break
        except Exception as e:
            logger.debug(f"Error reading thermals: {e}")

        return res

    def _sample_battery(self) -> Dict[str, Any]:
        res = {
            "available": False,
            "percent": None,
            "power_plugged": None,
            "status": "Unknown",
            "time_remaining_str": None,
        }
        try:
            batt = psutil.sensors_battery()
            if batt:
                res["available"] = True
                res["percent"] = round(batt.percent, 1)
                res["power_plugged"] = batt.power_plugged

                if batt.power_plugged:
                    res["status"] = "Charging" if batt.percent < 98 else "Full"
                else:
                    res["status"] = "Discharging"

                if batt.secsleft > 0 and batt.secsleft != psutil.POWER_TIME_UNLIMITED:
                    hrs = batt.secsleft // 3600
                    mins = (batt.secsleft % 3600) // 60
                    res["time_remaining_str"] = f"{hrs}h {mins}m remaining"
                elif batt.power_plugged:
                    res["time_remaining_str"] = "Plugged in"
                else:
                    res["time_remaining_str"] = "Estimating..."
        except Exception as e:
            logger.debug(f"Error reading battery: {e}")

        return res
