"""Application, game, and browser launcher widget with custom application dialog."""

import os
import re
import shlex
import shutil
import logging
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from PySide6.QtCore import Qt, QProcess, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QTabWidget,
    QDialog,
    QFileDialog,
    QCheckBox,
    QMessageBox,
    QFrame,
)

from linux_game_bar.ui.widget_base import WidgetBase
from linux_game_bar.ui.theme import Theme
from linux_game_bar.config_manager import ConfigManager

logger = logging.getLogger("linux_game_bar.launcher")


@dataclass
class AppEntry:
    id: str
    name: str
    exec_cmd: str
    icon: str
    categories: List[str] = field(default_factory=list)
    is_game: bool = False
    is_custom: bool = False
    is_favorite: bool = False
    args: str = ""


class AddAppDialog(QDialog):
    """Dialog for adding custom executable or game entries."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Application to Game Bar")
        self.resize(440, 360)
        self.setStyleSheet(f"background-color: #1a1a1e; color: #ffffff;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        lbl_title = QLabel("➕ Add Application or Custom Game")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #ffffff;")
        layout.addWidget(lbl_title)

        # Name
        layout.addWidget(QLabel("Display Name:"))
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("e.g. Cyberpunk 2077 or Custom Script")
        layout.addWidget(self.input_name)

        # Executable Path
        layout.addWidget(QLabel("Executable Path or Command:"))
        row_exec = QHBoxLayout()
        self.input_exec = QLineEdit()
        self.input_exec.setPlaceholderText("/usr/bin/... or ~/.local/bin/...")
        row_exec.addWidget(self.input_exec)

        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse_exec)
        row_exec.addWidget(btn_browse)
        layout.addLayout(row_exec)

        # Arguments
        layout.addWidget(QLabel("Optional Arguments:"))
        self.input_args = QLineEdit()
        self.input_args.setPlaceholderText("e.g. -fullscreen -novid")
        layout.addWidget(self.input_args)

        # Options
        self.chk_favorite = QCheckBox("Add to Favorites")
        self.chk_favorite.setChecked(True)
        layout.addWidget(self.chk_favorite)

        self.chk_game = QCheckBox("Categorize as Game")
        self.chk_game.setChecked(True)
        layout.addWidget(self.chk_game)

        layout.addStretch()

        # Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_save = QPushButton("Save Application")
        btn_save.setProperty("class", "accent")
        btn_save.clicked.connect(self._validate_and_accept)
        btn_box.addWidget(btn_save)

        layout.addLayout(btn_box)

    def _browse_exec(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Executable File", "/usr/bin")
        if path:
            self.input_exec.setText(path)
            if not self.input_name.text().strip():
                self.input_name.setText(Path(path).stem.capitalize())

    def _validate_and_accept(self) -> None:
        name = self.input_name.text().strip()
        exe = self.input_exec.text().strip()
        if not name:
            QMessageBox.warning(self, "Invalid Name", "Please provide an application name.")
            return
        if not exe:
            QMessageBox.warning(self, "Invalid Path", "Please specify an executable path or command.")
            return

        # Check if executable exists or is on PATH
        resolved = shutil.which(exe) or (exe if os.path.isfile(exe) and os.access(exe, os.X_OK) else None)
        if not resolved:
            res = QMessageBox.question(
                self,
                "Executable Not Found",
                f"The command '{exe}' was not found on your system PATH.\nSave anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if res != QMessageBox.Yes:
                return

        self.accept()

    def get_entry(self) -> AppEntry:
        name = self.input_name.text().strip()
        exe = self.input_exec.text().strip()
        args = self.input_args.text().strip()
        cmd = f"{exe} {args}".strip()
        return AppEntry(
            id=f"custom_{int(os.times().elapsed * 1000)}",
            name=name,
            exec_cmd=cmd,
            icon="application-x-executable",
            is_game=self.chk_game.isChecked(),
            is_custom=True,
            is_favorite=self.chk_favorite.isChecked(),
            args=args,
        )


class DesktopScanner:
    """Discovers installed system applications and browsers."""

    @staticmethod
    def scan_applications() -> List[AppEntry]:
        apps: Dict[str, AppEntry] = {}
        paths = [
            Path("/usr/share/applications"),
            Path("/usr/local/share/applications"),
            Path.home() / ".local" / "share" / "applications",
        ]

        for p in paths:
            if not p.exists():
                continue
            for dentry in p.glob("*.desktop"):
                entry = DesktopScanner._parse_desktop_file(dentry)
                if entry and entry.name:
                    apps[entry.id] = entry

        return sorted(list(apps.values()), key=lambda a: a.name.lower())

    @staticmethod
    def _parse_desktop_file(filepath: Path) -> Optional[AppEntry]:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                in_desktop_entry = False
                name = ""
                exec_cmd = ""
                icon = "application-x-executable"
                categories = []
                no_display = False
                app_type = ""

                for line in f:
                    line = line.strip()
                    if line == "[Desktop Entry]":
                        in_desktop_entry = True
                        continue
                    elif line.startswith("["):
                        in_desktop_entry = False

                    if not in_desktop_entry:
                        continue

                    if line.startswith("Type="):
                        app_type = line.split("=", 1)[1]
                    elif line.startswith("Name=") and not name:
                        name = line.split("=", 1)[1]
                    elif line.startswith("Exec="):
                        exec_cmd = line.split("=", 1)[1]
                    elif line.startswith("Icon="):
                        icon = line.split("=", 1)[1]
                    elif line.startswith("Categories="):
                        categories = [c for c in line.split("=", 1)[1].split(";") if c]
                    elif line.startswith("NoDisplay="):
                        no_display = line.split("=", 1)[1].lower() == "true"

                if app_type == "Application" and not no_display and exec_cmd:
                    clean_exec = re.sub(r"%\w", "", exec_cmd).strip()
                    is_game = "Game" in categories or "game" in filepath.name.lower()
                    return AppEntry(
                        id=filepath.name,
                        name=name,
                        exec_cmd=clean_exec,
                        icon=icon,
                        categories=categories,
                        is_game=is_game,
                    )
        except Exception:
            pass
        return None

    @staticmethod
    def detect_browsers() -> List[AppEntry]:
        """Discover installed web browsers for instant launching."""
        known_browsers = [
            ("Brave Browser", "brave-browser", "brave"),
            ("Firefox", "firefox", "firefox"),
            ("Google Chrome", "google-chrome", "google-chrome"),
            ("Chromium", "chromium", "chromium"),
            ("Microsoft Edge", "microsoft-edge", "microsoft-edge"),
        ]
        browsers = []
        for name, exe, icon in known_browsers:
            path = shutil.which(exe) or shutil.which(exe.split("-")[0])
            if path:
                browsers.append(AppEntry(
                    id=f"browser_{exe}",
                    name=name,
                    exec_cmd=path,
                    icon=icon,
                    categories=["Network", "WebBrowser"],
                ))
        return browsers


class LauncherWidget(WidgetBase):
    """Full-featured application, game, and browser launcher."""

    def __init__(self, config_manager: Optional[ConfigManager] = None, parent: QWidget = None):
        super().__init__("launcher", "LAUNCHER", "launcher", parent)
        self.setMinimumSize(420, 500)
        self.resize(480, 540)

        self.config_manager = config_manager or ConfigManager()
        self.all_apps: List[AppEntry] = []
        self.custom_apps: List[AppEntry] = []
        self.installed_browsers: List[AppEntry] = []

        self._build_ui()
        self._load_custom_apps()
        self._load_applications()

    def _build_ui(self) -> None:
        # Search Box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search installed games, apps, and browsers...")
        self.search_box.setFixedHeight(36)
        self.search_box.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Theme.BG_INPUT};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 13px;
                color: #ffffff;
            }}
            QLineEdit:focus {{
                border-color: {Theme.ACCENT_GREEN};
            }}
        """)
        self.search_box.textChanged.connect(self._filter_list)
        self.content_layout.addWidget(self.search_box)

        # Quick Browsers Row
        self.browser_bar = QWidget()
        b_lay = QHBoxLayout(self.browser_bar)
        b_lay.setContentsMargins(0, 0, 0, 0)
        b_lay.setSpacing(6)
        self.lbl_browser_title = QLabel("Browsers:")
        self.lbl_browser_title.setStyleSheet("font-size: 11px; font-weight: 600; color: #A0A0A5;")
        b_lay.addWidget(self.lbl_browser_title)
        self.browser_btn_box = QHBoxLayout()
        b_lay.addLayout(self.browser_btn_box)
        b_lay.addStretch()
        self.content_layout.addWidget(self.browser_bar)

        # Tabs: Favorites, Games, All, Custom
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 8px;
                background-color: {Theme.BG_CARD};
            }}
            QTabBar::tab {{
                background-color: transparent;
                color: {Theme.TEXT_SECONDARY};
                padding: 6px 14px;
                font-weight: 600;
                border-radius: 4px;
            }}
            QTabBar::tab:selected {{
                color: #ffffff;
                background-color: rgba(255, 255, 255, 0.08);
                border-bottom: 2px solid {Theme.ACCENT_GREEN};
            }}
        """)

        self.list_favs = QListWidget()
        self.list_favs.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tabs.addTab(self.list_favs, "⭐ Favorites")

        self.list_games = QListWidget()
        self.list_games.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tabs.addTab(self.list_games, "🎮 Games")

        self.list_all = QListWidget()
        self.list_all.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tabs.addTab(self.list_all, "All Apps")

        self.list_custom = QListWidget()
        self.list_custom.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tabs.addTab(self.list_custom, "Custom")

        self.content_layout.addWidget(self.tabs, 1)

        # Launch Status Banner
        self.lbl_status = QLabel("Ready to launch.")
        self.lbl_status.setStyleSheet("font-size: 11px; color: #707075; padding: 0 4px;")
        self.content_layout.addWidget(self.lbl_status)

        # Action Buttons Row
        btn_row = QHBoxLayout()
        self.btn_launch = QPushButton("▶ Launch Selected")
        self.btn_launch.setProperty("class", "accent")
        self.btn_launch.setCursor(Qt.PointingHandCursor)
        self.btn_launch.clicked.connect(self._launch_current_selected)
        btn_row.addWidget(self.btn_launch)

        self.btn_fav = QPushButton("⭐ Pin/Unpin Fav")
        self.btn_fav.setCursor(Qt.PointingHandCursor)
        self.btn_fav.clicked.connect(self._toggle_favorite_selected)
        btn_row.addWidget(self.btn_fav)

        self.btn_add_custom = QPushButton("➕ Add Custom...")
        self.btn_add_custom.setCursor(Qt.PointingHandCursor)
        self.btn_add_custom.clicked.connect(self._open_add_dialog)
        btn_row.addWidget(self.btn_add_custom)

        self.btn_remove_custom = QPushButton("🗑 Remove")
        self.btn_remove_custom.setCursor(Qt.PointingHandCursor)
        self.btn_remove_custom.clicked.connect(self._remove_custom_selected)
        btn_row.addWidget(self.btn_remove_custom)

        self.content_layout.addLayout(btn_row)

    def _load_applications(self) -> None:
        self.all_apps = DesktopScanner.scan_applications()
        self.installed_browsers = DesktopScanner.detect_browsers()
        self._populate_browser_bar()
        self._populate_lists()

    def _populate_browser_bar(self) -> None:
        # Clear existing buttons
        while self.browser_btn_box.count():
            item = self.browser_btn_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for b in self.installed_browsers:
            btn = QPushButton(f"🌐 {b.name}")
            btn.setFixedHeight(26)
            btn.setStyleSheet("padding: 2px 8px; font-size: 11px;")
            btn.clicked.connect(lambda _, app=b: self._execute_app(app))
            self.browser_btn_box.addWidget(btn)

    def _load_custom_apps(self) -> None:
        saved = self.config_manager.get("launcher.custom_entries", [])
        self.custom_apps = []
        for d in saved:
            self.custom_apps.append(AppEntry(
                id=d.get("id", "custom"),
                name=d.get("name", "Custom App"),
                exec_cmd=d.get("exec_cmd", ""),
                icon=d.get("icon", "application-x-executable"),
                is_game=d.get("is_game", True),
                is_custom=True,
                is_favorite=d.get("is_favorite", False),
            ))

    def _save_custom_apps(self) -> None:
        serialized = [
            {
                "id": a.id,
                "name": a.name,
                "exec_cmd": a.exec_cmd,
                "icon": a.icon,
                "is_game": a.is_game,
                "is_custom": True,
                "is_favorite": a.is_favorite,
            }
            for a in self.custom_apps
        ]
        self.config_manager.set("launcher.custom_entries", serialized)

    def _populate_lists(self, query: str = "") -> None:
        self.list_favs.clear()
        self.list_games.clear()
        self.list_all.clear()
        self.list_custom.clear()

        q = query.strip().lower()
        fav_ids = set(self.config_manager.get("launcher.favorites", ["steam", "discord", "lutris", "heroic"]))

        combined = self.custom_apps + self.all_apps

        for app in combined:
            if q and q not in app.name.lower() and q not in app.exec_cmd.lower():
                continue

            is_fav = app.id in fav_ids or any(f in app.exec_cmd.lower() for f in fav_ids) or app.is_favorite

            # Item label
            icon_str = "⭐ " if is_fav else ("🎮 " if app.is_game else "📦 ")
            item = QListWidgetItem(f"{icon_str}{app.name}")
            item.setData(Qt.UserRole, app)
            self.list_all.addItem(item)

            if is_fav:
                fav_item = QListWidgetItem(f"⭐ {app.name}")
                fav_item.setData(Qt.UserRole, app)
                self.list_favs.addItem(fav_item)

            if app.is_game:
                game_item = QListWidgetItem(f"🎮 {app.name}")
                game_item.setData(Qt.UserRole, app)
                self.list_games.addItem(game_item)

            if app.is_custom:
                cust_item = QListWidgetItem(f"🛠️ {app.name}")
                cust_item.setData(Qt.UserRole, app)
                self.list_custom.addItem(cust_item)

    def _filter_list(self, query: str) -> None:
        self._populate_lists(query)

    def _get_active_list(self) -> QListWidget:
        idx = self.tabs.currentIndex()
        if idx == 0:
            return self.list_favs
        elif idx == 1:
            return self.list_games
        elif idx == 2:
            return self.list_all
        else:
            return self.list_custom

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        app: AppEntry = item.data(Qt.UserRole)
        if app:
            self._execute_app(app)

    def _launch_current_selected(self) -> None:
        cur_list = self._get_active_list()
        item = cur_list.currentItem()
        if item:
            app: AppEntry = item.data(Qt.UserRole)
            if app:
                self._execute_app(app)
        else:
            self.lbl_status.setText("Select an application first.")

    def _execute_app(self, app: AppEntry) -> None:
        """Execute command safely without shell interpolation."""
        try:
            args = shlex.split(app.exec_cmd)
            if not args:
                self.lbl_status.setText(f"Invalid command for '{app.name}'")
                return

            exe = args[0]
            if not shutil.which(exe) and not os.path.isfile(exe):
                self.lbl_status.setText(f"Error: Executable '{exe}' not found.")
                QMessageBox.warning(self, "Launch Error", f"The executable '{exe}' was not found on your system.")
                return

            logger.info(f"Launching app detached: {args}")
            QProcess.startDetached(exe, args[1:])
            self.lbl_status.setText(f"✓ Launched '{app.name}' successfully.")
        except Exception as e:
            logger.error(f"Error launching {app.name}: {e}")
            self.lbl_status.setText(f"Launch failed: {e}")
            QMessageBox.warning(self, "Launch Failed", f"Could not launch '{app.name}':\n{e}")

    def _toggle_favorite_selected(self) -> None:
        cur_list = self._get_active_list()
        item = cur_list.currentItem()
        if not item:
            return

        app: AppEntry = item.data(Qt.UserRole)
        if not app:
            return

        fav_ids = list(self.config_manager.get("launcher.favorites", []))
        if app.id in fav_ids:
            fav_ids.remove(app.id)
            app.is_favorite = False
            self.lbl_status.setText(f"Unpinned '{app.name}' from favorites.")
        else:
            fav_ids.append(app.id)
            app.is_favorite = True
            self.lbl_status.setText(f"Pinned '{app.name}' to favorites.")

        self.config_manager.set("launcher.favorites", fav_ids)
        self._populate_lists(self.search_box.text())

    def _open_add_dialog(self) -> None:
        dlg = AddAppDialog(self)
        if dlg.exec() == QDialog.Accepted:
            new_entry = dlg.get_entry()
            self.custom_apps.append(new_entry)
            if new_entry.is_favorite:
                fav_ids = list(self.config_manager.get("launcher.favorites", []))
                if new_entry.id not in fav_ids:
                    fav_ids.append(new_entry.id)
                    self.config_manager.set("launcher.favorites", fav_ids, auto_save=False)
            self._save_custom_apps()
            self._populate_lists()
            self.lbl_status.setText(f"Added custom application '{new_entry.name}'")

    def _remove_custom_selected(self) -> None:
        cur_list = self._get_active_list()
        item = cur_list.currentItem()
        if not item:
            return
        app: AppEntry = item.data(Qt.UserRole)
        if not app or not app.is_custom:
            self.lbl_status.setText("Only custom user-added entries can be removed.")
            return

        res = QMessageBox.question(
            self,
            "Remove Application",
            f"Remove '{app.name}' from custom applications?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if res == QMessageBox.Yes:
            self.custom_apps = [a for a in self.custom_apps if a.id != app.id]
            self._save_custom_apps()
            self._populate_lists()
            self.lbl_status.setText(f"Removed '{app.name}'")
