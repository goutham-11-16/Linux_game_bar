"""UI tests verifying dashboard, overlay, and widgets under Qt offscreen platform."""

from pathlib import Path
from linux_game_bar.config_manager import ConfigManager
from linux_game_bar.ui.dashboard import DashboardBar
from linux_game_bar.ui.overlay_window import OverlayWindow
from linux_game_bar.ui.settings_dialog import SettingsDialog


def test_dashboard_bar_widget_toggle(qapp):
    bar = DashboardBar()
    toggled_events = []
    bar.widget_toggled.connect(lambda wid, active: toggled_events.append((wid, active)))

    # Click performance button
    btn_perf = bar._buttons.get("performance")
    assert btn_perf is not None
    btn_perf.click()

    assert len(toggled_events) == 1
    assert toggled_events[0] == ("performance", True)


def test_overlay_window_toggle(qapp, tmp_path: Path):
    cfg = ConfigManager(config_path=tmp_path / "settings.json")
    overlay = OverlayWindow(cfg)

    assert overlay._is_overlay_visible is False

    # Toggle overlay on
    overlay.toggle_overlay()
    assert overlay._is_overlay_visible is True
    assert overlay.dashboard_bar.isVisible() is True

    # Toggle overlay off
    overlay.toggle_overlay()
    assert overlay._is_overlay_visible is False


def test_settings_dialog_save(qapp, tmp_path: Path):
    from unittest.mock import MagicMock
    cfg = ConfigManager(config_path=tmp_path / "settings.json")
    dlg = SettingsDialog(cfg)
    dlg.shortcut_mgr = MagicMock()
    dlg.autostart_mgr = MagicMock()

    dlg.input_hotkey.setText("<Control><Alt>g")
    dlg.combo_interval.setCurrentIndex(0)  # 500ms
    dlg._save_and_apply()

    assert cfg.get("hotkey") == "<Control><Alt>g"
    assert cfg.get("metrics.sampling_interval_ms") == 500


def test_overlay_backdrop_click_dismisses(qapp, tmp_path: Path):
    from PySide6.QtCore import Qt, QPointF, QEvent
    from PySide6.QtGui import QMouseEvent

    cfg = ConfigManager(config_path=tmp_path / "settings.json")
    overlay = OverlayWindow(cfg)
    overlay.show_overlay()
    assert overlay._is_overlay_visible is True

    # Click on plane backdrop area (top-left outside dashboard/widgets)
    ev = QMouseEvent(QEvent.MouseButtonPress, QPointF(5, 5), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    overlay.mousePressEvent(ev)

    assert overlay._is_overlay_visible is False


def test_overlay_widget_click_does_not_dismiss(qapp, tmp_path: Path):
    from PySide6.QtCore import Qt, QPointF, QEvent
    from PySide6.QtGui import QMouseEvent

    cfg = ConfigManager(config_path=tmp_path / "settings.json")
    overlay = OverlayWindow(cfg)
    overlay.show_overlay()
    assert overlay._is_overlay_visible is True

    # Click inside dashboard_bar
    center = overlay.dashboard_bar.geometry().center()
    ev = QMouseEvent(QEvent.MouseButtonPress, QPointF(center), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    overlay.mousePressEvent(ev)

    # Should still be visible
    assert overlay._is_overlay_visible is True


def test_overlay_escape_dismisses(qapp, tmp_path: Path):
    from PySide6.QtCore import Qt, QEvent
    from PySide6.QtGui import QKeyEvent

    cfg = ConfigManager(config_path=tmp_path / "settings.json")
    overlay = OverlayWindow(cfg)
    overlay.show_overlay()
    assert overlay._is_overlay_visible is True

    ev = QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
    overlay.keyPressEvent(ev)

    assert overlay._is_overlay_visible is False


def test_overlay_pinned_widget_mask(qapp, tmp_path: Path):
    cfg = ConfigManager(config_path=tmp_path / "settings.json")
    overlay = OverlayWindow(cfg)
    overlay.show_overlay()

    # Pin performance widget
    overlay._on_widget_pinned("performance", True)
    assert "performance" in overlay._pinned_widgets

    # Hide overlay
    overlay.hide_overlay()
    assert overlay._is_overlay_visible is False
    # Pinned widget remains visible
    assert overlay.widget_perf.isVisible() is True
    # Mask is active
    assert not overlay.mask().isEmpty()
