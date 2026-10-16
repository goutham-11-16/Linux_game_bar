"""
Linux Game Bar Widget SDK.
Provides standard interfaces and classes for developers to build custom widgets
that integrate directly into the Linux Game Bar overlay ecosystem, implementing the
official Microsoft.Gaming.XboxGameBar contracts.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QObject, Signal

from linux_game_bar.sdk.xbox_game_bar import (
    XboxGameBarWidget,
    XboxGameBarWidgetActivatedEventArgs,
    XboxGameBarDisplayMode,
    XboxGameBarWindowState,
    XboxGameBarRecordingState,
    XboxGameBarTheme,
    XboxGameBarAppTarget,
)


@dataclass
class WidgetMetadata:
    """Metadata describing a Linux Game Bar widget plugin."""

    id: str  # Unique identifier (e.g. "com.example.spotify_controls")
    title: str  # Display title in Widget Menu and Header (e.g. "SPOTIFY")
    version: str = "1.0.0"
    author: str = "Unknown"
    description: str = ""
    icon_name: str = "plugin"  # SVG template name or standard icon
    default_width: int = 340
    default_height: int = 400
    min_width: int = 260
    min_height: int = 200
    permissions: list[str] = field(default_factory=list)


class WidgetContext(QObject):
    """
    Context services provided by the Linux Game Bar host to a widget plugin.
    Includes persistent settings storage, notifications, and host event hooks.
    """

    notification_requested = Signal(str, str)  # title, message

    def __init__(self, plugin_id: str, host_config: Optional[Any] = None):
        super().__init__()
        self.plugin_id = plugin_id
        self._host_config = host_config
        self._plugin_settings: Dict[str, Any] = {}

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Retrieve a persistent plugin configuration value."""
        if self._host_config:
            full_key = f"plugins.{self.plugin_id}.{key}"
            return self._host_config.get(full_key, default)
        return self._plugin_settings.get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        """Store a persistent plugin configuration value."""
        if self._host_config:
            full_key = f"plugins.{self.plugin_id}.{key}"
            self._host_config.set(full_key, value)
        else:
            self._plugin_settings[key] = value

    def show_notification(self, title: str, message: str) -> None:
        """Request host to display an on-screen toast notification."""
        self.notification_requested.emit(title, message)


class XboxGameBarWidgetPlugin(QObject):
    """
    Base class for Linux Game Bar widget plugins matching Microsoft.Gaming.XboxGameBar.

    Developers override on_navigated_to(args) or build_widget() to construct their UI.
    args.widget gives direct access to the XboxGameBarWidget instance and its events.

    Example:
    ```python
    from linux_game_bar.sdk import XboxGameBarWidgetPlugin, WidgetMetadata, XboxGameBarWidgetActivatedEventArgs
    from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

    class MyWidget(XboxGameBarWidgetPlugin):
        METADATA = WidgetMetadata(
            id="com.developer.my_widget",
            title="MY WIDGET",
        )

        def on_navigated_to(self, args: XboxGameBarWidgetActivatedEventArgs) -> QWidget:
            self.widget = args.widget
            self.widget.pinned_changed.connect(self.on_pinned_changed)

            container = QWidget()
            layout = QVBoxLayout(container)
            layout.addWidget(QLabel("Hello from Xbox Game Bar widget!"))
            return container
    ```
    """

    METADATA: WidgetMetadata = WidgetMetadata(
        id="base_plugin",
        title="BASE PLUGIN",
    )

    def __init__(self, context: WidgetContext):
        super().__init__()
        self.context = context
        self.widget: Optional[XboxGameBarWidget] = None
        self._widget_ui: Optional[QWidget] = None

    def on_load(self) -> None:
        """Called once when the plugin is discovered and loaded by the Game Bar host."""
        pass

    def on_unload(self) -> None:
        """Called when the plugin is unloaded or Game Bar daemon is stopping."""
        pass

    def on_navigated_to(self, args: XboxGameBarWidgetActivatedEventArgs) -> Optional[QWidget]:
        """
        Windows Xbox Game Bar standard activation callback.
        Receives XboxGameBarWidgetActivatedEventArgs containing args.widget.
        """
        return self.build_widget()

    def build_widget(self) -> Optional[QWidget]:
        """
        Build and return the internal QWidget content for this widget.
        The host automatically wraps this content in a standard WidgetBase frame.
        """
        return None

    def on_show(self) -> None:
        """Called when the widget becomes visible on screen."""
        if self.widget:
            self.widget.visible = True

    def on_hide(self) -> None:
        """Called when the widget is hidden."""
        if self.widget:
            self.widget.visible = False

    def on_pinned_changed(self, is_pinned: bool) -> None:
        """Called when the user pins or unpins this widget."""
        pass


# Backward compatibility alias
GameBarWidgetPlugin = XboxGameBarWidgetPlugin
