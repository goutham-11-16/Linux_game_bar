#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

if [ -f ".venv/bin/python" ]; then
    PYTHONPATH=src .venv/bin/python -m linux_game_bar --diagnostics
elif command -v python3 >/dev/null 2>&1; then
    PYTHONPATH=src python3 -m linux_game_bar --diagnostics
else
    echo "Python 3 is required to run diagnostics."
    exit 1
fi
