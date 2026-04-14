#!/usr/bin/env python
"""Grid Escape runner — use this if python -m games.grid_escape fails.

Run from the repo root (the directory containing games/):
    python games/grid_escape.py --grid ge-001
"""
import sys
from pathlib import Path

# Add the directory *above* games/ so Python finds the 'games' package
_script_dir = Path(__file__).resolve().parent
_repo_root = _script_dir.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from games.grid_escape.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
