from __future__ import annotations

from nexus.governance.errors import ErrorCode
from nexus.governance.projections import (
    FreshnessState,
    build_projection_snapshot,
    failed_projection_snapshot,
    mark_projection_stale,
    rebuild_projection_snapshot,
)
from nexus.governance.service_facade import validate_service_command_envelope

from ._evidence import write_evidence
from .fixtures.service_facade import SERVICE_SOURCE_REFS, service_command


def test_projection_snapshot_current_is_read_only_and_not_authority() -> None:
    snapshot = build_projection_snapshot(
        projection_type="mission_control",
        workspace_id="workspace-001",
        source_checkpoint="kernel:12",
        payload={"state": "completion_continuity_review_requested"},
        authority_refs=SERVICE_SOURCE_REFS,
        generated_at="2026-06-13T00:00:00+00:00",
    )

    assert snapshot.freshness == FreshnessState.CURRENT
    assert snapshot.read_only is True
    assert snapshot.is_canonical_state is False
    write_evidence("projection/projection-current-read-only.json", snapshot.to_evidence(), slice_id="l1gov-slice-009")


def test_stale_projection_rebuilds_from_kernel_checkpoint() -> None:
    stale = mark_projection_stale(
        build_projection_snapshot(
            projection_type="mission_control",
            workspace_id="workspace-001",
            source_checkpoint="kernel:11",
            payload={"state": "feedback_triage_recorded"},
            authority_refs=SERVICE_SOURCE_REFS,
        )
    )

    rebuilt = rebuild_projection_snapshot(
        stale,
        latest_source_checkpoint="kernel:12",
        payload={"state": "completion_continuity_review_requested"},
    )

    assert stale.freshness == FreshnessState.STALE
    assert rebuilt.freshness == FreshnessState.CURRENT
    assert rebuilt.source_checkpoint == "kernel:12"
    write_evidence("projection/stale-projection-rebuild.json", rebuilt.to_evidence(), slice_id="l1gov-slice-009")


def test_projection_rebuild_failure_remains_read_only() -> None:
    failed = failed_projection_snapshot(
        projection_type="mission_control",
        workspace_id="workspace-001",
        source_checkpoint="kernel:11",
        authority_refs=SERVICE_SOURCE_REFS,
        reason="workspace source mismatch",
    )

    assert failed.freshness == FreshnessState.FAILED
    assert failed.read_only is True
    assert failed.is_canonical_state is False
    write_evidence("projection/rebuild-timeout-failed.json", failed.to_evidence(), slice_id="l1gov-slice-009")


def test_projection_payload_cannot_be_used_as_authority() -> None:
    command = service_command(payload={"authorization_source": "projection:mission_control", "authority_source": "projection"})

    result = validate_service_command_envelope(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    write_evidence("projection/projection-not-authority.json", result.to_evidence(), slice_id="l1gov-slice-009")
