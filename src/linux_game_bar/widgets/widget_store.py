"""
Widget Store and Package Manager UI for Linux Game Bar.
Allows users to install, browse, and uninstall community widgets
via GitHub repository URLs, local .zip files, and project folders.
"""

import os
import logging
from typing import Optional, Callable

from PySide6.QtCore import Qt, QSize, QThread, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QFrame,
    QScrollArea,
    QFileDialog,
)

from linux_game_bar.ui.widget_base import WidgetBase
from linux_game_bar.ui.theme import Theme
from linux_game_bar.ui import icons
from linux_game_bar.config_manager import ConfigManager
from linux_game_bar.sdk.installer import WidgetInstaller

logger = logging.getLogger("linux_game_bar.widgets.widget_store")


class InstallWorker(QThread):
    """Background worker to download and install widgets without freezing UI."""

    finished_install = Signal(bool, str, str)  # success, message, widget_id

    def __init__(self, source: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.source = source

    def run(self) -> None:
        try:
            success, msg, wid = WidgetInstaller.install(self.source)
            self.finished_install.emit(success, msg, wid or "")
        except Exception as ex:
            self.finished_install.emit(False, f"Error: {str(ex)}", "")


class WidgetStoreWidget(WidgetBase):
    """
    In-game Widget Store & Package Manager dialog matching Fluent UI design.
    """

    plugins_changed = Signal()

    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        on_plugins_changed: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__("widget_store", "WIDGET STORE", "plus", parent)
        self.config_manager = config_manager
        self.on_plugins_changed_callback = on_plugins_changed
        self.setMinimumSize(420, 540)
        self.resize(460, 580)

        self._worker: Optional[InstallWorker] = None
        self._build_ui()
        self.refresh_installed_list()

    def _build_ui(self) -> None:
        layout = self.content_layout
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(10)

        # Header Title & Subtitle
        header_box = QVBoxLayout()
        header_box.setSpacing(2)
        lbl_title = QLabel("COMMUNITY WIDGETS & STORE")
        lbl_title.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {Theme.ACCENT_GREEN}; background: transparent;")
        lbl_sub = QLabel("Install custom widgets created with the Linux Game Bar SDK.")
        lbl_sub.setStyleSheet("font-size: 11px; color: #A0A0A5; background: transparent;")
        header_box.addWidget(lbl_title)
        header_box.addWidget(lbl_sub)
        layout.addLayout(header_box)

        # -------------------------------------------------------------
        # Section 1: Install from GitHub / Git URL
        # -------------------------------------------------------------
        card_git = QFrame()
        card_git.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 4px;
            }}
        """)
        git_layout = QVBoxLayout(card_git)
        git_layout.setContentsMargins(8, 8, 8, 8)
        git_layout.setSpacing(6)

        lbl_git = QLabel("Install from GitHub / Git Repository")
        lbl_git.setStyleSheet("font-size: 11px; font-weight: 600; color: #FFFFFF; background: transparent;")
        git_layout.addWidget(lbl_git)

        git_input_row = QHBoxLayout()
        git_input_row.setSpacing(6)
        self.input_git_url = QLineEdit()
        self.input_git_url.setPlaceholderText("https://github.com/developer/my-custom-widget")
        self.input_git_url.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Theme.BG_INPUT};
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 5px 8px;
                font-size: 11px;
            }}
            QLineEdit:focus {{
                border-color: {Theme.ACCENT_GREEN};
            }}
        """)
        git_input_row.addWidget(self.input_git_url, 1)

        self.btn_install_git = QPushButton("Install")
        self.btn_install_git.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.ACCENT_GREEN};
                border: none;
                border-radius: 4px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 600;
                color: #FFFFFF;
            }}
            QPushButton:hover {{
                background-color: #149c53;
            }}
        """)
        self.btn_install_git.clicked.connect(self._on_install_git_clicked)
        git_input_row.addWidget(self.btn_install_git)
        git_layout.addLayout(git_input_row)

        layout.addWidget(card_git)

        # -------------------------------------------------------------
        # Section 2: Install from Local ZIP / File
        # -------------------------------------------------------------
        card_file = QFrame()
        card_file.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 4px;
            }}
        """)
        file_layout = QVBoxLayout(card_file)
        file_layout.setContentsMargins(8, 8, 8, 8)
        file_layout.setSpacing(6)

        lbl_file = QLabel("Install from Local ZIP or Folder")
        lbl_file.setStyleSheet("font-size: 11px; font-weight: 600; color: #FFFFFF; background: transparent;")
        file_layout.addWidget(lbl_file)

        file_input_row = QHBoxLayout()
        file_input_row.setSpacing(6)
        self.input_file_path = QLineEdit()
        self.input_file_path.setPlaceholderText("/path/to/widget.zip or plugin folder")
        self.input_file_path.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Theme.BG_INPUT};
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 5px 8px;
                font-size: 11px;
            }}
            QLineEdit:focus {{
                border-color: {Theme.ACCENT_GREEN};
            }}
        """)
        file_input_row.addWidget(self.input_file_path, 1)

        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 11px;
                color: #CCCCCC;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.15);
                color: #FFFFFF;
            }}
        """)
        self.btn_browse.clicked.connect(self._on_browse_file_clicked)
        file_input_row.addWidget(self.btn_browse)

        self.btn_install_file = QPushButton("Install")
        self.btn_install_file.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.ACCENT_GREEN};
                border: none;
                border-radius: 4px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 600;
                color: #FFFFFF;
            }}
            QPushButton:hover {{
                background-color: #149c53;
            }}
        """)
        self.btn_install_file.clicked.connect(self._on_install_file_clicked)
        file_input_row.addWidget(self.btn_install_file)

        file_layout.addLayout(file_input_row)
        layout.addWidget(card_file)

        # -------------------------------------------------------------
        # Status / Progress Feedback
        # -------------------------------------------------------------
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(3)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 0)  # Marquee animation during install
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: transparent;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: {Theme.ACCENT_GREEN};
            }}
        """)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Ready to install widgets.")
        self.lbl_status.setStyleSheet("font-size: 11px; color: #888888; background: transparent;")
        layout.addWidget(self.lbl_status)

        # -------------------------------------------------------------
        # Section 3: Installed Community Widgets
        # -------------------------------------------------------------
        lbl_installed = QLabel("Installed Community Widgets")
        lbl_installed.setStyleSheet("font-size: 12px; font-weight: 600; color: #FFFFFF; margin-top: 4px; background: transparent;")
        layout.addWidget(lbl_installed)

        # Scrollable list of installed plugins
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 6px;
            }}
        """)

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(6, 6, 6, 6)
        self.list_layout.setSpacing(6)
        self.list_layout.setAlignment(Qt.AlignTop)

        self.scroll_area.setWidget(self.list_container)
        layout.addWidget(self.scroll_area, 1)

    def _on_install_git_clicked(self) -> None:
        url = self.input_git_url.text().strip()
        if not url:
            self.lbl_status.setText("Please enter a valid Git or GitHub repository URL.")
            self.lbl_status.setStyleSheet("font-size: 11px; color: #EF5350;")
            return
        self._start_install(url)

    def _on_browse_file_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Widget ZIP or Python Plugin",
            "",
            "Widget Packages (*.zip *.py);;All Files (*)",
        )
        if file_path:
            self.input_file_path.setText(file_path)

    def _on_install_file_clicked(self) -> None:
        path = self.input_file_path.text().strip()
        if not path:
            self.lbl_status.setText("Please specify a ZIP archive or plugin file path.")
            self.lbl_status.setStyleSheet("font-size: 11px; color: #EF5350;")
            return
        self._start_install(path)

    def _start_install(self, source: str) -> None:
        self.btn_install_git.setEnabled(False)
        self.btn_install_file.setEnabled(False)
        self.progress_bar.show()
        self.lbl_status.setText(f"Installing widget from {source}...")
        self.lbl_status.setStyleSheet("font-size: 11px; color: #CCCCCC;")

        self._worker = InstallWorker(source, parent=self)
        self._worker.finished_install.connect(self._on_install_completed)
        self._worker.start()

    def _on_install_completed(self, success: bool, message: str, widget_id: str) -> None:
        self.btn_install_git.setEnabled(True)
        self.btn_install_file.setEnabled(True)
        self.progress_bar.hide()

        if success:
            self.lbl_status.setText(message)
            self.lbl_status.setStyleSheet(f"font-size: 11px; color: {Theme.ACCENT_GREEN}; font-weight: 500;")
            self.input_git_url.clear()
            self.input_file_path.clear()
            self.refresh_installed_list()
            self.plugins_changed.emit()
            if self.on_plugins_changed_callback:
                self.on_plugins_changed_callback()
        else:
            self.lbl_status.setText(message)
            self.lbl_status.setStyleSheet("font-size: 11px; color: #EF5350;")

    def refresh_installed_list(self) -> None:
        """Populate list of installed community widgets."""
        # Clear existing items
        while self.list_layout.count() > 0:
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        plugins = WidgetInstaller.list_installed_plugins()
        if not plugins:
            lbl_empty = QLabel("No third-party widgets installed yet.\nInstall one using a GitHub URL or ZIP file above!")
            lbl_empty.setAlignment(Qt.AlignCenter)
            lbl_empty.setStyleSheet("color: #777777; font-size: 11px; padding: 20px;")
            self.list_layout.addWidget(lbl_empty)
            return

        for p in plugins:
            row = QFrame()
            row.setStyleSheet(f"""
                QFrame {{
                    background-color: {Theme.BG_CARD};
                    border: 1px solid {Theme.BORDER_SUBTLE};
                    border-radius: 4px;
                    padding: 4px 6px;
                }}
            """)
            r_layout = QHBoxLayout(row)
            r_layout.setContentsMargins(6, 4, 6, 4)
            r_layout.setSpacing(8)

            # Icon
            icon_lbl = QLabel()
            icon_lbl.setPixmap(icons.get_pixmap("package", color="#CCCCCC", size=18))
            r_layout.addWidget(icon_lbl)

            # Title & ID
            info_col = QVBoxLayout()
            info_col.setSpacing(1)
            p_title = QLabel(p["title"])
            p_title.setStyleSheet("font-size: 12px; font-weight: 600; color: #FFFFFF;")
            p_id = QLabel(p["id"])
            p_id.setStyleSheet("font-size: 10px; color: #888888;")
            info_col.addWidget(p_title)
            info_col.addWidget(p_id)
            r_layout.addLayout(info_col, 1)

            # Uninstall button
            btn_del = QPushButton("Uninstall")
            btn_del.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: 1px solid rgba(239, 83, 80, 0.4);
                    border-radius: 3px;
                    padding: 3px 8px;
                    font-size: 10px;
                    color: #EF5350;
                }
                QPushButton:hover {
                    background-color: rgba(239, 83, 80, 0.2);
                    color: #FF7777;
                }
            """)
            btn_del.clicked.connect(lambda _, wid=p["id"]: self._on_uninstall_clicked(wid))
            r_layout.addWidget(btn_del)

            self.list_layout.addWidget(row)

    def _on_uninstall_clicked(self, widget_id: str) -> None:
        ok, msg = WidgetInstaller.uninstall_plugin(widget_id)
        if ok:
            self.lbl_status.setText(msg)
            self.lbl_status.setStyleSheet(f"font-size: 11px; color: {Theme.ACCENT_GREEN};")
            self.refresh_installed_list()
            self.plugins_changed.emit()
            if self.on_plugins_changed_callback:
                self.on_plugins_changed_callback()
        else:
            self.lbl_status.setText(msg)
            self.lbl_status.setStyleSheet("font-size: 11px; color: #EF5350;")
