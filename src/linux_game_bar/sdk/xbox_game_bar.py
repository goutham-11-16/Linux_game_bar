"""
1:1 Linux implementation of Microsoft.Gaming.XboxGameBar (v7.3.2607010).
Reverse-engineered from official Microsoft.Gaming.XboxGameBar.winmd.
"""

from enum import IntEnum
from typing import Optional, Tuple, Callable, Any
from PySide6.QtCore import QObject, Signal, QSize, QRect


class XboxGameBarDisplayMode(IntEnum):
    """Corresponds to Microsoft.Gaming.XboxGameBar.XboxGameBarDisplayMode."""
    Foreground = 0  # Game Bar overlay is active and receiving input
    Pinned = 1      # Game Bar is dismissed; widget remains pinned to the screen


class XboxGameBarWindowState(IntEnum):
    """Corresponds to Microsoft.Gaming.XboxGameBar.XboxGameBarWindowState."""
    Restored = 0
    Minimized = 1
    Maximized = 2


class XboxGameBarRecordingState(IntEnum):
    """Corresponds to Microsoft.Gaming.XboxGameBar.XboxGameBarRecordingState."""
    Stopped = 0
    Recording = 1
    Paused = 2


class XboxGameBarTheme(IntEnum):
    Dark = 0
    Light = 1


class XboxGameBarAppTarget:
    """Corresponds to Microsoft.Gaming.XboxGameBar.XboxGameBarAppTarget."""

    def __init__(
        self,
        title: str = "Active Application",
        process_id: int = 0,
        is_game: bool = True,
        is_fullscreen: bool = False,
        aum_id: str = "",
    ):
        self._title = title
        self._process_id = process_id
        self._is_game = is_game
        self._is_fullscreen = is_fullscreen
        self._aum_id = aum_id

    @property
    def title(self) -> str:
        return self._title

    @property
    def process_id(self) -> int:
        return self._process_id

    @property
    def is_game(self) -> bool:
        return self._is_game

    @property
    def is_fullscreen(self) -> bool:
        return self._is_fullscreen

    @property
    def aum_id(self) -> str:
        return self._aum_id


class XboxGameBarWidgetCloseRequestedEventArgs:
    """Corresponds to Microsoft.Gaming.XboxGameBar.XboxGameBarWidgetCloseRequestedEventArgs."""

    def __init__(self):
        self.handled: bool = False
        self._deferred: bool = False

    def get_deferral(self) -> Callable[[], None]:
        self._deferred = True
        return lambda: setattr(self, "_deferred", False)


class XboxGameBarWidgetNotificationManager(QObject):
    """Corresponds to Microsoft.Gaming.XboxGameBar.XboxGameBarWidgetNotificationManager."""

    notification_sent = Signal(str, str, str)  # title, content, icon_path

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

    def show_notification_async(self, title: str, content: str, icon_path: Optional[str] = None) -> None:
        """Post a rich game notification through Game Bar."""
        self.notification_sent.emit(title, content, icon_path or "")


