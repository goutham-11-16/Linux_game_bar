"""Pytest configuration fixture."""

import os
import sys
import pytest

# Ensure offscreen platform is configured for headless/test environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"
if "XDG_RUNTIME_DIR" not in os.environ:
    os.environ["XDG_RUNTIME_DIR"] = "/tmp"

from PySide6.QtWidgets import QApplication

@pytest.fixture(scope="session")
def qapp():
    """Ensure a single persistent QApplication instance exists during test run."""
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    yield app
