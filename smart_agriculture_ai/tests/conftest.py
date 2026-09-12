"""Ensure pytest imports the project package instead of any parent shadow package."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PARENT_DIR = PROJECT_ROOT.parent

for candidate in (str(PROJECT_ROOT), str(PARENT_DIR)):
    if candidate in sys.path:
        sys.path.remove(candidate)

sys.path.insert(0, str(PROJECT_ROOT))

# Remove any parent directory path to prevent sibling shadow packages such as
# /home/seg/Documents/agriculture/rag from taking precedence over the project package.
for entry in list(sys.path):
    if entry and entry.startswith(str(PARENT_DIR)) and entry != str(PROJECT_ROOT):
        sys.path.remove(entry)