class XboxGameBarWidgetRecordingManager(QObject):
    """Corresponds to Microsoft.Gaming.XboxGameBar.XboxGameBarWidgetRecordingManager."""

    recording_state_changed = Signal(object, int)  # manager, XboxGameBarRecordingState

    def __init__(self, capture_service=None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._capture_service = capture_service
        self._state: XboxGameBarRecordingState = XboxGameBarRecordingState.Stopped

    @property
    def recording_state(self) -> XboxGameBarRecordingState:
        if self._capture_service and hasattr(self._capture_service, "is_recording"):
            return (
                XboxGameBarRecordingState.Recording
                if self._capture_service.is_recording
                else XboxGameBarRecordingState.Stopped
            )
        return self._state

    def start_recording_async(self) -> bool:
        if self._capture_service:
            success, _ = self._capture_service.start_recording()
            if success:
                self._state = XboxGameBarRecordingState.Recording
                self.recording_state_changed.emit(self, self._state)
            return success
        self._state = XboxGameBarRecordingState.Recording
        self.recording_state_changed.emit(self, self._state)
        return True

    def stop_recording_async(self) -> bool:
        if self._capture_service:
            success, _ = self._capture_service.stop_recording()
            self._state = XboxGameBarRecordingState.Stopped
            self.recording_state_changed.emit(self, self._state)
            return success
        self._state = XboxGameBarRecordingState.Stopped
        self.recording_state_changed.emit(self, self._state)
        return True

    def is_timeframe_recording_enabled_async(self) -> bool:
        """Returns True if background rolling replay buffer is supported and enabled."""
        return False


class XboxGameBarWidget(QObject):
    """
    1:1 implementation of Microsoft.Gaming.XboxGameBar.XboxGameBarWidget.
    Represents the host contract and lifecycle for a widget window.
    """

    # Events / Signals matching Windows XboxGameBar exactly
    pinned_changed = Signal(object, bool)                       # widget, is_pinned
    favorited_changed = Signal(object, bool)                    # widget, is_favorited
    visible_changed = Signal(object, bool)                      # widget, is_visible
    game_bar_display_mode_changed = Signal(object, int)         # widget, XboxGameBarDisplayMode
    window_state_changed = Signal(object, int)                  # widget, XboxGameBarWindowState
    window_bounds_changed = Signal(object, int, int, int, int)  # widget, x, y, width, height
    settings_clicked = Signal(object)                           # widget
    close_requested = Signal(object, object)                    # widget, XboxGameBarWidgetCloseRequestedEventArgs
    click_through_enabled_changed = Signal(object, bool)        # widget, enabled
    requested_opacity_changed = Signal(object, float)           # widget, opacity

    def __init__(
        self,
        widget_id: str,
        display_name: str,
        app_extension_id: str = "",
        host_wrapper: Optional[QObject] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._id = widget_id
        self._display_name = display_name
        self._app_extension_id = app_extension_id or widget_id
        self._host_wrapper = host_wrapper

        # Property backings
        self._favorited: bool = True
        self._pinned: bool = False
        self._visible: bool = True
        self._display_mode: XboxGameBarDisplayMode = XboxGameBarDisplayMode.Foreground
        self._window_state: XboxGameBarWindowState = XboxGameBarWindowState.Restored
        self._bounds: QRect = QRect(50, 90, 340, 420)
        self._min_size: QSize = QSize(240, 180)
        self._max_size: QSize = QSize(1920, 1080)
        self._click_through_enabled: bool = False
        self._pinning_supported: bool = True
        self._settings_supported: bool = False
        self._horizontal_resize_supported: bool = True
        self._vertical_resize_supported: bool = True
        self._requested_opacity: float = 1.0
        self._requested_theme: XboxGameBarTheme = XboxGameBarTheme.Dark

        # Sub-managers
        self.notification_manager = XboxGameBarWidgetNotificationManager(self)
        self.recording_manager = XboxGameBarWidgetRecordingManager(parent=self)
        self.app_target = XboxGameBarAppTarget()

    # --- Properties ---

    @property
    def id(self) -> str:
        return self._id

    @property
    def display_name(self) -> str:
        return self._display_name

    @property
    def app_extension_id(self) -> str:
        return self._app_extension_id

    @property
    def favorited(self) -> bool:
        return self._favorited

    @favorited.setter
    def favorited(self, value: bool) -> None:
        if self._favorited != value:
            self._favorited = value
            self.favorited_changed.emit(self, value)

    @property
    def pinned(self) -> bool:
        return self._pinned

    @pinned.setter
    def pinned(self, value: bool) -> None:
        if self._pinned != value:
            self._pinned = value
            if self._host_wrapper and hasattr(self._host_wrapper, "set_pinned"):
                self._host_wrapper.set_pinned(value)
            self.pinned_changed.emit(self, value)

    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        if self._visible != value:
            self._visible = value
            self.visible_changed.emit(self, value)

    @property
    def game_bar_display_mode(self) -> XboxGameBarDisplayMode:
        return self._display_mode

    def set_game_bar_display_mode(self, mode: XboxGameBarDisplayMode) -> None:
        if self._display_mode != mode:
            self._display_mode = mode
            self.game_bar_display_mode_changed.emit(self, int(mode))

    @property
    def window_state(self) -> XboxGameBarWindowState:
        return self._window_state

    @property
    def window_bounds(self) -> QRect:
        return self._bounds

    def set_window_bounds(self, x: int, y: int, w: int, h: int) -> None:
        self._bounds = QRect(x, y, w, h)
        self.window_bounds_changed.emit(self, x, y, w, h)

    @property
    def min_window_size(self) -> QSize:
        return self._min_size

    @min_window_size.setter
    def min_window_size(self, size: QSize) -> None:
        self._min_size = size
        if self._host_wrapper:
            self._host_wrapper.setMinimumSize(size)

    @property
    def max_window_size(self) -> QSize:
        return self._max_size

    @max_window_size.setter
    def max_window_size(self, size: QSize) -> None:
        self._max_size = size
        if self._host_wrapper:
            self._host_wrapper.setMaximumSize(size)

    @property
    def click_through_enabled(self) -> bool:
        return self._click_through_enabled

    @click_through_enabled.setter
    def click_through_enabled(self, enabled: bool) -> None:
        if self._click_through_enabled != enabled:
            self._click_through_enabled = enabled
            self.click_through_enabled_changed.emit(self, enabled)

    @property
    def pinning_supported(self) -> bool:
        return self._pinning_supported

    @pinning_supported.setter
    def pinning_supported(self, supported: bool) -> None:
        self._pinning_supported = supported

    @property
    def settings_supported(self) -> bool:
        return self._settings_supported

    @settings_supported.setter
    def settings_supported(self, supported: bool) -> None:
        self._settings_supported = supported

    @property
    def horizontal_resize_supported(self) -> bool:
        return self._horizontal_resize_supported

    @horizontal_resize_supported.setter
    def horizontal_resize_supported(self, supported: bool) -> None:
        self._horizontal_resize_supported = supported

    @property
    def vertical_resize_supported(self) -> bool:
        return self._vertical_resize_supported

    @vertical_resize_supported.setter
    def vertical_resize_supported(self, supported: bool) -> None:
        self._vertical_resize_supported = supported

    @property
    def requested_opacity(self) -> float:
        return self._requested_opacity

    @requested_opacity.setter
    def requested_opacity(self, opacity: float) -> None:
        clamped = max(0.1, min(1.0, opacity))
        if self._requested_opacity != clamped:
            self._requested_opacity = clamped
            if self._host_wrapper and hasattr(self._host_wrapper, "setWindowOpacity"):
                self._host_wrapper.setWindowOpacity(clamped)
            self.requested_opacity_changed.emit(self, clamped)

    @property
    def requested_theme(self) -> XboxGameBarTheme:
        return self._requested_theme

    # --- Methods ---

    def close(self) -> None:
        args = XboxGameBarWidgetCloseRequestedEventArgs()
        self.close_requested.emit(self, args)
        if not args.handled and self._host_wrapper and hasattr(self._host_wrapper, "close_widget"):
            self._host_wrapper.close_widget()

    def close_async(self) -> None:
        self.close()

    def activate_async(self) -> None:
        if self._host_wrapper and hasattr(self._host_wrapper, "show"):
            self._host_wrapper.show()
            self._host_wrapper.raise_()

    def minimize_async(self) -> None:
        self._window_state = XboxGameBarWindowState.Minimized
        if self._host_wrapper and hasattr(self._host_wrapper, "hide"):
            self._host_wrapper.hide()
        self.window_state_changed.emit(self, int(self._window_state))

    def restore_async(self) -> None:
        self._window_state = XboxGameBarWindowState.Restored
        if self._host_wrapper and hasattr(self._host_wrapper, "show"):
            self._host_wrapper.show()
        self.window_state_changed.emit(self, int(self._window_state))


class XboxGameBarWidgetActivatedEventArgs:
    """Corresponds to Microsoft.Gaming.XboxGameBar.XboxGameBarWidgetActivatedEventArgs."""

    def __init__(self, widget: XboxGameBarWidget, app_extension_id: str = "", is_launch: bool = True):
        self.widget = widget
        self.app_extension_id = app_extension_id or widget.app_extension_id
        self.is_launch_activation = is_launch
