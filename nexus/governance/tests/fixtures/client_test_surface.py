from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
SLICE012_SURFACE_ROOT = REPO_ROOT / "nexus" / "governance" / "client_test_surface" / "slice012"
SLICE012_FIXTURE_PATH = SLICE012_SURFACE_ROOT / "fixtures" / "slice012_state.json"
SLICE012_EVIDENCE_ROOT = REPO_ROOT / "verification" / "4.21" / "l1gov-slice-012"


REQUIRED_SURFACE_FILES: tuple[str, ...] = (
    "README.md",
    "index.html",
    "styles.css",
    "app.js",
    "fixtures/slice012_state.json",
)


REQUIRED_UI_REGION_IDS: tuple[str, ...] = (
    "workspace-picker-button",
    "workspace-picker-overlay",
    "mission-control",
    "module-nav",
    "inspector-panel",
    "status-bar",
    "notes-evidence-frame",
    "command-draft-panel",
    "service-outcome-panel",
    "stale-refresh-panel",
)
