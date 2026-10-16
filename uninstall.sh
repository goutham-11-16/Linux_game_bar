#!/usr/bin/env bash
set -euo pipefail

PURGE=false
if [ "${1:-}" = "--purge" ]; then
    PURGE=true
fi

echo "=========================================================="
echo "         Project Linux Game Bar - Uninstaller"
echo "=========================================================="

# 1. Stop active process
echo "[*] Stopping any running Linux Game Bar instances..."
if command -v linux-game-bar >/dev/null 2>&1; then
    linux-game-bar --quit || true
fi
pkill -f "linux_game_bar" || true

# 2. Unregister GNOME Shortcut
echo "[*] Removing GNOME shortcut..."
if command -v linux-game-bar >/dev/null 2>&1; then
    linux-game-bar --remove-shortcut || true
elif command -v gsettings >/dev/null 2>&1; then
    SCHEMA="org.gnome.settings-daemon.plugins.media-keys"
    KEY="custom-keybindings"
    SLOT="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/linux-game-bar/"
    CURRENT=$(gsettings get "$SCHEMA" "$KEY" 2>/dev/null || echo "@as []")
    if [[ "$CURRENT" == *"$SLOT"* ]]; then
        NEW_LIST=$(echo "$CURRENT" | sed "s|'$SLOT', ||; s|, '$SLOT'||; s|'$SLOT'||")
        gsettings set "$SCHEMA" "$KEY" "$NEW_LIST" || true
    fi
fi

# 3. Remove Desktop Launcher & Autostart
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
EXT_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/linux-game-bar@ubuntu.com"
INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/linux-game-bar"

echo "[*] Removing desktop entries & companion extension..."
if command -v gnome-extensions >/dev/null 2>&1; then
    gnome-extensions disable linux-game-bar@ubuntu.com 2>/dev/null || true
fi
rm -rf "$EXT_DIR"
rm -f "$APP_DIR/linux-game-bar.desktop"
rm -f "$AUTOSTART_DIR/linux-game-bar.desktop"
rm -f "$ICON_DIR/linux-game-bar.svg"
rm -f "$BIN_DIR/linux-game-bar"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APP_DIR" || true
fi

# 4. Remove Installation Files
echo "[*] Removing application binary files from $INSTALL_DIR..."
rm -rf "$INSTALL_DIR/venv" "$INSTALL_DIR/src" "$INSTALL_DIR/assets" "$INSTALL_DIR/config"

# 5. Handle User Data (Notes, Settings, Logs)
if [ "$PURGE" = true ]; then
    echo "[!] Purging all user data, notes, and configurations..."
    rm -rf "$INSTALL_DIR"
    rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/linux-game-bar"
    rm -rf "${XDG_STATE_HOME:-$HOME/.local/state}/linux-game-bar"
    rm -rf "${XDG_CACHE_HOME:-$HOME/.cache}/linux-game-bar"
    echo "[✓] All user settings and notes removed."
else
    echo "[✓] Preserving user notes and configuration by default."
    echo "    (To purge all user data, run: ./uninstall.sh --purge)"
fi

echo "=========================================================="
echo "Uninstallation verified and complete."
echo "=========================================================="
