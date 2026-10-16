"""Unit tests for EnvironmentDetector."""

from linux_game_bar.platform.detector import EnvironmentDetector
from linux_game_bar.capabilities import SystemCapabilities


def test_environment_detector_returns_capabilities():
    caps = EnvironmentDetector.detect()
    assert isinstance(caps, SystemCapabilities)
    assert caps.os_name is not None
    assert caps.session_type in ("wayland", "x11")
    assert caps.cpu_logical_cores >= 1
    assert caps.total_ram_bytes > 0


def test_capabilities_summary():
    caps = EnvironmentDetector.detect()
    summary = caps.summary()
    assert "Linux Game Bar Platform Capabilities" in summary
    assert caps.session_type.upper() in summary
    assert "CPU:" in summary


def test_capabilities_to_dict():
    caps = EnvironmentDetector.detect()
    d = caps.to_dict()
    assert "os_name" in d
    assert "cpu_logical_cores" in d
    assert "gpu_metrics_available" in d
    assert isinstance(d["screenshot_methods"], list)
