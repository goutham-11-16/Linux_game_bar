"""Full-screen overlay host window coordinating dashboard and widgets."""

from typing import Dict, Optional, List
from PySide6.QtCore import Qt, QPoint, QRect, Signal, QEvent
from PySide6.QtGui import QColor, QPainter, QGuiApplication, QKeyEvent, QMouseEvent, QRegion
from PySide6.QtWidgets import (
    QWidget,
    QApplication,
)

from linux_game_bar.ui.theme import Theme
from linux_game_bar.ui.dashboard import DashboardBar
from linux_game_bar.ui.widget_base import WidgetBase
from linux_game_bar.ui.settings_dialog import SettingsDialog
from linux_game_bar.config_manager import ConfigManager
from linux_game_bar.widgets.performance import PerformanceWidget
from linux_game_bar.widgets.audio import AudioWidget
from linux_game_bar.widgets.capture import CaptureWidget
from linux_game_bar.widgets.launcher import LauncherWidget
from linux_game_bar.widgets.battery import BatteryWidget
from linux_game_bar.widgets.notes import NotesWidget
from linux_game_bar.widgets.timer import TimerWidget
from linux_game_bar.sdk.loader import PluginLoader


class OverlayWindow(QWidget):
    """Semi-transparent backdrop host for Game Bar widgets."""

    visibility_changed = Signal(bool)

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self._is_overlay_visible = False

        self._widgets: Dict[str, WidgetBase] = {}
        self._pinned_widgets: set[str] = set()

        self._init_window()
        self._init_components()
        self._restore_saved_state()

        qinst = QApplication.instance()
        if qinst:
            qinst.installEventFilter(self)

    def _init_window(self) -> None:
        # Overlay window attributes - bypass window manager so it acts as an OS-level overlay
        # Qt.Tool + Qt.BypassWindowManagerHint prevents window manager taskbar/Alt-Tab/Overview interception
        self.setWindowFlags(
            Qt.Window
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.BypassWindowManagerHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_AlwaysShowToolTips, True)

        # Cover primary screen geometry
        screen = QGuiApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())

    def _init_components(self) -> None:
        # 1. Top Dashboard Bar
        self.dashboard_bar = DashboardBar(self)
        self.dashboard_bar.widget_toggled.connect(self._on_widget_toggled)
        self.dashboard_bar.settings_clicked.connect(self._open_settings)
        self.dashboard_bar.quit_clicked.connect(self.hide_overlay)

        # Center top bar
        bar_w = 540
        bar_x = (self.width() - bar_w) // 2
        self.dashboard_bar.setGeometry(bar_x, 15, bar_w, 44)

        # 2. Instantiate Built-in Widgets
        self.widget_perf = PerformanceWidget(self)
        self.widget_audio = AudioWidget(self)
        self.widget_capture = CaptureWidget(self.config_manager, self)
        self.widget_launcher = LauncherWidget(self.config_manager, self)
        self.widget_battery = BatteryWidget(self)
        self.widget_notes = NotesWidget(self)
        self.widget_timer = TimerWidget(self)

        self._register_widget("performance", self.widget_perf)
        self._register_widget("audio", self.widget_audio)
        self._register_widget("capture", self.widget_capture)
        self._register_widget("launcher", self.widget_launcher)
        self._register_widget("battery", self.widget_battery)
        self._register_widget("notes", self.widget_notes)
        self._register_widget("timer", self.widget_timer)

        # 3. Third-party SDK Plugins
        self.plugin_loader = PluginLoader(host_config=self.config_manager)
        plugin_widgets = self.plugin_loader.discover_and_load(parent_window=self)
        for wid, p_widget in plugin_widgets.items():
            self._register_widget(wid, p_widget)
            meta = p_widget.plugin.METADATA
            if hasattr(self.dashboard_bar, "menu_flyout"):
                self.dashboard_bar.menu_flyout.add_widget_entry(
                    widget_id=wid,
                    display_name=meta.title,
                    icon_name=meta.icon_name,
                    is_favorite=False,
                )

    def _register_widget(self, widget_id: str, widget: WidgetBase) -> None:
        self._widgets[widget_id] = widget
        widget.closed.connect(self._on_widget_closed)
        widget.pinned_changed.connect(self._on_widget_pinned)
        widget.geometry_changed.connect(self._on_widget_geometry_changed)

    def _restore_saved_state(self) -> None:
        """Restore positions, sizes, and pinned status from configuration."""
        saved_positions = self.config_manager.get("ui.widget_positions", {})
        open_list = self.config_manager.get("ui.open_widgets", ["performance", "audio", "capture"])
        pinned_list = self.config_manager.get("ui.pinned_widgets", [])

        for w_id, w in self._widgets.items():
            if w_id in saved_positions:
                p = saved_positions[w_id]
                w.setGeometry(p.get("x", 50), p.get("y", 90), p.get("width", 320), p.get("height", 400))

            is_open = w_id in open_list
            is_pinned = w_id in pinned_list

            w.set_pinned(is_pinned)
            if is_pinned:
                self._pinned_widgets.add(w_id)

            if is_open:
                self.dashboard_bar.set_widget_active(w_id, True)
                w.show()
            else:
                self.dashboard_bar.set_widget_active(w_id, False)
                w.hide()

    def toggle_overlay(self) -> None:
        if self._is_overlay_visible:
            self.hide_overlay()
        else:
            self.show_overlay()

    def show_overlay(self) -> None:
        self._is_overlay_visible = True
        self.clearMask()
        self.show()
        self.raise_()
        self.activateWindow()

        # Show all open widgets
        open_list = self.config_manager.get("ui.open_widgets", [])
        for w_id in open_list:
            if w_id in self._widgets:
                self._widgets[w_id].show()
                self._widgets[w_id].raise_()

        self.dashboard_bar.show()
        self.dashboard_bar.raise_()
        self.update()
        self.visibility_changed.emit(True)

    def hide_overlay(self) -> None:
        self._is_overlay_visible = False

        # Hide unpinned widgets and dashboard bar
        for w_id, w in self._widgets.items():
            if w_id not in self._pinned_widgets:
                w.hide()

        self.dashboard_bar.hide()
        if hasattr(self.dashboard_bar, "menu_flyout"):
            self.dashboard_bar.menu_flyout.hide()
        # If no widgets are pinned, hide backdrop completely
        if not self._pinned_widgets:
            self.clearMask()
            self.hide()
        else:
            self._update_pinned_mask()
            self.update()

        self.visibility_changed.emit(False)

    def hide_for_capture(self) -> None:
        """Temporarily hide overlay window and all widgets so clean desktop/game is captured."""
        self.hide()
        QApplication.processEvents()

    def restore_after_capture(self) -> None:
        """Restore overlay visibility after screenshot capture completes."""
        if self._is_overlay_visible:
            self.show_overlay()
        elif self._pinned_widgets:
            self.show()
            self._update_pinned_mask()
            for w_id in self._pinned_widgets:
                if w_id in self._widgets:
                    self._widgets[w_id].show()
                    self._widgets[w_id].raise_()
        QApplication.processEvents()

    def _update_pinned_mask(self) -> None:
        """Set window mask to only the union of pinned widget rectangles."""
        region = QRegion()
        for w_id in self._pinned_widgets:
            w = self._widgets.get(w_id)
            if w and w.isVisible():
                region = region.united(QRegion(w.geometry()))
        if not region.isEmpty():
            self.setMask(region)
        else:
            self.clearMask()
            self.hide()

    def _on_widget_toggled(self, widget_id: str, active: bool) -> None:
        if widget_id in self._widgets:
            widget = self._widgets[widget_id]
            open_list: List[str] = list(self.config_manager.get("ui.open_widgets", []))

            if active:
                widget.show()
                widget.raise_()
                if widget_id not in open_list:
                    open_list.append(widget_id)
            else:
                widget.hide()
                if widget_id in open_list:
                    open_list.remove(widget_id)

            self.config_manager.set("ui.open_widgets", open_list)

    def _on_widget_closed(self, widget_id: str) -> None:
        self.dashboard_bar.set_widget_active(widget_id, False)
        open_list: List[str] = list(self.config_manager.get("ui.open_widgets", []))
        if widget_id in open_list:
            open_list.remove(widget_id)
            self.config_manager.set("ui.open_widgets", open_list)

    def _on_widget_pinned(self, widget_id: str, is_pinned: bool) -> None:
        pinned_list: List[str] = list(self.config_manager.get("ui.pinned_widgets", []))
        if is_pinned:
            self._pinned_widgets.add(widget_id)
            if widget_id not in pinned_list:
                pinned_list.append(widget_id)
        else:
            self._pinned_widgets.discard(widget_id)
            if widget_id in pinned_list:
                pinned_list.remove(widget_id)
        self.config_manager.set("ui.pinned_widgets", pinned_list)

    def _on_widget_geometry_changed(self, widget_id: str, x: int, y: int, w: int, h: int) -> None:
        saved_positions = self.config_manager.get("ui.widget_positions", {})
        saved_positions[widget_id] = {"x": x, "y": y, "width": w, "height": h}
        self.config_manager.set("ui.widget_positions", saved_positions)
        if not self._is_overlay_visible and widget_id in self._pinned_widgets:
            self._update_pinned_mask()

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.config_manager, self)
        dlg.reset_layout_requested.connect(self._reset_layout)
        dlg.exec()

    def _reset_layout(self) -> None:
        defaults = {
            "performance": {"x": 40, "y": 90, "width": 340, "height": 480},
            "audio": {"x": 400, "y": 90, "width": 360, "height": 420},
            "capture": {"x": 780, "y": 90, "width": 340, "height": 390},
            "launcher": {"x": 400, "y": 90, "width": 460, "height": 500},
            "battery": {"x": 1140, "y": 90, "width": 320, "height": 360},
            "notes": {"x": 780, "y": 90, "width": 380, "height": 480},
            "timer": {"x": 1140, "y": 90, "width": 320, "height": 340},
        }
        for w_id, p in defaults.items():
            if w_id in self._widgets:
                self._widgets[w_id].setGeometry(p["x"], p["y"], p["width"], p["height"])
        self.config_manager.set("ui.widget_positions", defaults)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Dismiss overlay if user clicks on any plane/backdrop area."""
        if self._is_overlay_visible and event.button() in (Qt.LeftButton, Qt.RightButton):
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            if not self._is_pos_inside_interactive_widget(pos):
                self.hide_overlay()
                event.accept()
                return
        super().mousePressEvent(event)

    def _is_pos_inside_interactive_widget(self, pos: QPoint) -> bool:
        """Check if a coordinate falls inside the dashboard or any active widget."""
        if self.dashboard_bar.isVisible() and self.dashboard_bar.geometry().contains(pos):
            return True
        for widget in self._widgets.values():
            if widget.isVisible() and widget.geometry().contains(pos):
                return True
        return False

    def eventFilter(self, watched, event) -> bool:
        """Globally intercept Escape to dismiss overlay from any child widget."""
        if self._is_overlay_visible and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Escape:
                self.hide_overlay()
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        # Dismiss overlay on Escape
        if event.key() == Qt.Key_Escape:
            self.hide_overlay()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:
        # If overlay is visible, draw semi-transparent dim backdrop
        if self._is_overlay_visible:
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor(14, 14, 16, 170))
