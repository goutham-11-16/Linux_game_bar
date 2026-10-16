# Project Linux Game Bar

An authentic **Windows 11 Xbox Game Bar clone and gaming overlay for Ubuntu GNOME**, built with Python 3 and PySide6 / Qt 6.

Designed specifically for Linux desktop gamers, Linux Game Bar provides a translucent acrylic floating dashboard accessible instantly via **Super + G**, featuring monochrome Fluent vector graphics, real hardware telemetry, PipeWire audio mixing, instant bitmap screenshot copying, screen recording, application launching, battery and thermal monitoring, persistent notes, game timers, and a full **Widget Developer SDK**.

---

## Key Features

- **🎮 Super + G Global Activation**: Registered natively in GNOME Shell without background keyloggers. Operates fully isolated on top of your games and ordinary desktop applications.
- **💎 Windows 11 Fluent UI**:
  - **Xbox Home Bar**: Top floating controller bar with the official Xbox orb emblem button, digital clock, quick widget toggles with Xbox green (`#107C41`) active indicator pills, settings, and dismiss controls.
  - **Widget Menu Flyout**: Authentic dropdown flyout listing all available widgets (both built-in and third-party) with search, display names, and Star favorite toggles to pin widgets to the Home Bar.
  - **Zero Emojis**: 100% monochrome vector SVG iconography dynamically rendered at crisp resolutions via `QSvgRenderer`.
- **⚡ Single-Instance IPC Daemon**: Instant toggling via local UNIX domain socket (`$XDG_RUNTIME_DIR/linux-game-bar.sock`).
- **📸 Screen Capture & Direct Clipboard Copying**:
  - Automatic full screenshot capture via XDG Desktop Portal without repetitive region selection prompts.
  - **Copy Image**: Copies actual uncompressed bitmap data (`image/png`, `image/bmp`) directly to the system clipboard for immediate pasting into Discord, Slack, Telegram, GIMP, etc.
  - **Exclude Game Bar Mode**: Momently withdraws the overlay during capture so only the underlying gameplay or application is captured.
  - **Recent Captures Gallery**: Interactive horizontal carousel of recent screenshots with full preview, copy path, and delete options.
- **🔊 PipeWire Audio Mixer**:
  - Reorganized into authentic **`[MIX]`** and **`[VOICE]`** tabs.
  - Master volume slider and instant mute toggle via `wpctl`.
  - Microphone input volume and mute controls.
  - Dynamic audio device switcher for speakers, headphones, and HDMI outputs.
- **📊 Real Hardware Performance Monitoring**:
  - Live CPU percentage (total & per-core) with frequency in GHz.
  - RAM & Swap usage in GiB with vector sparkline history graphs.
  - Real Intel Iris Xe GPU clock frequency & load metrics via Linux DRM sysfs.
- **🚀 Game & App Launcher**:
  - Automatically parses system `.desktop` files.
  - Instant search and dedicated "Games" and "Browsers" categories.
  - Safe, injection-free execution.
- **🔋 Battery & Thermal Monitoring**:
  - Battery charge level, AC power state, and time remaining.
  - CPU Package temperatures from `coretemp` and CPU fan speed from `dell_ddv`.
- **📝 Persistent Quick Notes**:
  - SQLite3-backed gaming notepad (`~/.local/share/linux-game-bar/notes.db`).
  - Debounced auto-save, multi-note management, and search.
- **⏱️ Game Timer**:
  - Drift-free monotonic countdown timer (`time.monotonic()`) with 5m, 10m, 15m, 25m Pomodoro presets.
- **📌 Pinning Widgets**:
  - Click the pushpin button on any widget header. Pinned widgets remain visible on screen even when the main Game Bar is dismissed!
- **🧩 Linux Game Bar Widget SDK (`linux_game_bar.sdk`)**:
  - Official SDK mirroring Microsoft's `Microsoft.Gaming.XboxGameBar`.
  - Simple base class `GameBarWidgetPlugin` with lifecycle hooks (`on_load`, `on_show`, `on_hide`, `on_pinned_changed`) and `build_widget()`.
  - Automatic dynamic plugin loading from `~/.local/share/linux-game-bar/plugins/`.

---

## Widget SDK Quickstart

Creating a custom widget plugin takes just a few lines of Python:

```python
# ~/.local/share/linux-game-bar/plugins/my_widget/plugin.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from linux_game_bar.sdk import GameBarWidgetPlugin, WidgetMetadata

class MyCustomWidget(GameBarWidgetPlugin):
    METADATA = WidgetMetadata(
        id="com.developer.my_widget",
        title="MY WIDGET",
        version="1.0.0",
        author="Developer Name",
        description="Custom widget for Linux Game Bar",
        icon_name="plugin",
        default_width=320,
        default_height=280,
    )

    def build_widget(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(QLabel("Hello from custom widget!"))
        btn = QPushButton("Notify Host")
        btn.clicked.connect(lambda: self.context.show_notification("Widget", "Button was clicked!"))
        layout.addWidget(btn)
        return container
```

---

## System Requirements

- **OS**: Ubuntu Linux 22.04 LTS / 24.04 LTS / 26.04 LTS (tested on Ubuntu 26.04.1)
- **Desktop Environment**: GNOME Shell on Wayland or X11
- **Python**: Python 3.10+ (tested on Python 3.14)
- **Audio**: PipeWire & WirePlumber (`wpctl`) or PulseAudio (`pactl`)

---

## Quick Installation

Run the automated installer script:

```bash
./install.sh
```

The installer will:
1. Create a dedicated virtual environment in `~/.local/share/linux-game-bar/venv`.
2. Install PySide6 and psutil dependencies.
3. Install the executable launcher in `~/.local/bin/linux-game-bar`.
4. Register the GNOME desktop entry and application icons.
5. Register the global shortcut **Super + G** in GNOME GSettings.
6. Execute automated verification.

---

## Usage

### Opening the Overlay
- Press **Super + G** anywhere on your desktop.
- Or run in terminal:
  ```bash
  linux-game-bar --toggle
  ```
- Or launch **Linux Game Bar** from the GNOME application grid.

### Closing / Dismissing
- Press **Escape** or click anywhere on the background.
- Or click the **✕** button on the top Home Bar.
- Or press **Super + G** again.

---

## Command Line Interface

```bash
linux-game-bar --toggle          # Toggle overlay visibility
linux-game-bar --show            # Show overlay
linux-game-bar --hide            # Hide overlay
linux-game-bar --quit            # Stop background daemon
linux-game-bar --diagnostics     # Print platform capabilities report
linux-game-bar --setup-shortcut  # Re-register GNOME Super+G shortcut
linux-game-bar --remove-shortcut # Remove GNOME shortcut
linux-game-bar --daemon          # Start daemon in background
```

---

## Testing

Run the automated test suite (37 unit, integration, and UI tests):

```bash
make test
# Or directly via pytest:
PYTHONPATH=src .venv/bin/pytest tests/
```

---

## Uninstallation

To cleanly remove the application while **preserving your notes and settings**:

```bash
./uninstall.sh
```

To purge all data, including notes databases and configuration files:

```bash
./uninstall.sh --purge
```

---

## License

MIT License. Open source and native Linux software.
