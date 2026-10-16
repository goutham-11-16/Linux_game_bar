# Troubleshooting & FAQ: Project Linux Game Bar

This document covers common questions, edge cases, and troubleshooting solutions.

---

## 1. Global Shortcut (Super + G) Not Opening the Bar

### Symptom:
Pressing `Super + G` does not open or toggle the overlay.

### Root Cause & Solutions:
1. **Shortcut Not Registered**:
   Check if the GNOME custom shortcut is registered:
   ```bash
   gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings
   ```
   If empty (`@as []`), run:
   ```bash
   ~/.local/bin/linux-game-bar --setup-shortcut
   ```

2. **GNOME Shell Interception**:
   Some versions of GNOME or custom extensions reserve the `Super` key.
   Switch to `Ctrl + Alt + G`:
   ```bash
   ./scripts/configure_hotkey.sh "<Control><Alt>g"
   ```

3. **Daemon Not Running**:
   Ensure the background daemon is alive:
   ```bash
   pgrep -fl linux_game_bar
   ```
   If not running, launch it:
   ```bash
   ~/.local/bin/linux-game-bar --daemon &
   ```

---

## 2. Audio Mixer Shows "No Devices" or Slider Doesn't Respond

### Symptom:
The audio mixer widget cannot find sinks or control volume.

### Root Cause & Solutions:
1. **PipeWire WirePlumber tool (`wpctl`)**:
   Verify that `wpctl` works in your terminal:
   ```bash
   wpctl status
   ```
   If `wpctl` is missing, install WirePlumber:
   ```bash
   sudo apt install wireplumber
   ```
2. **Runtime Directory Permissions**:
   Make sure `XDG_RUNTIME_DIR` points to `/run/user/$(id -u)`.

---

## 3. Intel GPU Metrics Show "Unavailable"

### Symptom:
GPU utilization percentage stays at 0% or says "No Telemetry Sysfs".

### Explanation:
Linux Game Bar **never fabricates** GPU metrics. On Intel Iris Xe / Raptor Lake graphics, telemetry is read directly from kernel DRM sysfs files:
```text
/sys/class/drm/card1/gt_act_freq_mhz
/sys/class/drm/card1/gt_cur_freq_mhz
```
If your system uses a different DRM card index (e.g. `card0` instead of `card1`), check available cards:
```bash
ls -la /sys/class/drm/card*/gt_act_freq_mhz
```
You can update your card index in `~/.config/linux-game-bar/settings.json`.

---

## 4. Screen Capture / Recording Permissions on Wayland

### Symptom:
Screenshot button triggers an error or prompt.

### Explanation:
Under GNOME Wayland, direct desktop window inspection is prohibited for security. Linux Game Bar uses `xdg-desktop-portal` and `org.gnome.Shell.Screencast`.
1. When prompted by the system, click **Share / Allow** to permit desktop access.
2. Screenshots are automatically saved to `~/Pictures/Captures/` and `~/Pictures/Screenshots/`.
3. Screen recordings are saved to `~/Videos/Captures/`.

---

## 5. Overlay Window Not Visible Over Exclusive Fullscreen Games

### Symptom:
In certain exclusive fullscreen games running via Wine/Proton, the overlay appears behind the game window.

### Recommendation:
Run games in **Borderless Windowed** or **Fullscreen Windowed** mode. On Wayland compositors (Mutter), Wayland enforces strict surface layering and borderless windowed mode guarantees overlay visibility.
