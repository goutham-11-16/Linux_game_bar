"""
Plugin Loader and Registry for the Linux Game Bar Widget SDK.
Discovers, validates, and loads third-party widget plugins implementing
Microsoft.Gaming.XboxGameBar contracts.
"""

import os
import sys
import inspect
import logging
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional, Type

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout
from linux_game_bar.ui.widget_base import WidgetBase
from linux_game_bar.sdk.widget import (
    XboxGameBarWidgetPlugin,
    GameBarWidgetPlugin,
    WidgetMetadata,
    WidgetContext,
)
from linux_game_bar.sdk.xbox_game_bar import (
    XboxGameBarWidget,
    XboxGameBarWidgetActivatedEventArgs,
    XboxGameBarDisplayMode,
)

logger = logging.getLogger("linux_game_bar.sdk.loader")


class PluginWidgetWrapper(WidgetBase):
    """
    Host container wrapping a third-party plugin inside the standard
    Linux Game Bar floating window frame, bridging the XboxGameBarWidget contract.
    """

    def __init__(self, plugin: XboxGameBarWidgetPlugin, parent: Optional[QWidget] = None):
        meta = plugin.METADATA
        super().__init__(
            widget_id=meta.id,
            title=meta.title,
            icon_str=meta.icon_name,
            parent=parent,
        )
        self.plugin = plugin

        # Create the 1:1 XboxGameBarWidget instance
        self.xbox_widget = XboxGameBarWidget(
            widget_id=meta.id,
            display_name=meta.title,
            app_extension_id=meta.id,
            host_wrapper=self,
            parent=self,
        )
        self.plugin.widget = self.xbox_widget

        # Forward bounds & constraints
        self.setMinimumSize(meta.min_width, meta.min_height)
        self.resize(meta.default_width, meta.default_height)
        self.xbox_widget.min_window_size = self.minimumSize()
        self.xbox_widget.max_window_size = self.maximumSize()

        # Connect click-through mode
        self.xbox_widget.click_through_enabled_changed.connect(self._on_click_through_changed)

        # Build plugin inner UI via on_navigated_to
        try:
            activation_args = XboxGameBarWidgetActivatedEventArgs(
                widget=self.xbox_widget,
                app_extension_id=meta.id,
                is_launch=True,
            )
            inner_ui = plugin.on_navigated_to(activation_args)
            if inner_ui:
                self.content_layout.addWidget(inner_ui)
        except Exception as e:
            logger.error(f"Error activating plugin {meta.id}: {e}", exc_info=True)

        self.pinned_changed.connect(self._on_pin_changed)
        self.geometry_changed.connect(self._on_geom_changed)

    def _on_click_through_changed(self, widget: Any, enabled: bool) -> None:
        """When pinned and click-through enabled, clicks pass through to the game underneath."""
        self.setAttribute(Qt.WA_TransparentForMouseEvents, enabled)

    def _on_pin_changed(self, wid: str, pinned: bool) -> None:
        self.xbox_widget._pinned = pinned
        self.xbox_widget.pinned_changed.emit(self.xbox_widget, pinned)
        try:
            self.plugin.on_pinned_changed(pinned)
        except Exception as e:
            logger.debug(f"Plugin {self.plugin.METADATA.id} on_pinned_changed error: {e}")

    def _on_geom_changed(self, wid: str, x: int, y: int, w: int, h: int) -> None:
        self.xbox_widget.set_window_bounds(x, y, w, h)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.xbox_widget.visible = True
        try:
            self.plugin.on_show()
        except Exception as e:
            logger.debug(f"Plugin {self.plugin.METADATA.id} on_show error: {e}")

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self.xbox_widget.visible = False
        try:
            self.plugin.on_hide()
        except Exception as e:
            logger.debug(f"Plugin {self.plugin.METADATA.id} on_hide error: {e}")


class PluginLoader:
    """Discovers and manages third-party Game Bar widget plugins."""

    def __init__(self, plugin_dirs: Optional[List[Path]] = None, host_config=None):
        if plugin_dirs is None:
            user_plugins = Path.home() / ".local" / "share" / "linux-game-bar" / "plugins"
            plugin_dirs = [user_plugins]
        self.plugin_dirs = [Path(p) for p in plugin_dirs]
        self.host_config = host_config
        self.loaded_plugins: Dict[str, XboxGameBarWidgetPlugin] = {}
        self.wrapped_widgets: Dict[str, PluginWidgetWrapper] = {}

    def ensure_directories(self) -> None:
        """Create plugin directories if they do not exist."""
        for d in self.plugin_dirs:
            d.mkdir(parents=True, exist_ok=True)

    def discover_and_load(self, parent_window: Optional[QWidget] = None) -> Dict[str, PluginWidgetWrapper]:
        """
        Scan all plugin directories, load valid plugins, and wrap them in WidgetBase.
        Returns a dictionary of widget_id -> PluginWidgetWrapper.
        """
        self.ensure_directories()

        for directory in self.plugin_dirs:
            if not directory.exists() or not directory.is_dir():
                continue

            for entry in directory.iterdir():
                if entry.is_dir():
                    candidate = entry / "plugin.py"
                    if not candidate.exists():
                        candidate = entry / "__init__.py"
                    if candidate.exists():
                        self._load_from_file(candidate, parent_window)
                elif entry.is_file() and entry.suffix == ".py":
                    self._load_from_file(entry, parent_window)

        return self.wrapped_widgets

    def _load_from_file(self, file_path: Path, parent_window: Optional[QWidget] = None) -> None:
        module_name = f"lgb_plugin_{file_path.stem}_{abs(hash(str(file_path)))}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, str(file_path))
            if not spec or not spec.loader:
                return

            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)

            for name, obj in inspect.getmembers(mod, inspect.isclass):
                if issubclass(obj, (XboxGameBarWidgetPlugin, GameBarWidgetPlugin)) and obj not in (
                    XboxGameBarWidgetPlugin,
                    GameBarWidgetPlugin,
                ):
                    meta = getattr(obj, "METADATA", None)
                    if not meta or not meta.id:
                        logger.warning(f"Plugin class {name} in {file_path} missing METADATA.id")
                        continue

                    if meta.id in self.wrapped_widgets:
                        logger.debug(f"Plugin {meta.id} already loaded, skipping.")
                        continue

                    ctx = WidgetContext(meta.id, self.host_config)
                    plugin_instance: XboxGameBarWidgetPlugin = obj(ctx)
                    plugin_instance.on_load()

                    wrapper = PluginWidgetWrapper(plugin_instance, parent=parent_window)
                    self.loaded_plugins[meta.id] = plugin_instance
                    self.wrapped_widgets[meta.id] = wrapper
                    logger.info(f"Successfully loaded Game Bar plugin: {meta.title} ({meta.id})")

        except Exception as e:
            logger.error(f"Failed to load plugin from {file_path}: {e}", exc_info=True)

    def reload_plugins(self, parent_window: Optional[QWidget] = None) -> Dict[str, PluginWidgetWrapper]:
        """Re-scans plugin directories and loads newly installed plugins."""
        return self.discover_and_load(parent_window=parent_window)
