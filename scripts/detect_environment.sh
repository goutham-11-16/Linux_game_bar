#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================="
echo "         Linux Game Bar - Environment Discovery"
echo "=========================================================="

echo "[*] Operating System:"
if [ -f /etc/os-release ]; then
    grep -E '^(PRETTY_NAME|NAME|VERSION)=' /etc/os-release | sed 's/"//g'
fi
echo "Kernel: $(uname -r)"

echo ""
echo "[*] Desktop Session:"
echo "Desktop: ${XDG_CURRENT_DESKTOP:-Unknown}"
echo "Session Type: ${XDG_SESSION_TYPE:-Unknown}"
echo "Wayland Display: ${WAYLAND_DISPLAY:-None}"
echo "X11 Display: ${DISPLAY:-None}"
if command -v gnome-shell >/dev/null 2>&1; then
    echo "GNOME Shell: $(gnome-shell --version)"
fi

echo ""
echo "[*] CPU & Memory:"
if command -v lscpu >/dev/null 2>&1; then
    lscpu | grep "Model name:" || true
    lscpu | grep "CPU(s):" | head -n 1 || true
fi
free -h | awk 'NR==2{printf "Memory: Used %s / Total %s (Available: %s)\n", $3, $2, $7}'

echo ""
echo "[*] GPU & Telemetry:"
if command -v lspci >/dev/null 2>&1; then
    lspci | grep -i 'vga\|3d' || true
fi
if [ -d /sys/class/drm/card1 ]; then
    echo "DRM device /sys/class/drm/card1 detected."
    if [ -f /sys/class/drm/card1/gt_act_freq_mhz ]; then
        echo "Intel GT sysfs frequencies available: $(cat /sys/class/drm/card1/gt_act_freq_mhz) MHz active"
    fi
fi

echo ""
echo "[*] Audio Server:"
if command -v wpctl >/dev/null 2>&1; then
    echo "PipeWire WirePlumber (wpctl) is INSTALLED."
elif command -v pactl >/dev/null 2>&1; then
    echo "PulseAudio (pactl) is INSTALLED."
else
    echo "No supported audio CLI found."
fi

echo ""
echo "[*] Capture & Recording Tools:"
for tool in ffmpeg grim slurp gnome-screenshot gst-launch-1.0; do
    if command -v "$tool" >/dev/null 2>&1; then
        echo " - $tool: $(command -v "$tool")"
    else
        echo " - $tool: not found"
    fi
done

echo "=========================================================="
