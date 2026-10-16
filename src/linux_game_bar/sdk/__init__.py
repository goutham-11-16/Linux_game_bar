"""
Linux Game Bar Widget Software Development Kit (SDK).

1:1 Linux implementation of Microsoft.Gaming.XboxGameBar (NuGet 7.3.2607010).
Allows third-party developers to build, package, and distribute custom
widgets for the Linux Game Bar desktop overlay.
"""

from linux_game_bar.sdk.xbox_game_bar import (
    XboxGameBarWidget,
    XboxGameBarWidgetActivatedEventArgs,
    XboxGameBarWidgetCloseRequestedEventArgs,
    XboxGameBarWidgetNotificationManager,
    XboxGameBarWidgetRecordingManager,
    XboxGameBarAppTarget,
    XboxGameBarDisplayMode,
    XboxGameBarWindowState,
    XboxGameBarRecordingState,
    XboxGameBarTheme,
)
from linux_game_bar.sdk.widget import (
    XboxGameBarWidgetPlugin,
    GameBarWidgetPlugin,
    WidgetMetadata,
    WidgetContext,
)
from linux_game_bar.sdk.loader import (
    PluginLoader,
    PluginWidgetWrapper,
)
from linux_game_bar.sdk.installer import WidgetInstaller

__all__ = [
    # 1:1 Microsoft.Gaming.XboxGameBar classes
    "XboxGameBarWidget",
    "XboxGameBarWidgetActivatedEventArgs",
    "XboxGameBarWidgetCloseRequestedEventArgs",
    "XboxGameBarWidgetNotificationManager",
    "XboxGameBarWidgetRecordingManager",
    "XboxGameBarAppTarget",
    "XboxGameBarDisplayMode",
    "XboxGameBarWindowState",
    "XboxGameBarRecordingState",
    "XboxGameBarTheme",
    # Plugin developer classes
    "XboxGameBarWidgetPlugin",
    "GameBarWidgetPlugin",
    "WidgetMetadata",
    "WidgetContext",
    "PluginLoader",
    "PluginWidgetWrapper",
    "WidgetInstaller",
]
