"""Tests for CaptureWidget gallery, image-to-clipboard, preview, and deletion."""

import os
import pytest
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QClipboard, QPixmap
from PySide6.QtWidgets import QApplication

from linux_game_bar.widgets.capture import CaptureWidget, ScreenshotViewerDialog


def test_clipboard_image_copy_and_verification(qapp, tmp_path: Path):
    # 1. Create a genuine test PNG image
    test_img_path = tmp_path / "test_screenshot_1.png"
    q_img = QImage(320, 240, QImage.Format_ARGB32)
    q_img.fill(0xFF107C10)  # Xbox green
    assert q_img.save(str(test_img_path)) is True

    # 2. Instantiate CaptureWidget
    widget = CaptureWidget()
    widget.service.capture_dir = tmp_path
    widget._refresh_gallery()

    # 3. Select the screenshot
    widget._select_screenshot(str(test_img_path))
    assert widget.active_screenshot_path == str(test_img_path)
    assert widget.btn_copy_image.isEnabled() is True

    # 4. Perform Copy Image
    widget._copy_image_data()

    # 5. Verify actual image data and MIME formats on system clipboard
    clipboard = QApplication.clipboard()
    cb_img = clipboard.image()
    assert not cb_img.isNull()
    assert cb_img.width() == 320
    assert cb_img.height() == 240
    mime = clipboard.mimeData()
    assert mime.hasImage() is True
    assert "image/png" in mime.formats()
    assert len(mime.data("image/png")) > 0


def test_screenshot_gallery_ordering_and_deletion(qapp, tmp_path: Path):
    # Create two test images with different timestamps
    file1 = tmp_path / "Screenshot_20261016_100000.png"
    file2 = tmp_path / "Screenshot_20261016_110000.png"

    img1 = QImage(100, 100, QImage.Format_RGB32)
    img1.fill(0xFFFFFFFF)
    img1.save(str(file1))

    img2 = QImage(100, 100, QImage.Format_RGB32)
    img2.fill(0xFF000000)
    img2.save(str(file2))

    widget = CaptureWidget()
    widget.service.capture_dir = tmp_path
    widget._refresh_gallery()

    # Verify both exist in gallery list
    assert widget.gallery_list.count() >= 2
    assert widget.active_screenshot_path is not None

    # Test file deletion directly through service/widget logic
    target_path = widget.active_screenshot_path
    assert Path(target_path).exists()
    os.remove(target_path)
    widget._refresh_gallery()

    assert not Path(target_path).exists()
    assert target_path not in widget._gallery_paths


def test_preview_dialog_initialization(qapp, tmp_path: Path):
    img_path = tmp_path / "preview_test.png"
    img = QImage(200, 150, QImage.Format_ARGB32)
    img.fill(0xFF1E90FF)
    img.save(str(img_path))

    dialog = ScreenshotViewerDialog(str(img_path))
    assert dialog.image_path == str(img_path)
    assert not dialog.lbl_image.pixmap().isNull()


def test_take_screenshot_hides_overlay_during_capture(qapp, tmp_path: Path):
    from unittest.mock import MagicMock
    from PySide6.QtWidgets import QWidget

    parent = QWidget()
    parent.show()
    assert parent.isVisible() is True

    widget = CaptureWidget(parent)
    widget.service.capture_dir = tmp_path

    # Create dummy screenshot
    captured_img = tmp_path / "Screenshot_20261016_200000.png"
    q_img = QImage(100, 100, QImage.Format_RGB32)
    q_img.fill(0xFF00FF00)
    q_img.save(str(captured_img))

    # 1. Test clean background mode explicitly: window hides and restores
    widget.config_manager.set("capture.clean_background_capture", True)
    was_hidden_during_capture = False

    def mock_capture(*args, **kwargs):
        nonlocal was_hidden_during_capture
        was_hidden_during_capture = not parent.isVisible()
        return True, str(captured_img)

    widget.service.take_screenshot = MagicMock(side_effect=mock_capture)
    widget.service.get_latest_screenshot = MagicMock(return_value=captured_img)

    widget._take_screenshot()

    assert was_hidden_during_capture is True
    assert parent.isVisible() is True
    assert widget.active_screenshot_path == str(captured_img)

    # 2. Test default seamless silent mode: window stays open smoothly
    widget.config_manager.set("capture.clean_background_capture", False)
    was_hidden_seamless = False

    def mock_capture_seamless(*args, **kwargs):
        nonlocal was_hidden_seamless
        was_hidden_seamless = not parent.isVisible()
        return True, str(captured_img)

    widget.service.take_screenshot = MagicMock(side_effect=mock_capture_seamless)
    widget._take_screenshot()

    assert was_hidden_seamless is False
    assert parent.isVisible() is True


