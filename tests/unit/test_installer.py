"""Unit tests for WidgetInstaller and WidgetStoreWidget."""

import os
import shutil
import zipfile
import pytest
from pathlib import Path
from PySide6.QtWidgets import QApplication

from linux_game_bar.sdk.installer import WidgetInstaller
from linux_game_bar.widgets.widget_store import WidgetStoreWidget


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def custom_plugins_dir(tmp_path, monkeypatch):
    p_dir = tmp_path / "test_plugins"
    p_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(WidgetInstaller, "PLUGINS_DIR", p_dir)
    return p_dir


def test_install_from_path_valid(custom_plugins_dir):
    # Use existing sample plugin
    sample_src = Path("examples/plugins/sample_widget")
    assert sample_src.exists()

    ok, msg, wid = WidgetInstaller.install_from_path(str(sample_src))
    assert ok is True
    assert wid == "com.example.quick_links"
    assert (custom_plugins_dir / "com.example.quick_links").exists()
    assert (custom_plugins_dir / "com.example.quick_links" / "plugin.py").exists()


def test_install_from_path_invalid(custom_plugins_dir, tmp_path):
    empty_dir = tmp_path / "empty_widget"
    empty_dir.mkdir()
    ok, msg, wid = WidgetInstaller.install_from_path(str(empty_dir))
    assert ok is False
    assert wid is None


def test_install_from_zip(custom_plugins_dir, tmp_path):
    sample_src = Path("examples/plugins/sample_widget")
    zip_path = tmp_path / "test_widget.zip"

    # Create zip archive of quick_links
    with zipfile.ZipFile(zip_path, "w") as zf:
        for root, _, files in os.walk(sample_src):
            for file in files:
                fpath = Path(root) / file
                zf.write(fpath, arcname=fpath.name)

    ok, msg, wid = WidgetInstaller.install_from_zip(str(zip_path))
    assert ok is True
    assert wid == "com.example.quick_links"
    assert (custom_plugins_dir / "com.example.quick_links").exists()


def test_list_and_uninstall_plugin(custom_plugins_dir):
    sample_src = Path("examples/plugins/sample_widget")
    WidgetInstaller.install_from_path(str(sample_src))

    plugins = WidgetInstaller.list_installed_plugins()
    assert len(plugins) == 1
    assert plugins[0]["id"] == "com.example.quick_links"
    assert plugins[0]["title"] == "QUICK LINKS"

    # Uninstall
    ok, msg = WidgetInstaller.uninstall_plugin("com.example.quick_links")
    assert ok is True
    assert not (custom_plugins_dir / "com.example.quick_links").exists()
    assert len(WidgetInstaller.list_installed_plugins()) == 0


def test_widget_store_ui(qapp, custom_plugins_dir):
    store = WidgetStoreWidget()
    assert store.widget_id == "widget_store"
    assert store.widget_title == "WIDGET STORE"
    assert store.input_git_url is not None
    assert store.btn_install_git is not None
    assert store.btn_install_file is not None

    # Refresh list runs cleanly
    store.refresh_installed_list()
