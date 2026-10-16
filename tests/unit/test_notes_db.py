"""Unit tests for NotesDatabase SQLite CRUD."""

from pathlib import Path
from linux_game_bar.widgets.notes import NotesDatabase


def test_notes_database_crud(tmp_path: Path):
    db_file = tmp_path / "test_notes.db"
    db = NotesDatabase(db_path=db_file)

    # 1. Create note
    note = db.create_note("Boss Strategy", "Aim for glowing weak spot on left shoulder.")
    assert note.id is not None
    assert note.title == "Boss Strategy"

    # 2. Read notes
    notes = db.get_all_notes()
    assert len(notes) == 1
    assert notes[0].title == "Boss Strategy"
    assert "weak spot" in notes[0].content

    # 3. Update note
    db.update_note(note.id, "Boss Strategy (Updated)", "Use electric arrows first.")
    updated_notes = db.get_all_notes()
    assert updated_notes[0].title == "Boss Strategy (Updated)"
    assert "electric arrows" in updated_notes[0].content

    # 4. Delete note
    db.delete_note(note.id)
    assert len(db.get_all_notes()) == 0
