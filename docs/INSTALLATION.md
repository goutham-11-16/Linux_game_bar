# Installation Guide: Project Linux Game Bar

This guide provides step-by-step instructions for installing, configuring, and testing Linux Game Bar on Ubuntu GNOME.

## System Requirements

- **Operating System**: Ubuntu 22.04 LTS, 24.04 LTS, 26.04 LTS or compatible Debian/Ubuntu derivatives.
- **Desktop Environment**: GNOME (Wayland or X11).
- **Python**: Python 3.10+ (tested and verified on Python 3.14).
- **Core Packages**: `python3-venv`, `libgl1`, `libegl1`, `gsettings-desktop-schemas`.
- **Audio Tools**: `pipewire`, `wireplumber` (`wpctl`), or `pulseaudio-utils` (`pactl`).

---

## 1. Quick Automated Installation

From the project root directory, execute:

```bash
./install.sh
```

### What `install.sh` Does:
1. Detects your Ubuntu version and desktop session.
2. Creates a dedicated installation directory at `~/.local/share/linux-game-bar/`.
3. Sets up an isolated Python virtual environment at `~/.local/share/linux-game-bar/venv`.
4. Installs required libraries (`PySide6`, `psutil`).
5. Generates the executable binary wrapper at `~/.local/bin/linux-game-bar`.
6. Installs application icons and `.desktop` launcher in `~/.local/share/applications/`.
7. Registers the global shortcut **Super + G** in GNOME settings.
8. Executes an automated smoke test to verify functionality.

---

## 2. Manual / Developer Installation

If you prefer to run or develop from source:

```bash
# Clone / navigate to project repository
cd "linux-game-bar"

# Create local virtual environment
python3 -m venv .venv

# Activate and install dependencies
source .venv/bin/activate
pip install -r requirements.txt

# Run application
PYTHONPATH=src python3 -m linux_game_bar
```

---

## 3. Configuring the Global Shortcut

The installer automatically configures `Super + G`. You can also configure or re-bind shortcuts using the CLI:

```bash
# Register Super + G
~/.local/bin/linux-game-bar --setup-shortcut

# Or test with the helper script
./scripts/configure_hotkey.sh "<Super>g"
```

If your GNOME session intercepts `Super + G`, you can switch to `Ctrl + Alt + G` via the in-app Settings dialog or by running:

```bash
./scripts/configure_hotkey.sh "<Control><Alt>g"
```

---

## 4. Verifying Installation

Run the diagnostics test:

```bash
~/.local/bin/linux-game-bar --diagnostics
```

Expected output:
```text
=== Linux Game Bar Platform Capabilities ===
OS: Ubuntu 26.04.1 LTS (Kernel: 7.0.0-38-generic)
Desktop: ubuntu:GNOME
Session: WAYLAND
CPU: 13th Gen Intel(R) Core(TM) i7-1360P (16 logical cores)
RAM: 14.8 GiB
GPU: Intel Iris Xe Graphics (i915/xe) (Telemetry: Yes)
Audio Backend: pipewire (wpctl: True, pactl: True)
Battery: Detected
Thermal Sensors: coretemp, dell_ddv, dell_smm
...
============================================
```

---

## 5. Clean Uninstallation

To remove all installed application files, shortcuts, and autostart entries while **preserving your notes and settings**:

```bash
./uninstall.sh
```

To perform a complete purge including all user notes, databases, logs, and settings:

```bash
./uninstall.sh --purge
```
