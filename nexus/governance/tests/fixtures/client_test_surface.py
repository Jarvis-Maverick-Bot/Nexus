from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
DESKTOP_APP_ROOT = REPO_ROOT / "apps" / "l1gov-desktop-client"
DESKTOP_FIXTURE_PATH = DESKTOP_APP_ROOT / "src" / "fixtures" / "slice012_desktop_state.json"
