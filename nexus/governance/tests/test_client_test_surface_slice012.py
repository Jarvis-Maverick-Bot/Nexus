from __future__ import annotations

import json
import re

from .fixtures.client_test_surface import (
    REQUIRED_SURFACE_FILES,
    REQUIRED_UI_REGION_IDS,
    SLICE012_FIXTURE_PATH,
    SLICE012_SURFACE_ROOT,
)

SURFACE_ROOT = SLICE012_SURFACE_ROOT
FIXTURE_PATH = SLICE012_FIXTURE_PATH


def read_surface_file(name: str) -> str:
    return (SURFACE_ROOT / name).read_text(encoding="utf-8")


def load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_slice012_static_surface_files_exist_and_open_without_build_step() -> None:
    for relative_path in REQUIRED_SURFACE_FILES:
        path = SURFACE_ROOT / relative_path
        assert path.exists(), relative_path
        assert path.is_file(), relative_path
        assert path.stat().st_size > 0, relative_path

    html = read_surface_file("index.html")
    assert '<main id="app"' in html
    assert 'data-surface="l1gov-slice-012"' in html
    assert "app.js" in html
    assert "styles.css" in html


def test_slice012_fixture_is_non_authoritative_and_source_backed() -> None:
    fixture = load_fixture()

    assert fixture["slice_id"] == "L1GOV-SLICE-012"
    assert fixture["surface_mode"] == "static_local_browser_test_surface"
    assert fixture["canonical_authority"] == "GovernanceKernel"
    assert fixture["service_boundary"] == "GovernanceService"
    assert fixture["non_authoritative"] is True
    assert fixture["live_execution_invoked"] is False
    assert fixture["source_refs"] == [
        "Nexus:aa2ff2ad757988429764b6f5b9d748d75f5ab2bd",
        "L1GOV-SLICE-010",
        "L1GOV-SLICE-011",
        "UX V0.2-CS direction",
    ]

    workspace_picker = fixture["workspace_picker"]
    assert workspace_picker["mode"] == "temporary_overlay"
    assert workspace_picker["creates_authority"] is False

    mission_control = fixture["mission_control"]
    assert mission_control["projection_surface"]["read_only"] is True
    assert mission_control["projection_surface"]["canonical_authority"] is False


def test_slice012_surface_contains_required_operable_ux_regions() -> None:
    html = read_surface_file("index.html")

    for element_id in REQUIRED_UI_REGION_IDS:
        assert f'id="{element_id}"' in html

    js = read_surface_file("app.js")
    for hook in (
        "openWorkspacePicker",
        "selectWorkspace",
        "selectModule",
        "showCommandDraftPreview",
        "showServiceRejection",
        "showNoGoBlock",
        "cycleStaleRefresh",
    ):
        assert hook in js


def test_slice012_fixture_covers_service_rejection_no_go_and_stale_refresh_states() -> None:
    fixture = load_fixture()

    service_examples = fixture["service_outcomes"]
    assert service_examples["rejection"]["status"] == "rejected"
    assert service_examples["rejection"]["error_code"]
    assert service_examples["no_go_block"]["status"] == "blocked"
    assert service_examples["no_go_block"]["error_code"] == "ERR_NO_GO_BOUNDARY"

    stale_refresh = fixture["stale_refresh"]
    assert stale_refresh["states"] == ["stale", "rebuilding", "current"]
    assert stale_refresh["canonical_mutation"] is False


def test_slice012_surface_supports_render_scenarios_for_screenshots() -> None:
    js = read_surface_file("app.js")

    assert "applyScenarioFromUrl" in js
    assert 'scenario")' in js
    assert '"no-go"' in js
    assert '"stale"' in js


def test_slice012_surface_blocks_authority_and_live_runtime_paths() -> None:
    combined = "\n".join(
        [
            read_surface_file("index.html"),
            read_surface_file("styles.css"),
            read_surface_file("app.js"),
            FIXTURE_PATH.read_text(encoding="utf-8"),
        ]
    ).lower()

    forbidden_patterns = (
        r"\blocalstorage\b",
        r"\bsessionstorage\b",
        r"\bindexeddb\b",
        r"\bwebsocket\b",
        r"new\s+websocket",
        r"http://(?!127\.0\.0\.1|localhost)",
        r"https://",
        r"fetch\(['\"]http",
        r"runtime/live",
        r"private-agent invocation",
        r"dispatch execution",
        r"controller call",
        r"route activation",
        r"adapter transport activation",
        r"owner-path call",
        r"lower-layer submission",
        r"production readiness",
        r"continuity activation",
        r"final pass claim",
    )
    for pattern in forbidden_patterns:
        assert not re.search(pattern, combined), pattern

    assert "kernel and governance service remain authority" in combined
    assert "display state only" in combined
    assert "no canonical mutation" in combined
