"""Environment and capabilities detection module for Linux Game Bar."""

import os
import shutil
import subprocess
import psutil
from pathlib import Path
from typing import Optional, List

from linux_game_bar.capabilities import SystemCapabilities, MonitorInfo


class EnvironmentDetector:
    """Discovers underlying hardware, desktop session, audio backend, and media tools."""

    @staticmethod
    def detect() -> SystemCapabilities:
        caps = SystemCapabilities()

        # 1. OS & Kernel
        EnvironmentDetector._detect_os(caps)

        # 2. Desktop & Session
        EnvironmentDetector._detect_desktop(caps)

        # 3. CPU & RAM
        EnvironmentDetector._detect_cpu_ram(caps)

        # 4. GPU & Telemetry
        EnvironmentDetector._detect_gpu(caps)

        # 5. Audio Backend
        EnvironmentDetector._detect_audio(caps)

        # 6. Power & Thermal
        EnvironmentDetector._detect_power_thermal(caps)

        # 7. Capture Tools
        EnvironmentDetector._detect_capture(caps)

        # 8. GNOME Integration
        EnvironmentDetector._detect_gnome(caps)

        return caps

    @staticmethod
    def _detect_os(caps: SystemCapabilities) -> None:
        os_release = Path("/etc/os-release")
        if os_release.exists():
            try:
                with open(os_release, "r", encoding="utf-8") as f:
                    data = {}
                    for line in f:
                        if "=" in line:
                            k, v = line.strip().split("=", 1)
                            data[k] = v.strip('"')
                    caps.os_name = data.get("NAME", "Linux")
                    caps.os_version = data.get("VERSION", data.get("VERSION_ID", "Unknown"))
            except Exception:
                pass

        try:
            uname = os.uname()
            caps.kernel_version = uname.release
        except Exception:
            pass

    @staticmethod
    def _detect_desktop(caps: SystemCapabilities) -> None:
        caps.desktop_environment = os.environ.get("XDG_CURRENT_DESKTOP", "GNOME")
        session = os.environ.get("XDG_SESSION_TYPE", "").lower()
        if session in ("wayland", "x11"):
            caps.session_type = session
        elif os.environ.get("WAYLAND_DISPLAY"):
            caps.session_type = "wayland"
        else:
            caps.session_type = "x11"

        # Try to get GNOME version
        try:
            out = subprocess.check_output(["gnome-shell", "--version"], text=True, timeout=2).strip()
            # Format: GNOME Shell 46.0 or similar
            caps.gnome_version = out.replace("GNOME Shell ", "")
        except Exception:
            caps.gnome_version = None

    @staticmethod
    def _detect_cpu_ram(caps: SystemCapabilities) -> None:
        # CPU Model from /proc/cpuinfo
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
                for line in f:
                    if "model name" in line:
                        caps.cpu_model = line.split(":", 1)[1].strip()
                        break
        except Exception:
            caps.cpu_model = "Intel/AMD Processor"

        caps.cpu_logical_cores = psutil.cpu_count(logical=True) or 1
        caps.cpu_physical_cores = psutil.cpu_count(logical=False) or caps.cpu_logical_cores

        try:
            caps.total_ram_bytes = psutil.virtual_memory().total
        except Exception:
            caps.total_ram_bytes = 0

    @staticmethod
    def _detect_gpu(caps: SystemCapabilities) -> None:
        # Check /sys/class/drm
        drm_path = Path("/sys/class/drm")
        if not drm_path.exists():
            return

        for card in sorted(drm_path.glob("card*")):
            # Look for render device or primary card
            device_dir = card / "device"
            if not device_dir.exists():
                continue

            # Read vendor & device
            driver_link = device_dir / "driver"
            driver_name = driver_link.resolve().name if driver_link.exists() else "unknown"

            # Check for Intel GT sysfs frequencies
            gt_act = card / "gt_act_freq_mhz"
            gt_sub = card / "gt" / "gt0" / "rps_act_freq_mhz"
            if gt_act.exists() or gt_sub.exists():
                caps.gpu_metrics_available = True
                caps.intel_gt_sysfs_path = str(card)
                caps.gpu_driver = driver_name
                caps.gpu_model = "Intel Iris Xe Graphics (i915/xe)"
                return

        # Fallback check lspci or default
        try:
            out = subprocess.check_output(["lspci"], text=True, timeout=2)
            for line in out.splitlines():
                if "VGA compatible controller" in line or "3D controller" in line:
                    caps.gpu_model = line.split(":", 2)[-1].strip()
                    break
        except Exception:
            pass

    @staticmethod
    def _detect_audio(caps: SystemCapabilities) -> None:
        caps.wpctl_available = shutil.which("wpctl") is not None
        caps.pactl_available = shutil.which("pactl") is not None

        if caps.wpctl_available:
            caps.audio_backend = "pipewire"
        elif caps.pactl_available:
            caps.audio_backend = "pulseaudio"
        else:
            caps.audio_backend = "none"

    @staticmethod
    def _detect_power_thermal(caps: SystemCapabilities) -> None:
        # Battery
        try:
            batt = psutil.sensors_battery()
            if batt is not None:
                caps.battery_available = True
                caps.battery_percent = batt.percent
                caps.power_plugged = batt.power_plugged
        except Exception:
            caps.battery_available = False

        # Thermal
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                caps.thermal_sensors_available = True
                caps.thermal_sensor_names = list(temps.keys())
        except Exception:
            caps.thermal_sensors_available = False

    @staticmethod
    def _detect_capture(caps: SystemCapabilities) -> None:
        # Screenshot detection
        methods = []
        # Test GNOME Shell screenshot DBus
        try:
            res = subprocess.run(
                ["gdbus", "introspect", "--session", "--dest", "org.gnome.Shell.Screenshot", "--object-path", "/org/gnome/Shell/Screenshot"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=1,
            )
            if res.returncode == 0:
                methods.append("gnome_shell_dbus")
        except Exception:
            pass

        if shutil.which("grim"):
            methods.append("grim")
        if shutil.which("gnome-screenshot"):
            methods.append("gnome-screenshot")

        caps.screenshot_methods = methods
        caps.screenshot_supported = len(methods) > 0

        # Recording detection
        rec_methods = []
        try:
            res = subprocess.run(
                ["gdbus", "introspect", "--session", "--dest", "org.gnome.Shell.Screencast", "--object-path", "/org/gnome/Shell/Screencast"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=1,
            )
            if res.returncode == 0:
                rec_methods.append("gnome_shell_screencast")
        except Exception:
            pass

        if shutil.which("ffmpeg"):
            rec_methods.append("ffmpeg")

        caps.recording_methods = rec_methods
        caps.recording_supported = len(rec_methods) > 0

    @staticmethod
    def _detect_gnome(caps: SystemCapabilities) -> None:
        if shutil.which("gsettings") is not None:
            try:
                res = subprocess.run(
                    ["gsettings", "list-schemas"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=2,
                )
                if "org.gnome.settings-daemon.plugins.media-keys" in res.stdout:
                    caps.gsettings_available = True
            except Exception:
                caps.gsettings_available = False
