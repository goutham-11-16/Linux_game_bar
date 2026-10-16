"""
Linux Game Bar Widget Software Development Kit (SDK).

Allows third-party developers to easily build, package, and distribute custom
widgets for the Linux Game Bar desktop overlay.
"""

from linux_game_bar.sdk.widget import (
    GameBarWidgetPlugin,
    WidgetMetadata,
    WidgetContext,
)
from linux_game_bar.sdk.loader import (
    PluginLoader,
    PluginWidgetWrapper,
)

__all__ = [
    "GameBarWidgetPlugin",
    "WidgetMetadata",
    "WidgetContext",
    "PluginLoader",
    "PluginWidgetWrapper",
]
