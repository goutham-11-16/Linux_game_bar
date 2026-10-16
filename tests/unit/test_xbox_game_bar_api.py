"""Unit tests verifying 1:1 Microsoft.Gaming.XboxGameBar API contracts."""

import pytest
from PySide6.QtCore import QSize, QRect
from linux_game_bar.sdk import (
    XboxGameBarWidget,
    XboxGameBarWidgetActivatedEventArgs,
    XboxGameBarWidgetNotificationManager,
    XboxGameBarWidgetRecordingManager,
    XboxGameBarAppTarget,
    XboxGameBarDisplayMode,
    XboxGameBarWindowState,
    XboxGameBarRecordingState,
    XboxGameBarWidgetPlugin,
    WidgetMetadata,
    WidgetContext,
    PluginWidgetWrapper,
)


def test_xbox_game_bar_widget_properties_and_signals(qapp):
    widget = XboxGameBarWidget("com.test.widget", "TEST WIDGET")

    # Initial state
    assert widget.id == "com.test.widget"
    assert widget.display_name == "TEST WIDGET"
    assert widget.favorited is True
    assert widget.pinned is False
    assert widget.visible is True
    assert widget.game_bar_display_mode == XboxGameBarDisplayMode.Foreground
    assert widget.window_state == XboxGameBarWindowState.Restored
    assert widget.click_through_enabled is False
    assert widget.requested_opacity == 1.0

    # Signal event tracking
    signals_fired = []
    widget.pinned_changed.connect(lambda w, p: signals_fired.append(("pinned", p)))
    widget.favorited_changed.connect(lambda w, f: signals_fired.append(("favorited", f)))
    widget.visible_changed.connect(lambda w, v: signals_fired.append(("visible", v)))
    widget.game_bar_display_mode_changed.connect(lambda w, m: signals_fired.append(("mode", m)))
    widget.click_through_enabled_changed.connect(lambda w, c: signals_fired.append(("clickthrough", c)))
    widget.requested_opacity_changed.connect(lambda w, o: signals_fired.append(("opacity", o)))

    # Property mutations triggering signals
    widget.pinned = True
    assert ("pinned", True) in signals_fired

    widget.favorited = False
    assert ("favorited", False) in signals_fired

    widget.visible = False
    assert ("visible", False) in signals_fired

    widget.set_game_bar_display_mode(XboxGameBarDisplayMode.Pinned)
    assert ("mode", int(XboxGameBarDisplayMode.Pinned)) in signals_fired

    widget.click_through_enabled = True
    assert ("clickthrough", True) in signals_fired

    widget.requested_opacity = 0.75
    assert ("opacity", 0.75) in signals_fired


def test_xbox_game_bar_notification_manager(qapp):
    widget = XboxGameBarWidget("com.test.widget", "TEST")
    notifs = []
    widget.notification_manager.notification_sent.connect(
        lambda t, c, i: notifs.append((t, c, i))
    )

    widget.notification_manager.show_notification_async("Game Alert", "Level Completed", "/tmp/icon.png")
    assert len(notifs) == 1
    assert notifs[0] == ("Game Alert", "Level Completed", "/tmp/icon.png")


def test_xbox_game_bar_recording_manager(qapp):
    widget = XboxGameBarWidget("com.test.widget", "TEST")
    rec_states = []
    widget.recording_manager.recording_state_changed.connect(
        lambda m, s: rec_states.append(s)
    )

    assert widget.recording_manager.recording_state == XboxGameBarRecordingState.Stopped
    widget.recording_manager.start_recording_async()
    assert widget.recording_manager.recording_state == XboxGameBarRecordingState.Recording
    assert XboxGameBarRecordingState.Recording in rec_states

    widget.recording_manager.stop_recording_async()
    assert widget.recording_manager.recording_state == XboxGameBarRecordingState.Stopped
    assert XboxGameBarRecordingState.Stopped in rec_states


def test_xbox_game_bar_app_target():
    target = XboxGameBarAppTarget(title="Doom Eternal", process_id=1234, is_game=True, is_fullscreen=True)
    assert target.title == "Doom Eternal"
    assert target.process_id == 1234
    assert target.is_game is True
    assert target.is_fullscreen is True


def test_xbox_game_bar_plugin_activation(qapp):
    activated_widget = None

    class CustomXboxPlugin(XboxGameBarWidgetPlugin):
        METADATA = WidgetMetadata(id="com.test.xbox_plugin", title="CUSTOM XBOX")

        def on_navigated_to(self, args: XboxGameBarWidgetActivatedEventArgs):
            nonlocal activated_widget
            activated_widget = args.widget
            from PySide6.QtWidgets import QLabel
            return QLabel("Xbox Content")

    ctx = WidgetContext("com.test.xbox_plugin")
    plugin = CustomXboxPlugin(ctx)
    wrapper = PluginWidgetWrapper(plugin)

    assert activated_widget is not None
    assert activated_widget.id == "com.test.xbox_plugin"
    assert activated_widget.display_name == "CUSTOM XBOX"
    assert wrapper.xbox_widget is activated_widget
