"""Settings configuration dialog."""

import os
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QCheckBox,
    QComboBox,
    QSlider,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QFrame,
)

from linux_game_bar.ui.theme import Theme
from linux_game_bar.config_manager import ConfigManager
from linux_game_bar.platform.gnome_integration import GnomeShortcutManager
from linux_game_bar.platform.autostart import AutostartManager


class SettingsDialog(QDialog):
    """Settings modal dialog for configuring shortcuts, directories, and startup."""

    settings_applied = Signal()
    reset_layout_requested = Signal()

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.shortcut_mgr = GnomeShortcutManager()
        self.autostart_mgr = AutostartManager()

        self.setWindowTitle("Linux Game Bar Settings")
        self.setFixedSize(500, 620)
        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #1a1a1e;
                color: #ffffff;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Title
        lbl_title = QLabel("⚙️ Overlay Settings")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #ffffff;")
        layout.addWidget(lbl_title)

        # 1. Global Shortcut Section
        card_hotkey = QFrame()
        card_hotkey.setStyleSheet(f"background-color: {Theme.BG_CARD}; border-radius: 8px; padding: 10px;")
        vbox_hk = QVBoxLayout(card_hotkey)
        vbox_hk.setSpacing(6)

        lbl_hk = QLabel("Global Activation Shortcut:")
        lbl_hk.setStyleSheet("font-weight: 600;")
        vbox_hk.addWidget(lbl_hk)

        self.input_hotkey = QLineEdit(self.config_manager.get("hotkey", "<Super>g"))
        self.input_hotkey.setPlaceholderText("<Super>g or <Control><Alt>g")
        vbox_hk.addWidget(self.input_hotkey)

        lbl_hk_hint = QLabel("Uses GNOME custom keybinding. Default is Super + G.")
        lbl_hk_hint.setStyleSheet("font-size: 11px; color: #A0A0A5;")
        vbox_hk.addWidget(lbl_hk_hint)
        layout.addWidget(card_hotkey)

        # 2. Startup & Autostart
        card_start = QFrame()
        card_start.setStyleSheet(f"background-color: {Theme.BG_CARD}; border-radius: 8px; padding: 10px;")
        vbox_st = QVBoxLayout(card_start)
        vbox_st.setSpacing(6)

        self.chk_autostart = QCheckBox("Start Linux Game Bar automatically on login")
        self.chk_autostart.setChecked(self.autostart_mgr.is_enabled())
        vbox_st.addWidget(self.chk_autostart)
        layout.addWidget(card_start)

        # 3. Telemetry Refresh Rate
        card_perf = QFrame()
        card_perf.setStyleSheet(f"background-color: {Theme.BG_CARD}; border-radius: 8px; padding: 10px;")
        vbox_pf = QVBoxLayout(card_perf)
        vbox_pf.setSpacing(6)

        lbl_rate = QLabel("Performance Sampling Interval:")
        lbl_rate.setStyleSheet("font-weight: 600;")
        vbox_pf.addWidget(lbl_rate)

        self.combo_interval = QComboBox()
        self.combo_interval.addItem("Fast (500 ms)", 500)
        self.combo_interval.addItem("Normal (1000 ms) - Recommended", 1000)
        self.combo_interval.addItem("Eco / Low Power (2000 ms)", 2000)

        cur_interval = self.config_manager.get("metrics.sampling_interval_ms", 1000)
        idx = 1
        if cur_interval == 500:
            idx = 0
        elif cur_interval == 2000:
            idx = 2
        self.combo_interval.setCurrentIndex(idx)
        vbox_pf.addWidget(self.combo_interval)
        layout.addWidget(card_perf)

        # 4. Captures Settings: Mode & Folder
        card_cap = QFrame()
        card_cap.setStyleSheet(f"background-color: {Theme.BG_CARD}; border-radius: 8px; padding: 10px;")
        vbox_cp = QVBoxLayout(card_cap)
        vbox_cp.setSpacing(6)

        lbl_cap_mode = QLabel("Screenshot Capture Mode:")
        lbl_cap_mode.setStyleSheet("font-weight: 600;")
        vbox_cp.addWidget(lbl_cap_mode)

        self.combo_capture_mode = QComboBox()
        self.combo_capture_mode.addItem("Clean Background (Exclude Game Bar Overlay)", True)
        self.combo_capture_mode.addItem("Direct Screen Capture (Zero Flicker / Instant)", False)

        is_clean = self.config_manager.get("capture.clean_background_capture", True)
        self.combo_capture_mode.setCurrentIndex(0 if is_clean else 1)
        vbox_cp.addWidget(self.combo_capture_mode)

        lbl_mode_hint = QLabel(
            "• Clean Background: Momentarily withdraws overlay so only the underlying game is captured.\n"
            "• Direct Capture: Captures instantly with zero blinking, capturing the screen as-is."
        )
        lbl_mode_hint.setStyleSheet("font-size: 11px; color: #A0A0A5; line-height: 1.4;")
        vbox_cp.addWidget(lbl_mode_hint)

        lbl_cap = QLabel("Captures Output Directory:")
        lbl_cap.setStyleSheet("font-weight: 600; margin-top: 4px;")
        vbox_cp.addWidget(lbl_cap)

        row_cap = QHBoxLayout()
        self.input_cap_dir = QLineEdit(str(self.config_manager.get("capture.screenshot_directory", Path.home() / "Pictures" / "Captures")))
        row_cap.addWidget(self.input_cap_dir)

        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse_cap_dir)
        row_cap.addWidget(btn_browse)
        vbox_cp.addLayout(row_cap)
        layout.addWidget(card_cap)

        # 5. Reset Layout
        row_reset = QHBoxLayout()
        btn_reset_layout = QPushButton("Reset All Widgets to Default Positions")
        btn_reset_layout.clicked.connect(self._reset_layout)
        row_reset.addWidget(btn_reset_layout)
        layout.addLayout(row_reset)

        layout.addStretch()

        # Dialog Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_save = QPushButton("Save & Apply")
        btn_save.setProperty("class", "accent")
        btn_save.clicked.connect(self._save_and_apply)
        btn_box.addWidget(btn_save)

        layout.addLayout(btn_box)

    def _browse_cap_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Captures Directory", self.input_cap_dir.text())
        if folder:
            self.input_cap_dir.setText(folder)

    def _reset_layout(self) -> None:
        res = QMessageBox.question(
            self,
            "Reset Layout",
            "Reset all widgets to their default positions and sizes?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if res == QMessageBox.Yes:
            self.reset_layout_requested.emit()

    def _save_and_apply(self) -> None:
        # Save hotkey
        new_hotkey = self.input_hotkey.text().strip() or "<Super>g"
        old_hotkey = self.config_manager.get("hotkey", "<Super>g")
        self.config_manager.set("hotkey", new_hotkey, auto_save=False)

        if new_hotkey != old_hotkey:
            # Register in GNOME
            exec_bin = shutil_which_or_default("linux-game-bar", str(Path.home() / ".local" / "bin" / "linux-game-bar"))
            cmd = f"{exec_bin} --toggle"
            self.shortcut_mgr.register_shortcut(cmd, shortcut=new_hotkey)

        # Autostart
        if self.chk_autostart.isChecked():
            self.autostart_mgr.enable()
            self.config_manager.set("autostart", True, auto_save=False)
        else:
            self.autostart_mgr.disable()
            self.config_manager.set("autostart", False, auto_save=False)

        # Interval
        interval = self.combo_interval.currentData()
        self.config_manager.set("metrics.sampling_interval_ms", interval, auto_save=False)

        # Directory & Capture Mode
        self.config_manager.set("capture.screenshot_directory", self.input_cap_dir.text(), auto_save=False)
        self.config_manager.set("capture.clean_background_capture", self.combo_capture_mode.currentData(), auto_save=False)

        self.config_manager.save()
        self.settings_applied.emit()
        self.accept()


def shutil_which_or_default(name: str, default: str) -> str:
    import shutil
    res = shutil.which(name)
    return res if res else default
