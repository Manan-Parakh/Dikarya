"""
This module provides a utility function to consistently determine the root directory of the project, 
which is used for storing logs and other persistent artifacts. 
The logic ensures correct root resolution whether the code is running as a packaged application 
(e.g., via PyInstaller) or during local development.

- If the script is running in a frozen/packaged state (like with PyInstaller), 
  the project root is set to the directory containing the executable.
- Otherwise (in source/development mode), the root is the parent directory of this file's directory.

This allows all data-writing and data-reading operations (like saving logs) 
to always target the appropriate, predictable location regardless of the app's execution mode.
"""

from __future__ import annotations

import sys
from pathlib import Path

def get_project_root() -> Path:
    """
    Returns the directory where logs and other project artifacts should be stored.

    - In a packaged (frozen) executable, this returns the directory containing the executable.
    - In development (i.e., running from source), this returns the project root directory,
      specifically the parent of the folder containing this module.
    """
    if getattr(sys, "frozen", False):
        # If running as a bundled app (PyInstaller), use the executable's directory.
        return Path(sys.executable).resolve().parent
    # Otherwise, use the parent folder of the helper package as the project root.
    return Path(__file__).resolve().parents[1]
