"""Integration test for GnomeShortcutManager."""

from linux_game_bar.platform.gnome_integration import GnomeShortcutManager


def test_gnome_shortcut_manager_query(tmp_path):
    mgr = GnomeShortcutManager(backup_file=tmp_path / "shortcut_backup.json")
    assert mgr.is_available() is True
    bindings = mgr.get_custom_bindings()
    assert isinstance(bindings, list)


def test_conflict_detection(tmp_path):
    mgr = GnomeShortcutManager(backup_file=tmp_path / "shortcut_backup.json")
    # Conflict check with a non-existent random shortcut should return None
    conflict = mgr.check_conflict("<Control><Alt><Super>F12")
    assert conflict is None
