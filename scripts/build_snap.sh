#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================="
echo "          Linux Game Bar - Snap Package Builder"
echo "=========================================================="

if ! command -v snapcraft >/dev/null 2>&1; then
    echo "[!] snapcraft is not installed."
    echo "[*] You can install it using: sudo snap install snapcraft --classic"
    exit 1
fi

echo "[*] Building Snap package..."
snapcraft clean
snapcraft --destructive-mode

echo "[✓] Build complete! Package .snap is ready in $(pwd)"
