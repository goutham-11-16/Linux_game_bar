"""
AutoTyper Widget Plugin for Microsoft.Gaming.XboxGameBar on Linux.
Demonstrates packaging Auto-Typer as a 1:1 SDK plugin extension.
"""

from PySide6.QtWidgets import QWidget
from linux_game_bar.sdk import (
    XboxGameBarWidgetPlugin,
    WidgetMetadata,
    XboxGameBarWidgetActivatedEventArgs,
)
from linux_game_bar.widgets.autotyper import AutoTyperWidget


class AutoTyperPlugin(XboxGameBarWidgetPlugin):
    METADATA = WidgetMetadata(
        id="com.microsoft.gaming.autotyper",
        title="AUTO TYPER",
        version="1.0.0",
        author="Goutham",
        description="Automated typing, snippet management, and macro execution for games.",
        icon_name="keyboard",
        default_width=380,
        default_height=520,
        min_width=340,
        min_height=420,
    )

    def on_navigated_to(self, args: XboxGameBarWidgetActivatedEventArgs) -> QWidget:
        self.widget = args.widget
        # Return core AutoTyperWidget instance
        autotyper = AutoTyperWidget(parent=None)
        return autotyper
