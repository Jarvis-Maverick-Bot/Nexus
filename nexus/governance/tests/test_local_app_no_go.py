from __future__ import annotations

import pytest

from nexus.governance.app_contract import (
    CommandAffordance,
    NotesEvidenceFrameViewModel,
    app_shell_forbidden_intent,
    validate_notes_evidence_frame,
)
from nexus.governance.errors import ErrorCode
from nexus.governance.no_go import NoGoBoundaryPolicy

from ._evidence import write_evidence


@pytest.mark.parametrize(
    "action",
    (
        "local_app_framework_selection",
        "local_app_database_selection",
        "local_app_api_schema_selection",
        "local_app_package_manager_selection",
        "local_app_server_selection",
        "local_app_runtime_invocation",
        "local_app_dispatch_execution",
        "local_app_route_activation",
        "local_app_view_model_authority",
        "local_app_direct_canonical_mutation",
        "local_app_approval",
        "local_app_completion",
        "local_app_archive",
        "local_app_baseline",
        "local_app_no_go_decision",
        "local_app_production_readiness",
        "local_app_deploy",
        "local_app_continuity_activation",
        "local_app_final_pass",
    ),
)
def test_local_app_no_go_policy_actions_are_blocked(action: str) -> None:
    result = NoGoBoundaryPolicy.default().evaluate({"action": action})

    assert result.blocked is True
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    write_evidence(f"no-go/{action}.json", result.to_evidence(), slice_id="l1gov-slice-010")


@pytest.mark.parametrize(
    "text",
    (
        "electron selected",
        "local database",
        "api schema selected",
        "server_url",
        "runtime transport",
        "desktop app project",
        "web frontend",
        "native shell",
        "view model authority",
        "projection authority",
        "cache authority",
        "approve now",
        "complete project",
        "archive workspace",
        "mark baseline",
        "no-go decision",
        "production readiness",
        "deploy now",
        "continuity activation",
        "final pass",
        "runtime invocation",
        "dispatch execution",
        "route activation",
        "adapter call",
        "transport call",
        "workpacket execution",
    ),
)
def test_app_shell_forbidden_intent_matches_sentence_shapes(text: str) -> None:
    assert app_shell_forbidden_intent({"label": f"please {text} from the local app"}) is True


def test_notes_evidence_frame_is_evidence_only() -> None:
    frame = NotesEvidenceFrameViewModel(
        frame_id="notes-evidence-001",
        source_docs_read=("UX V0.2-CS README",),
        prototype_refs=("figma:ux-v0.2-cs",),
        figma_refs=("figma:file:612813643",),
        ux_only_status="review_direction_only",
        governance_boundaries=("not_authority", "not_final_ui"),
        open_questions=("final framework deferred",),
        is_app_screen=False,
        creates_authority=False,
    )

    result = validate_notes_evidence_frame(frame)

    assert result.accepted is True
    write_evidence("notes/evidence-only-boundary.json", frame.to_evidence(), slice_id="l1gov-slice-010")


def test_notes_evidence_frame_rejects_app_screen_authority() -> None:
    frame = NotesEvidenceFrameViewModel(
        frame_id="notes-evidence-001",
        source_docs_read=("UX V0.2-CS README",),
        prototype_refs=("figma:ux-v0.2-cs",),
        figma_refs=("figma:file:612813643",),
        ux_only_status="review_direction_only",
        governance_boundaries=("not_authority",),
        open_questions=(),
        is_app_screen=True,
        creates_authority=True,
    )

    result = validate_notes_evidence_frame(frame)

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
