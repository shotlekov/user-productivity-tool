#!/usr/bin/env python3
"""Launcher for User Productivity Tool GUI - double-click to run without terminal."""

import sys
import subprocess
from pathlib import Path

# Add the current directory to path so we can import the tool
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

if __name__ == "__main__":
    # Run the GUI directly
    from user_productivity_tool import run_gui
    run_gui()