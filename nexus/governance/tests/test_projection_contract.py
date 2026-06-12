from __future__ import annotations

from nexus.governance.projections import FreshnessState, ProjectionSnapshot, build_projection

from ._evidence import write_evidence


def test_projection_snapshot_records_source_checkpoint() -> None:
    snapshot = build_projection(
        projection_type="mission_control",
        workspace_id="workspace-001",
        source_checkpoint="kernel:2",
        payload={"status": "kernel_ready"},
        authority_refs=("WBS V0.6",),
    )

    assert snapshot.source_checkpoint == "kernel:2"
    assert snapshot.freshness == FreshnessState.FRESH
    write_evidence("projection/projection-snapshot.json", snapshot.to_evidence())


def test_stale_projection_is_marked_stale() -> None:
    snapshot = ProjectionSnapshot(
        projection_id="projection-001",
        projection_type="mission_control",
        workspace_id="workspace-001",
        source_checkpoint="kernel:1",
        freshness=FreshnessState.STALE,
        payload={},
        authority_refs=("WBS V0.6",),
    )

    assert snapshot.is_stale is True


def test_projection_payload_is_not_canonical_state() -> None:
    snapshot = build_projection(
        projection_type="monitor_queue",
        workspace_id="workspace-001",
        source_checkpoint="kernel:2",
        payload={"can_accept": False},
        authority_refs=("WBS V0.6",),
    )

    assert snapshot.is_canonical_state is False
