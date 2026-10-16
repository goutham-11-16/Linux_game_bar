#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
    echo "Virtual environment .venv not found. Creating and installing requirements..."
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
fi

PYTHONPATH=src .venv/bin/python -m linux_game_bar "$@"
