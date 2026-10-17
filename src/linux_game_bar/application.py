"""Application lifecycle and main coordinator for Linux Game Bar."""

import sys
import signal
import logging
from typing import Optional

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from linux_game_bar.logging_setup import setup_logging
from linux_game_bar.config_manager import ConfigManager
from linux_game_bar.single_instance import SingleInstanceManager
from linux_game_bar.capabilities import SystemCapabilities
from linux_game_bar.platform.detector import EnvironmentDetector
from linux_game_bar.platform.gnome_integration import GnomeShortcutManager
from linux_game_bar.core.metrics_service import MetricsWorker
from linux_game_bar.ui.theme import Theme
from linux_game_bar.ui.overlay_window import OverlayWindow

logger = logging.getLogger("linux_game_bar.app")


class LinuxGameBarApp(QObject):
    """Main application lifecycle controller."""

    def __init__(self, verbose: bool = False):
        super().__init__()
        self.logger = setup_logging(verbose=verbose)
        self.config_manager = ConfigManager()
        self.capabilities: SystemCapabilities = EnvironmentDetector.detect()

        self.qapp: Optional[QApplication] = None
        self.ipc_manager: Optional[SingleInstanceManager] = None
        self.overlay_window: Optional[OverlayWindow] = None
        self.metrics_worker: Optional[MetricsWorker] = None

    def initialize(self) -> bool:
        """Initialize GUI application, single instance server, and background services."""
        # 1. Create Qt Application FIRST before any QObjects or QLocalServers
        self.qapp = QApplication.instance()
        if not self.qapp:
            self.qapp = QApplication(sys.argv)

        self.qapp.setApplicationName("Linux Game Bar")
        self.qapp.setApplicationDisplayName("Linux Game Bar")
        self.qapp.setQuitOnLastWindowClosed(False)

        # 2. Ensure single instance
        self.ipc_manager = SingleInstanceManager(self)
        if not self.ipc_manager.start_server():
            logger.error("Could not start local IPC server (another instance might be active).")
            return False

        # Apply dark theme
        accent = self.config_manager.get("accent_color", Theme.ACCENT_GREEN)
        self.qapp.setStyleSheet(Theme.get_stylesheet(accent=accent))

        # Create overlay window
        self.overlay_window = OverlayWindow(self.config_manager)

        # Wire single instance IPC signals
        self.ipc_manager.toggle_requested.connect(self.overlay_window.toggle_overlay)
        self.ipc_manager.show_requested.connect(self.overlay_window.show_overlay)
        self.ipc_manager.hide_requested.connect(self.overlay_window.hide_overlay)
        self.ipc_manager.quit_requested.connect(self.shutdown)
        self.ipc_manager.reload_requested.connect(self.overlay_window.reload_plugins)
        self.ipc_manager.screenshot_requested.connect(self.trigger_screenshot)

        # Start metrics telemetry worker
        interval_ms = self.config_manager.get("metrics.sampling_interval_ms", 1000)
        self.metrics_worker = MetricsWorker(
            interval_ms=interval_ms,
            history_len=45,
            intel_sysfs_path=self.capabilities.intel_gt_sysfs_path or "/sys/class/drm/card1",
        )
        self.metrics_worker.metrics_updated.connect(self.overlay_window.widget_perf.update_metrics)
        self.metrics_worker.metrics_updated.connect(self.overlay_window.widget_battery.update_metrics)
        self.metrics_worker.start()

        # Handle Unix termination signals
        signal.signal(signal.SIGINT, lambda *_: self.shutdown())
        signal.signal(signal.SIGTERM, lambda *_: self.shutdown())

        return True

    def run(self, show_immediately: bool = False) -> int:
        """Run Qt event loop."""
        if not self.initialize():
            return 1

        if show_immediately:
            self.overlay_window.show_overlay()

        logger.info("Linux Game Bar background daemon is active.")
        return self.qapp.exec()

    def trigger_screenshot(self) -> None:
        """Silently capture screenshot via IPC command or global hotkey."""
        logger.info("Triggering screenshot via IPC / global shortcut...")
        if self.overlay_window and hasattr(self.overlay_window, "widget_capture"):
            self.overlay_window.widget_capture.trigger_capture()
        else:
            from linux_game_bar.platform.portals import CaptureService
            CaptureService().take_screenshot(interactive=False)

    def shutdown(self) -> None:
        """Cleanly stop background services and exit."""
        logger.info("Shutting down Linux Game Bar...")
        if self.metrics_worker:
            self.metrics_worker.stop()
        if self.ipc_manager:
            self.ipc_manager.cleanup()
        if self.qapp:
            self.qapp.quit()
