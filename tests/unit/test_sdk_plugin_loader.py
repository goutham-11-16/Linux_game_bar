"""Unit tests for Linux Game Bar Widget SDK and PluginLoader."""

import pytest
from pathlib import Path
from linux_game_bar.sdk import (
    GameBarWidgetPlugin,
    WidgetMetadata,
    WidgetContext,
    PluginLoader,
    PluginWidgetWrapper,
)


def test_widget_metadata_structure():
    meta = WidgetMetadata(
        id="test.plugin",
        title="TEST PLUGIN",
        version="1.2.3",
        author="Tester",
        description="Test description",
        icon_name="plugin",
        default_width=320,
        default_height=400,
    )
    assert meta.id == "test.plugin"
    assert meta.title == "TEST PLUGIN"
    assert meta.version == "1.2.3"
    assert meta.icon_name == "plugin"


def test_widget_context_settings():
    ctx = WidgetContext("test.plugin")
    assert ctx.get_setting("custom_key", "default_val") == "default_val"
    ctx.set_setting("custom_key", "new_val")
    assert ctx.get_setting("custom_key") == "new_val"


def test_plugin_loader_discovers_and_loads(qapp):
    example_dir = Path(__file__).parent.parent.parent / "examples" / "plugins"
    loader = PluginLoader(plugin_dirs=[example_dir])
    loaded = loader.discover_and_load()

    assert "com.example.quick_links" in loaded
    wrapper = loaded["com.example.quick_links"]
    assert isinstance(wrapper, PluginWidgetWrapper)
    assert wrapper.widget_id == "com.example.quick_links"
    assert wrapper.widget_title == "QUICK LINKS"
    assert wrapper.plugin.METADATA.author == "Community Developer"


def test_plugin_lifecycle_events(qapp):
    events = []

    class DummyPlugin(GameBarWidgetPlugin):
        METADATA = WidgetMetadata(id="test.dummy", title="DUMMY")

        def on_show(self):
            events.append("show")

        def on_hide(self):
            events.append("hide")

        def on_pinned_changed(self, pinned: bool):
            events.append(f"pinned:{pinned}")

        def build_widget(self):
            from PySide6.QtWidgets import QLabel
            return QLabel("Dummy Content")

    ctx = WidgetContext("test.dummy")
    plugin = DummyPlugin(ctx)
    wrapper = PluginWidgetWrapper(plugin)

    wrapper.show()
    assert "show" in events

    wrapper.set_pinned(True)
    assert "pinned:True" in events

    wrapper.hide()
    assert "hide" in events
