#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================="
echo "         Project Linux Game Bar - Installer"
echo "=========================================================="

# 1. Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "[✓] Detected OS: $PRETTY_NAME"
else
    echo "[!] Warning: /etc/os-release not found. Assuming Linux."
fi

# 2. Check Python
if ! command -v python3 >/dev/null 2>&1; then
    echo "[✗] Error: python3 is not installed. Please install Python 3.10+."
    exit 1
fi

PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "[✓] Python version: $PY_VER"

# 3. Check for python3-venv
if ! python3 -m venv --help >/dev/null 2>&1; then
    echo "[✗] Error: python3-venv is required. Please install python3-venv."
    exit 1
fi

# 4. Target Directories
PREFIX="${XDG_DATA_HOME:-$HOME/.local/share}/linux-game-bar"
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"

mkdir -p "$PREFIX" "$BIN_DIR" "$APP_DIR" "$ICON_DIR"

echo "[*] Installing to $PREFIX..."

# 5. Create Python Virtual Environment
VENV_DIR="$PREFIX/venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "[*] Creating dedicated virtual environment at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
fi

echo "[*] Installing dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install "PySide6>=6.5.0" "psutil>=5.9.0"

# 6. Copy Application Source Code
echo "[*] Copying application files..."
rm -rf "$PREFIX/src" "$PREFIX/assets" "$PREFIX/config"
cp -r src "$PREFIX/"
cp -r assets "$PREFIX/"
cp -r config "$PREFIX/"

# 7. Create Executable Wrapper
WRAPPER="$BIN_DIR/linux-game-bar"
cat << 'EOF' > "$WRAPPER"
#!/usr/bin/env bash
INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/linux-game-bar"
export PYTHONPATH="$INSTALL_DIR/src"
exec "$INSTALL_DIR/venv/bin/python" -m linux_game_bar "$@"
EOF
chmod +x "$WRAPPER"
echo "[✓] Created launcher binary at $WRAPPER"

# 8. Install Icon and Desktop Launcher
cp assets/icons/app_icon.svg "$ICON_DIR/linux-game-bar.svg"
sed "s|Exec=linux-game-bar|Exec=$WRAPPER|g" packaging/linux-game-bar.desktop > "$APP_DIR/linux-game-bar.desktop"
chmod +x "$APP_DIR/linux-game-bar.desktop"
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APP_DIR" || true
fi
echo "[✓] Registered desktop launcher in $APP_DIR"

# 9. Register Global Shortcut in GNOME
echo "[*] Registering GNOME global shortcut (Super + G)..."
"$WRAPPER" --setup-shortcut || true

# 10. Install Companion GNOME Shell Extension (if supported)
EXT_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/linux-game-bar@ubuntu.com"
if [ -d "packaging/extension/linux-game-bar@ubuntu.com" ]; then
    echo "[*] Installing companion GNOME Shell extension..."
    mkdir -p "$EXT_DIR"
    cp -r packaging/extension/linux-game-bar@ubuntu.com/* "$EXT_DIR/"
    if command -v gnome-extensions >/dev/null 2>&1; then
        gnome-extensions enable linux-game-bar@ubuntu.com 2>/dev/null || true
    fi
    echo "[✓] Companion GNOME Shell extension installed."
fi

# 10. Run Smoke Test
echo "[*] Executing smoke test..."
if "$WRAPPER" --diagnostics >/dev/null 2>&1; then
    echo "[✓] Smoke test PASSED successfully!"
else
    echo "[!] Warning: Smoke test returned non-zero exit code."
fi

echo ""
echo "=========================================================="
echo "Installation complete!"
echo "You can launch Linux Game Bar by:"
echo " 1. Pressing Super + G"
echo " 2. Running: $WRAPPER --toggle"
echo " 3. Launching 'Linux Game Bar' from GNOME Activities"
echo "=========================================================="
