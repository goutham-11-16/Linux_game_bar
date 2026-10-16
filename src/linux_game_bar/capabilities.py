"""Capabilities data structures for Linux Game Bar."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class MonitorInfo:
    name: str
    width: int
    height: int
    scale: float = 1.0
    is_primary: bool = False


@dataclass
class SystemCapabilities:
    os_name: str = "Linux"
    os_version: str = "Unknown"
    kernel_version: str = "Unknown"
    desktop_environment: str = "GNOME"
    gnome_version: Optional[str] = None
    session_type: str = "wayland"  # wayland or x11

    # Display
    monitors: List[MonitorInfo] = field(default_factory=list)

    # Hardware
    cpu_model: str = "Unknown CPU"
    cpu_logical_cores: int = 1
    cpu_physical_cores: int = 1
    total_ram_bytes: int = 0

    # GPU
    gpu_model: str = "Unknown GPU"
    gpu_driver: str = "unknown"
    gpu_metrics_available: bool = False
    intel_gt_sysfs_path: Optional[str] = None

    # Audio
    audio_backend: str = "unknown"  # pipewire, pulseaudio, none
    wpctl_available: bool = False
    pactl_available: bool = False

    # Power & Thermal
    battery_available: bool = False
    battery_percent: Optional[float] = None
    power_plugged: Optional[bool] = None
    thermal_sensors_available: bool = False
    thermal_sensor_names: List[str] = field(default_factory=list)

    # Capture
    screenshot_supported: bool = False
    screenshot_methods: List[str] = field(default_factory=list)
    recording_supported: bool = False
    recording_methods: List[str] = field(default_factory=list)

    # Integration
    gsettings_available: bool = False
    dbus_available: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert capabilities to a clean serializable dictionary."""
        return {
            "os_name": self.os_name,
            "os_version": self.os_version,
            "kernel_version": self.kernel_version,
            "desktop_environment": self.desktop_environment,
            "gnome_version": self.gnome_version,
            "session_type": self.session_type,
            "monitors": [
                {
                    "name": m.name,
                    "width": m.width,
                    "height": m.height,
                    "scale": m.scale,
                    "is_primary": m.is_primary,
                }
                for m in self.monitors
            ],
            "cpu_model": self.cpu_model,
            "cpu_logical_cores": self.cpu_logical_cores,
            "cpu_physical_cores": self.cpu_physical_cores,
            "total_ram_gb": round(self.total_ram_bytes / (1024**3), 2),
            "gpu_model": self.gpu_model,
            "gpu_driver": self.gpu_driver,
            "gpu_metrics_available": self.gpu_metrics_available,
            "audio_backend": self.audio_backend,
            "battery_available": self.battery_available,
            "thermal_sensors_available": self.thermal_sensors_available,
            "thermal_sensor_names": self.thermal_sensor_names,
            "screenshot_methods": self.screenshot_methods,
            "recording_methods": self.recording_methods,
            "gsettings_available": self.gsettings_available,
        }

    def summary(self) -> str:
        """Return formatted human-readable diagnostic summary."""
        lines = [
            "=== Linux Game Bar Platform Capabilities ===",
            f"OS: {self.os_name} {self.os_version} (Kernel: {self.kernel_version})",
            f"Desktop: {self.desktop_environment} (GNOME: {self.gnome_version or 'N/A'})",
            f"Session: {self.session_type.upper()}",
            f"CPU: {self.cpu_model} ({self.cpu_logical_cores} logical cores)",
            f"RAM: {round(self.total_ram_bytes / (1024**3), 1)} GiB",
            f"GPU: {self.gpu_model} (Driver: {self.gpu_driver}, Telemetry: {'Yes' if self.gpu_metrics_available else 'No'})",
            f"Audio Backend: {self.audio_backend} (wpctl: {self.wpctl_available}, pactl: {self.pactl_available})",
            f"Battery: {'Detected' if self.battery_available else 'None'} ({f'{self.battery_percent:.1f}%' if self.battery_percent is not None else 'N/A'})",
            f"Thermal Sensors: {', '.join(self.thermal_sensor_names) if self.thermal_sensor_names else 'None'}",
            f"Screenshot Methods: {', '.join(self.screenshot_methods) if self.screenshot_methods else 'None'}",
            f"Recording Methods: {', '.join(self.recording_methods) if self.recording_methods else 'None'}",
            f"GNOME Shortcuts (GSettings): {'Available' if self.gsettings_available else 'Unavailable'}",
            "============================================",
        ]
        return "\n".join(lines)
