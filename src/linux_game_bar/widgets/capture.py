"""Capture widget providing screenshot gallery, image clipboard, and screen recording."""

import os
import time
import subprocess
import logging
from pathlib import Path
from typing import Optional, List

from PySide6.QtCore import Qt, QTimer, QSize, QMimeData, QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QGuiApplication, QPixmap, QImage, QClipboard, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QDialog,
    QScrollArea,
    QMessageBox,
    QFrame,
    QFileDialog,
    QCheckBox,
)

from linux_game_bar.ui.widget_base import WidgetBase
from linux_game_bar.ui.theme import Theme
from linux_game_bar.ui import icons
from linux_game_bar.config_manager import ConfigManager
from linux_game_bar.platform.portals import CaptureService

logger = logging.getLogger("linux_game_bar.capture_ui")


class ScreenshotViewerDialog(QDialog):
    """Full-resolution preview dialog for a captured screenshot."""

    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.setWindowTitle(f"Preview: {Path(image_path).name}")
        self.resize(800, 560)
        self.setStyleSheet(f"background-color: #1a1a1e; color: #ffffff;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header info
        hdr = QHBoxLayout()
        lbl_name = QLabel(Path(image_path).name)
        lbl_name.setStyleSheet("font-size: 14px; font-weight: 600; color: #ffffff;")
        hdr.addWidget(lbl_name)
        hdr.addStretch()

        self.btn_copy = QPushButton("Copy Image")
        self.btn_copy.setIcon(icons.get_icon("copy", color="#FFFFFF", size=16))
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.ACCENT_GREEN};
                color: #ffffff;
                font-weight: 600;
                font-size: 12px;
                padding: 6px 14px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {Theme.ACCENT_GREEN_HOVER};
            }}
        """)
        self.btn_copy.clicked.connect(self._copy_image)
        hdr.addWidget(self.btn_copy)

        btn_close = QPushButton("Close")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #2e2e34;
                color: #ffffff;
                border-radius: 6px;
                padding: 6px 12px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            QPushButton:hover {
                background-color: #3b3b44;
            }
        """)
        btn_close.clicked.connect(self.accept)
        hdr.addWidget(btn_close)
        layout.addLayout(hdr)

        # Scroll area for large image
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 6px;")

        self.lbl_image = QLabel()
        self.lbl_image.setAlignment(Qt.AlignCenter)
        pix = QPixmap(image_path)
        if not pix.isNull():
            self.lbl_image.setPixmap(pix.scaled(760, 480, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.lbl_image.setText("Failed to load image file.")
        scroll.setWidget(self.lbl_image)
        layout.addWidget(scroll, 1)

    def _copy_image(self) -> None:
        img = QImage(self.image_path)
        if not img.isNull():
            mime = QMimeData()
            mime.setImageData(img)
            ba = QByteArray()
            buf = QBuffer(ba)
            buf.open(QIODevice.WriteOnly)
            img.save(buf, "PNG")
            buf.close()
            mime.setData("image/png", ba)
            mime.setData("image/bmp", ba)
            QApplication.clipboard().setMimeData(mime, QClipboard.Clipboard)
            self.btn_copy.setText("✓ Copied!")
            QTimer.singleShot(1500, lambda: self.btn_copy.setText("Copy Image"))


class CaptureWidget(WidgetBase):
    """Xbox-inspired screenshot and screen recording capture dashboard."""

    def __init__(self, config_manager=None, parent: QWidget = None):
        if isinstance(config_manager, QWidget) and parent is None:
            parent = config_manager
            config_manager = None
        super().__init__("capture", "CAPTURE", "camera", parent)

        if config_manager is not None:
            self.config_manager = config_manager
        elif parent and hasattr(parent, "config_manager"):
            self.config_manager = parent.config_manager
        else:
            self.config_manager = ConfigManager()

        self.setMinimumSize(340, 440)
        self.resize(360, 480)

        self.service = CaptureService()
        self.active_screenshot_path: Optional[str] = None
        self._gallery_paths: List[str] = []
        self._mic_enabled: bool = False

        self._build_ui()
        self._refresh_gallery()

        # Recording timer
        self.rec_timer = QTimer(self)
        self.rec_timer.timeout.connect(self._update_rec_timer)

    def _build_ui(self) -> None:
        # 1. Xbox 4-Button Action Row Container
        card_actions = QFrame()
        card_actions.setObjectName("cardActions")
        card_actions.setStyleSheet(f"""
            QFrame#cardActions {{
                background-color: {Theme.BG_CARD};
                border-radius: 8px;
                border: 1px solid {Theme.BORDER_SUBTLE};
            }}
        """)
        vbox_act = QVBoxLayout(card_actions)
        vbox_act.setContentsMargins(12, 12, 12, 12)
        vbox_act.setSpacing(10)

        # Action Buttons Layout (4 round Xbox buttons)
        row_btns = QHBoxLayout()
        row_btns.setSpacing(10)
        row_btns.setAlignment(Qt.AlignCenter)

        # 1. Record Last 30s (Replay)
        self.btn_replay = QPushButton()
        self.btn_replay.setFixedSize(40, 40)
        self.btn_replay.setIconSize(QSize(20, 20))
        self.btn_replay.setIcon(icons.get_icon("replay", color="#D0D0D0", size=20))
        self.btn_replay.setToolTip("Record that (Last 30 seconds)")
        self.btn_replay.setCursor(Qt.PointingHandCursor)
        self._apply_round_button_style(self.btn_replay)
        self.btn_replay.clicked.connect(self._on_replay_clicked)
        row_btns.addWidget(self.btn_replay)

        # 2. Take Screenshot (Camera)
        self.btn_capture = QPushButton()
        self.btn_capture.setFixedSize(40, 40)
        self.btn_capture.setIconSize(QSize(20, 20))
        self.btn_capture.setIcon(icons.get_icon("camera", color="#FFFFFF", active_color="#107C41", size=20))
        self.btn_capture.setToolTip("Take screenshot")
        self.btn_capture.setCursor(Qt.PointingHandCursor)
        self._apply_round_button_style(self.btn_capture, highlight=True)
        self.btn_capture.clicked.connect(self._take_screenshot)
        row_btns.addWidget(self.btn_capture)

        # 3. Record (Circle Dot)
        self.btn_rec_toggle = QPushButton()
        self.btn_rec_toggle.setFixedSize(40, 40)
        self.btn_rec_toggle.setIconSize(QSize(20, 20))
        self.btn_rec_toggle.setIcon(icons.get_icon("record", color="#E81123", size=20))
        self.btn_rec_toggle.setToolTip("Start recording")
        self.btn_rec_toggle.setCursor(Qt.PointingHandCursor)
        self._apply_round_button_style(self.btn_rec_toggle)
        self.btn_rec_toggle.clicked.connect(self._toggle_recording)
        row_btns.addWidget(self.btn_rec_toggle)

        # 4. Mic Toggle while recording
        self.btn_mic = QPushButton()
        self.btn_mic.setFixedSize(40, 40)
        self.btn_mic.setIconSize(QSize(20, 20))
        self.btn_mic.setIcon(icons.get_icon("mic", color="#D0D0D0", size=20))
        self.btn_mic.setToolTip("Turn mic on/off while recording")
        self.btn_mic.setCursor(Qt.PointingHandCursor)
        self._apply_round_button_style(self.btn_mic)
        self.btn_mic.clicked.connect(self._toggle_mic)
        row_btns.addWidget(self.btn_mic)

        # 5. Open Folder
        self.btn_folder = QPushButton()
        self.btn_folder.setFixedSize(40, 40)
        self.btn_folder.setIconSize(QSize(18, 18))
        self.btn_folder.setIcon(icons.get_icon("folder", color="#D0D0D0", size=18))
        self.btn_folder.setToolTip("See my captures (Open folder)")
        self.btn_folder.setCursor(Qt.PointingHandCursor)
        self._apply_round_button_style(self.btn_folder)
        self.btn_folder.clicked.connect(self._open_captures_folder)
        row_btns.addWidget(self.btn_folder)

        vbox_act.addLayout(row_btns)

        # Clean Background capture mode toggle
        self.chk_clean_bg = QCheckBox("Hide Game Bar while capturing")
        self.chk_clean_bg.setToolTip("When checked, Game Bar temporarily hides so only the background game is captured. Uncheck for instant silent capture without closing the Game Bar.")
        self.chk_clean_bg.setStyleSheet("""
            QCheckBox {
                font-size: 11px;
                color: #A0A0A5;
                background: transparent;
                spacing: 6px;
            }
        """)
        self.chk_clean_bg.setChecked(self.config_manager.get("capture.clean_background_capture", False))
        self.chk_clean_bg.toggled.connect(self._on_clean_bg_toggled)
        vbox_act.addWidget(self.chk_clean_bg)

        # Recording Status Row
        self.rec_status_bar = QWidget()
        self.rec_status_bar.setVisible(False)
        rec_lay = QHBoxLayout(self.rec_status_bar)
        rec_lay.setContentsMargins(0, 0, 0, 0)
        self.lbl_rec_dot = QLabel("● RECORDING")
        self.lbl_rec_dot.setStyleSheet(f"font-size: 11px; font-weight: 800; color: {Theme.COLOR_DANGER};")
        rec_lay.addWidget(self.lbl_rec_dot)
        rec_lay.addStretch()
        self.lbl_rec_timer = QLabel("00:00")
        self.lbl_rec_timer.setStyleSheet("font-size: 13px; font-weight: 700; color: #FFFFFF;")
        rec_lay.addWidget(self.lbl_rec_timer)
        vbox_act.addWidget(self.rec_status_bar)

        self.content_layout.addWidget(card_actions)

        # 2. Status message
        self.lbl_status = QLabel("Ready to capture.")
        self.lbl_status.setStyleSheet("font-size: 11px; color: #8E8E93; padding: 1px 2px; background: transparent;")
        self.lbl_status.setWordWrap(True)
        self.content_layout.addWidget(self.lbl_status)

        # 3. Selected Screenshot Details & Action Controls
        self.card_preview = QFrame()
        self.card_preview.setObjectName("cardPreview")
        self.card_preview.setStyleSheet(f"""
            QFrame#cardPreview {{
                background-color: {Theme.BG_CARD};
                border-radius: 8px;
                border: 1px solid {Theme.BORDER_SUBTLE};
            }}
        """)
        vbox_prev = QVBoxLayout(self.card_preview)
        vbox_prev.setContentsMargins(10, 10, 10, 10)
        vbox_prev.setSpacing(8)

        # Thumbnail display
        self.lbl_thumb = QLabel()
        self.lbl_thumb.setFixedHeight(120)
        self.lbl_thumb.setAlignment(Qt.AlignCenter)
        self.lbl_thumb.setCursor(Qt.PointingHandCursor)
        self.lbl_thumb.setToolTip("Click to open full-resolution preview")
        self.lbl_thumb.setStyleSheet("background-color: #1a1a1e; border-radius: 6px; border: 1px solid rgba(255, 255, 255, 0.06);")
        self.lbl_thumb.mousePressEvent = lambda _: self._open_full_preview()
        vbox_prev.addWidget(self.lbl_thumb)

        # Details: Name, Resolution, Size
        self.lbl_file_details = QLabel("No screenshot selected.")
        self.lbl_file_details.setStyleSheet("font-size: 11px; font-weight: 500; color: #E0E0E0; background: transparent;")
        self.lbl_file_details.setWordWrap(True)
        vbox_prev.addWidget(self.lbl_file_details)

        # Prominent Full-Width Copy Image Button
        self.btn_copy_image = QPushButton("Copy Image")
        self.btn_copy_image.setIcon(icons.get_icon("copy", color="#FFFFFF", size=16))
        self.btn_copy_image.setFixedHeight(34)
        self.btn_copy_image.setCursor(Qt.PointingHandCursor)
        self.btn_copy_image.setEnabled(False)
        self.btn_copy_image.setToolTip("Copy actual image bitmap data to system clipboard (ready to paste)")
        self.btn_copy_image.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.ACCENT_GREEN};
                color: #ffffff;
                font-weight: 600;
                font-size: 12px;
                padding: 4px 10px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {Theme.ACCENT_GREEN_HOVER};
            }}
            QPushButton:disabled {{
                background-color: #28282e;
                color: #65656d;
                border: 1px solid rgba(255, 255, 255, 0.04);
            }}
        """)
        self.btn_copy_image.clicked.connect(self._copy_image_data)
        vbox_prev.addWidget(self.btn_copy_image)

        # Secondary Actions Row: Preview, Copy Path, Delete
        row_actions = QHBoxLayout()
        row_actions.setSpacing(6)

        btn_sec_style = f"""
            QPushButton {{
                background-color: #2e2e34;
                color: #d0d0d5;
                font-size: 11px;
                font-weight: 500;
                padding: 4px 8px;
                border-radius: 5px;
                border: 1px solid {Theme.BORDER_SUBTLE};
            }}
            QPushButton:hover {{
                background-color: #3b3b44;
                color: #ffffff;
            }}
            QPushButton:disabled {{
                background-color: #202024;
                color: #55555a;
                border-color: transparent;
            }}
        """

        self.btn_open_image = QPushButton("Preview")
        self.btn_open_image.setIcon(icons.get_icon("external_link", color="#CCCCCC", size=13))
        self.btn_open_image.setFixedHeight(28)
        self.btn_open_image.setEnabled(False)
        self.btn_open_image.setStyleSheet(btn_sec_style)
        self.btn_open_image.clicked.connect(self._open_full_preview)
        row_actions.addWidget(self.btn_open_image)

        self.btn_copy_path = QPushButton("Path")
        self.btn_copy_path.setIcon(icons.get_icon("copy", color="#CCCCCC", size=13))
        self.btn_copy_path.setFixedHeight(28)
        self.btn_copy_path.setEnabled(False)
        self.btn_copy_path.setStyleSheet(btn_sec_style)
        self.btn_copy_path.clicked.connect(self._copy_path_text)
        row_actions.addWidget(self.btn_copy_path)

        self.btn_delete_image = QPushButton("Delete")
        self.btn_delete_image.setIcon(icons.get_icon("trash", color="#E81123", size=13))
        self.btn_delete_image.setFixedHeight(28)
        self.btn_delete_image.setEnabled(False)
        self.btn_delete_image.setStyleSheet(f"""
            QPushButton {{
                background-color: #2e2e34;
                color: #E81123;
                font-size: 11px;
                font-weight: 500;
                padding: 4px 8px;
                border-radius: 5px;
                border: 1px solid {Theme.BORDER_SUBTLE};
            }}
            QPushButton:hover {{
                background-color: rgba(232, 17, 35, 0.2);
                border-color: #E81123;
            }}
            QPushButton:disabled {{
                background-color: #202024;
                color: #55555a;
                border-color: transparent;
            }}
        """)
        self.btn_delete_image.clicked.connect(self._delete_image)
        row_actions.addWidget(self.btn_delete_image)

        vbox_prev.addLayout(row_actions)
        self.content_layout.addWidget(self.card_preview)

        # 4. Recent Screenshots Gallery
        lbl_gallery_hdr = QLabel("RECENT CAPTURES")
        lbl_gallery_hdr.setStyleSheet("font-weight: 700; font-size: 11px; letter-spacing: 0.6px; color: #8E8E93; margin-top: 4px;")
        self.content_layout.addWidget(lbl_gallery_hdr)

        self.gallery_list = QListWidget()
        self.gallery_list.setViewMode(QListWidget.IconMode)
        self.gallery_list.setIconSize(QSize(64, 48))
        self.gallery_list.setGridSize(QSize(74, 58))
        self.gallery_list.setFixedHeight(72)
        self.gallery_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 3px;
            }}
            QListWidget::item {{
                border-radius: 4px;
                margin: 2px;
            }}
            QListWidget::item:selected {{
                background-color: {Theme.ACCENT_GREEN_MUTED};
                border: 2px solid {Theme.ACCENT_GREEN};
            }}
        """)
        self.gallery_list.itemClicked.connect(self._on_gallery_item_clicked)
        self.content_layout.addWidget(self.gallery_list)

    def _apply_round_button_style(self, btn: QPushButton, highlight: bool = False) -> None:
        if highlight:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #32323a;
                    border: 1px solid rgba(255, 255, 255, 0.15);
                    border-radius: 20px;
                }}
                QPushButton:hover {{
                    background-color: {Theme.ACCENT_GREEN};
                    border-color: {Theme.ACCENT_GREEN};
                }}
                QPushButton:pressed {{
                    background-color: {Theme.ACCENT_GREEN_ACTIVE};
                }}
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2b2b32;
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 20px;
                }
                QPushButton:hover {
                    background-color: #3b3b44;
                    border-color: rgba(255, 255, 255, 0.2);
                }
                QPushButton:pressed {
                    background-color: #222228;
                }
            """)

    def _on_replay_clicked(self) -> None:
        self.lbl_status.setText("Replay buffer not active in current session.")

    def _toggle_mic(self) -> None:
        self._mic_enabled = not self._mic_enabled
        if self._mic_enabled:
            self.btn_mic.setIcon(icons.get_icon("mic", color="#107C41", size=20))
            self.btn_mic.setToolTip("Microphone ON")
            self.lbl_status.setText("Microphone enabled for recording.")
        else:
            self.btn_mic.setIcon(icons.get_icon("mic_off", color="#D0D0D0", size=20))
            self.btn_mic.setToolTip("Microphone OFF")
            self.lbl_status.setText("Microphone muted.")

    def _refresh_gallery(self) -> None:
        """Scan capture directories for existing real image files."""
        dirs = [
            self.service.capture_dir,
            Path.home() / "Pictures" / "Screenshots",
            Path.home() / "Pictures",
        ]
        files = []
        for d in dirs:
            if d.exists():
                for p in d.glob("*.png"):
                    try:
                        files.append((p.stat().st_mtime, str(p)))
                    except Exception:
                        pass

        # Sort newest first
        files.sort(key=lambda x: x[0], reverse=True)
        self._gallery_paths = [f[1] for f in files]

        self.gallery_list.clear()
        for path_str in self._gallery_paths[:20]:
            p = Path(path_str)
            item = QListWidgetItem()
            pix = QPixmap(path_str)
            if not pix.isNull():
                thumb = pix.scaled(64, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                item.setIcon(QIcon(thumb))
            item.setToolTip(p.name)
            item.setData(Qt.UserRole, path_str)
            self.gallery_list.addItem(item)

        if self._gallery_paths:
            self._select_screenshot(self._gallery_paths[0])
            self.gallery_list.setCurrentRow(0)
        else:
            self._clear_selection()

    def _select_screenshot(self, path_str: str) -> None:
        self.active_screenshot_path = path_str
        p = Path(path_str)

        if not p.exists():
            self._clear_selection()
            return

        pix = QPixmap(path_str)
        if not pix.isNull():
            self.lbl_thumb.setPixmap(pix.scaled(320, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            size_kb = round(p.stat().st_size / 1024, 1)
            self.lbl_file_details.setText(f"{p.name}\n{pix.width()}x{pix.height()} • {size_kb} KB")
            self.btn_copy_image.setEnabled(True)
            self.btn_open_image.setEnabled(True)
            self.btn_delete_image.setEnabled(True)
            self.btn_copy_path.setEnabled(True)
        else:
            self.lbl_file_details.setText(f"{p.name} (Corrupted image)")
            self.btn_copy_image.setEnabled(False)

    def _clear_selection(self) -> None:
        self.active_screenshot_path = None
        self.lbl_thumb.clear()
        self.lbl_thumb.setText("No screenshot selected.")
        self.lbl_file_details.setText("No screenshot selected.")
        self.btn_copy_image.setEnabled(False)
        self.btn_copy_image.setText("Copy Image")
        self.btn_open_image.setEnabled(False)
        self.btn_delete_image.setEnabled(False)
        self.btn_copy_path.setEnabled(False)

    def _on_gallery_item_clicked(self, item: QListWidgetItem) -> None:
        path_str = item.data(Qt.UserRole)
        if path_str:
            self._select_screenshot(path_str)

    def _on_clean_bg_toggled(self, checked: bool) -> None:
        self.config_manager.set("capture.clean_background_capture", checked)

    def _take_screenshot(self) -> None:
        self.btn_capture.setEnabled(False)

        clean_mode = self.config_manager.get("capture.clean_background_capture", False)

        top_win = self.window()
        was_visible = clean_mode and top_win and top_win.isVisible()

        if was_visible:
            self.lbl_status.setText("Capturing clean background screenshot...")
            if hasattr(top_win, "hide_for_capture"):
                top_win.hide_for_capture()
            else:
                top_win.hide()
                QApplication.processEvents()
            time.sleep(0.18)
            QApplication.processEvents()
        else:
            self.lbl_status.setText("Capturing screenshot...")

        before_time = time.time() - 1.0

        try:
            success, path_or_msg = self.service.take_screenshot(interactive=False)
        finally:
            if was_visible:
                if hasattr(top_win, "restore_after_capture"):
                    top_win.restore_after_capture()
                else:
                    top_win.show()
                    top_win.raise_()
                    top_win.activateWindow()
                self.raise_()
                self.activateWindow()
                QApplication.processEvents()
            self.btn_capture.setEnabled(True)

        if not success:
            self.lbl_status.setText(f"Capture failed: {path_or_msg}")
            return

        new_file = None
        for _ in range(12):
            latest = self.service.get_latest_screenshot()
            if latest and latest.exists() and latest.stat().st_mtime >= before_time:
                new_file = latest
                break
            time.sleep(0.25)

        if new_file and new_file.exists():
            path_str = str(new_file)
            self._refresh_gallery()
            self._select_screenshot(path_str)
            self._copy_image_data()
            if clean_mode:
                self.lbl_status.setText(f"✓ Background captured & copied to clipboard: {new_file.name}")
            else:
                self.lbl_status.setText(f"✓ Screenshot captured & copied to clipboard: {new_file.name}")
        else:
            self.lbl_status.setText("Screenshot completed.")
            self._refresh_gallery()

    def _copy_image_data(self) -> None:
        """Place actual image bitmap onto the system clipboard with multi-format MIME data."""
        if not self.active_screenshot_path or not os.path.exists(self.active_screenshot_path):
            self.lbl_status.setText("No valid image file to copy.")
            return

        image = QImage(self.active_screenshot_path)
        if image.isNull():
            self.lbl_status.setText("Failed to decode image data.")
            return

        mime = QMimeData()
        mime.setImageData(image)
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.WriteOnly)
        image.save(buf, "PNG")
        buf.close()
        mime.setData("image/png", ba)
        mime.setData("image/bmp", ba)

        clipboard = QApplication.clipboard()
        clipboard.setMimeData(mime, QClipboard.Clipboard)

        self.btn_copy_image.setText("✓ Copied to Clipboard!")
        QTimer.singleShot(1800, lambda: self.btn_copy_image.setText("Copy Image"))

        cb_mime = clipboard.mimeData()
        if cb_mime.hasImage() or cb_mime.hasFormat("image/png"):
            self.lbl_status.setText("✓ Image copied to system clipboard (ready to paste).")
        else:
            self.lbl_status.setText("Warning: Clipboard did not report image content.")

    def _open_image_viewer(self) -> None:
        if self.active_screenshot_path and os.path.exists(self.active_screenshot_path):
            subprocess.Popen(["xdg-open", self.active_screenshot_path])
            self.lbl_status.setText(f"Opened {Path(self.active_screenshot_path).name}")

    def _delete_image(self) -> None:
        if not self.active_screenshot_path:
            return

        target = Path(self.active_screenshot_path)
        res = QMessageBox.question(
            self,
            "Delete Screenshot",
            f"Are you sure you want to delete '{target.name}' from disk?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if res == QMessageBox.Yes:
            try:
                if target.exists():
                    target.unlink()
                self.lbl_status.setText(f"Deleted {target.name}")
                self._refresh_gallery()
            except Exception as e:
                self.lbl_status.setText(f"Delete failed: {e}")

    def _copy_path_text(self) -> None:
        if self.active_screenshot_path:
            QApplication.clipboard().setText(self.active_screenshot_path)
            self.lbl_status.setText(f"Copied file path to clipboard.")

    def _open_full_preview(self) -> None:
        if self.active_screenshot_path and os.path.exists(self.active_screenshot_path):
            dlg = ScreenshotViewerDialog(self.active_screenshot_path, self)
            dlg.exec()

    def _open_captures_folder(self) -> None:
        subprocess.Popen(["xdg-open", str(self.service.capture_dir)])

    def _toggle_recording(self) -> None:
        if not self.service.is_recording:
            success, msg = self.service.start_recording()
            if success:
                self.btn_rec_toggle.setStyleSheet(f"background-color: {Theme.COLOR_DANGER}; border-radius: 20px;")
                self.rec_status_bar.setVisible(True)
                self.lbl_status.setText("Recording in progress...")
                self.rec_timer.start(500)
            else:
                self.lbl_status.setText(f"Recording error: {msg}")
        else:
            self.rec_timer.stop()
            success, out_file = self.service.stop_recording()
            self._apply_round_button_style(self.btn_rec_toggle)
            self.rec_status_bar.setVisible(False)
            self.lbl_rec_timer.setText("00:00")
            if success and out_file:
                self.lbl_status.setText(f"✓ Video saved: {Path(out_file).name}")
            else:
                self.lbl_status.setText("Recording stopped.")

    def _update_rec_timer(self) -> None:
        dur = int(self.service.get_recording_duration())
        mins = dur // 60
        secs = dur % 60
        self.lbl_rec_timer.setText(f"{mins:02d}:{secs:02d}")
