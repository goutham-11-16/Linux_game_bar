# Feature Matrix: Project Linux Game Bar

This document catalogs all functional components, capabilities, widgets, and platform behaviors.

## Feature Overview

| Feature Area | Component | Implementation | Wayland Support | X11 Support |
| :--- | :--- | :--- | :---: | :---: |
| **Global Shortcut** | Super + G | GNOME GSettings Custom Keybinding | Full | Full |
| **Single Instance** | IPC Server | `QLocalServer` Unix domain socket | Full | Full |
| **Top Dashboard** | DashboardBar | Qt6 Acrylic Translucent dark bar | Full | Full |
| **Performance** | PerformanceWidget | Real CPU % (total + per-core), RAM, Swap, Intel Iris Xe GT MHz | Full | Full |
| **Live Graphs** | SparklineGraph | Anti-aliased QPainter vector graph with Xbox green gradient fill | Full | Full |
| **Audio Mixer** | AudioWidget | Master output/input volume, mute, sink/source switching via `wpctl` | Full | Full |
| **Screenshots** | CaptureWidget | Desktop portal & GNOME capture, preview, open & copy path | Full | Full |
| **Screen Recording**| CaptureWidget | Native `org.gnome.Shell.Screencast`, elapsed timer, valid file verify | Full | Full (FFmpeg) |
| **App Launcher** | LauncherWidget | Desktop scanner (`.desktop` parsing), category filtering, instant search | Full | Full |
| **Battery & Thermals**| BatteryWidget| Real-time battery %, charging state, CPU Package temp & Fan RPM | Full | Full |
| **Quick Notes** | NotesWidget | Local SQLite database, auto-save debounce, search, persistence | Full | Full |
| **Game Timer** | TimerWidget | Monotonic countdown (`time.monotonic`), presets, audible notification | Full | Full |
| **Settings** | SettingsDialog | Hotkey configuration, interval tuning, directory selection, layout reset | Full | Full |
| **Autostart** | AutostartManager | XDG Autostart `~/.config/autostart/linux-game-bar.desktop` | Full | Full |
| **Installation** | install.sh | Automated user-level venv installation, desktop entries, smoke test | Full | Full |
| **Uninstaller** | uninstall.sh | Complete removal, shortcut restoration, optional data purge | Full | Full |

---

## Detailed Widget Specifications

### 1. Performance Widget
- **Sampling Interval**: Default 1000 ms (configurable to 500 ms or 2000 ms).
- **CPU Metrics**: Overall utilization, per-core utilization meters (all 16 cores), current frequency in GHz.
- **RAM Metrics**: Used memory, total memory, available memory, swap used, swap total.
- **GPU Metrics**: Real-time Intel Iris Xe GT clock frequency (`gt_act_freq_mhz`) from kernel DRM sysfs, active load percentage calculated from clock ratio. No fabricated metrics.
- **FPS Indicator**: Clear status reporting for MangoHud in-game overlay integration.

### 2. Audio Mixer Widget
- **Output Device Selector**: Dynamic dropdown of all detected PipeWire sinks with default indicator.
- **Master Output Slider**: Real-time volume percentage adjustment and mute toggle.
- **Microphone Input Slider**: Input gain adjustment and microphone mute toggle.
- **Readback Verification**: State is read back from `wpctl` to ensure synchronization with the system audio server.

### 3. Screen Capture Widget
- **Screenshot Modes**: Full desktop capture, active window capture, and region capture via standard portals.
- **Direct Actions**: Instant "Open File" (`xdg-open`) and "Copy Path" (system clipboard) buttons.
- **Screen Recording**: Starts/stops `org.gnome.Shell.Screencast`, displays live elapsed timer, and verifies valid output video file.

### 4. Game & App Launcher Widget
- **Discovery**: Automatically parses `/usr/share/applications` and `~/.local/share/applications`.
- **Filtering**: Instant fuzzy search across application names and executable strings.
- **Tabs**: "All Apps" and "🎮 Games".
- **Safe Execution**: Uses `QProcess.startDetached` without shell interpolation.

### 5. Battery & Thermals Widget
- **Battery Info**: Live charge percentage, charging/discharging state, AC power presence, time remaining estimate.
- **Thermal Sensors**: CPU package temperature from `coretemp` and CPU fan speed from `dell_ddv`.
- **Thermal Warning**: Color-coded status badge (Normal < 70°C, Warm 70-85°C, Hot > 85°C).

### 6. Quick Notes Widget
- **Storage**: Clean SQLite3 database located at `~/.local/share/linux-game-bar/notes.db`.
- **Auto-Save**: Debounced auto-save triggers 1 second after typing stops.
- **Multi-Note Support**: Create, search, switch, and delete notes with confirmation.

### 7. Game Timer Widget
- **Time Base**: Monotonic clock (`time.monotonic()`) prevents drift or freezing during system lag.
- **Presets**: 5m, 10m, 15m, 25m (Pomodoro), and 45m quick buttons, plus custom minute spinner.
- **Feedback**: Color change to red and terminal bell on completion.
