"""Notes widget with local SQLite persistence, search, and auto-save."""

import os
import sqlite3
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QFrame,
)

from linux_game_bar.ui.widget_base import WidgetBase
from linux_game_bar.ui.theme import Theme

logger = logging.getLogger("linux_game_bar.notes")


@dataclass
class Note:
    id: int
    title: str
    content: str
    created_at: str
    updated_at: str
    is_pinned: bool = False


class NotesDatabase:
    """Manages SQLite storage for local notes in ~/.local/share/linux-game-bar/notes.db."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path:
            self.db_path = db_path
        else:
            data_home = os.environ.get("XDG_DATA_HOME")
            base = Path(data_home) if data_home else Path.home() / ".local" / "share"
            self.db_path = base / "linux-game-bar" / "notes.db"

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_pinned INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    def get_all_notes(self) -> List[Note]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, title, content, created_at, updated_at, is_pinned 
                FROM notes 
                ORDER BY is_pinned DESC, updated_at DESC
            """)
            rows = cursor.fetchall()
            return [Note(r[0], r[1], r[2], r[3], r[4], bool(r[5])) for r in rows]

    def create_note(self, title: str = "New Note", content: str = "") -> Note:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO notes (title, content, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (title, content),
            )
            note_id = cursor.lastrowid
            conn.commit()
            return Note(note_id, title, content, "", "", False)

    def update_note(self, note_id: int, title: str, content: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE notes SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (title, content, note_id),
            )
            conn.commit()

    def delete_note(self, note_id: int) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            conn.commit()


class NotesWidget(WidgetBase):
    """Local gaming notepad widget."""

    def __init__(self, parent: QWidget = None):
        super().__init__("notes", "NOTES", "notes", parent)
        self.setMinimumSize(360, 440)
        self.resize(380, 480)

        self.db = NotesDatabase()
        self.current_note: Optional[Note] = None
        self._all_notes: List[Note] = []

        self._build_ui()

        # Auto-save debounce timer (1 second)
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self._save_current_note)

        self._load_notes()

    def _build_ui(self) -> None:
        # Search Box & New Button
        top_row = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search notes...")
        self.search_box.textChanged.connect(self._filter_notes)
        top_row.addWidget(self.search_box)

        self.btn_new = QPushButton("+ New")
        self.btn_new.setProperty("class", "accent")
        self.btn_new.clicked.connect(self._create_new_note)
        top_row.addWidget(self.btn_new)
        self.content_layout.addLayout(top_row)

        # Note List (Compact)
        self.list_notes = QListWidget()
        self.list_notes.setFixedHeight(110)
        self.list_notes.setStyleSheet(f"""
            QListWidget {{
                background-color: {Theme.BG_CARD};
                border-radius: 6px;
                padding: 4px;
            }}
        """)
        self.list_notes.itemClicked.connect(self._on_note_selected)
        self.content_layout.addWidget(self.list_notes)

        # Editor Area
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Note Title")
        self.title_input.setStyleSheet("font-weight: 700; font-size: 14px; padding: 6px;")
        self.title_input.textChanged.connect(self._on_text_modified)
        self.content_layout.addWidget(self.title_input)

        self.editor = QTextEdit()
        self.editor.setPlaceholderText("Write gaming tips, coords, strategies, codes...")
        self.editor.textChanged.connect(self._on_text_modified)
        self.content_layout.addWidget(self.editor, 1)

        # Footer with Save Status & Delete Button
        foot_row = QHBoxLayout()
        self.lbl_status = QLabel("Ready")
        self.lbl_status.setStyleSheet("font-size: 11px; color: #707075;")
        foot_row.addWidget(self.lbl_status)
        foot_row.addStretch()

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #A0A0A5;
                border: none;
                font-size: 12px;
            }
            QPushButton:hover {
                color: #E81123;
            }
        """)
        self.btn_delete.clicked.connect(self._delete_current_note)
        foot_row.addWidget(self.btn_delete)
        self.content_layout.addLayout(foot_row)

    def _load_notes(self) -> None:
        self._all_notes = self.db.get_all_notes()
        self._populate_list(self._all_notes)
        if self._all_notes:
            self._select_note(self._all_notes[0])
        else:
            self._create_new_note()

    def _populate_list(self, notes: List[Note]) -> None:
        self.list_notes.clear()
        for n in notes:
            item = QListWidgetItem(f"📄 {n.title}")
            item.setData(Qt.UserRole, n)
            self.list_notes.addItem(item)

    def _filter_notes(self, query: str) -> None:
        q = query.strip().lower()
        if not q:
            self._populate_list(self._all_notes)
            return
        filtered = [n for n in self._all_notes if q in n.title.lower() or q in n.content.lower()]
        self._populate_list(filtered)

    def _on_note_selected(self, item: QListWidgetItem) -> None:
        # Flush any pending changes to current note
        self._save_current_note()
        note: Note = item.data(Qt.UserRole)
        self._select_note(note)

    def _select_note(self, note: Note) -> None:
        self.current_note = note
        self.title_input.blockSignals(True)
        self.editor.blockSignals(True)

        self.title_input.setText(note.title)
        self.editor.setPlainText(note.content)

        self.title_input.blockSignals(False)
        self.editor.blockSignals(False)
        self.lbl_status.setText("Saved")

    def _create_new_note(self) -> None:
        self._save_current_note()
        new_note = self.db.create_note("Untitled Note", "")
        self._all_notes.insert(0, new_note)
        self._populate_list(self._all_notes)
        self._select_note(new_note)

    def _on_text_modified(self) -> None:
        self.lbl_status.setText("Saving...")
        self.save_timer.start(1000)

    def _save_current_note(self) -> None:
        if not self.current_note:
            return
        title = self.title_input.text().strip() or "Untitled Note"
        content = self.editor.toPlainText()

        self.db.update_note(self.current_note.id, title, content)
        self.current_note.title = title
        self.current_note.content = content
        self.lbl_status.setText("Saved")

        # Update item in list
        for i in range(self.list_notes.count()):
            item = self.list_notes.item(i)
            n = item.data(Qt.UserRole)
            if n and n.id == self.current_note.id:
                item.setText(f"📄 {title}")
                break

    def _delete_current_note(self) -> None:
        if not self.current_note:
            return

        res = QMessageBox.question(
            self,
            "Delete Note",
            f"Are you sure you want to delete note '{self.current_note.title}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if res == QMessageBox.Yes:
            self.db.delete_note(self.current_note.id)
            self._all_notes = [n for n in self._all_notes if n.id != self.current_note.id]
            self._populate_list(self._all_notes)
            if self._all_notes:
                self._select_note(self._all_notes[0])
            else:
                self._create_new_note()
