from __future__ import annotations

from nexus.governance.app_contract import (
    MissionControlViewModel,
    ProjectionReadSurface,
    build_projection_read_surface,
    build_projection_refresh_command,
    build_service_outcome_view,
    validate_mission_control_view_model,
    validate_projection_read_surface,
)
from nexus.governance.errors import ErrorCode
from nexus.governance.projections import build_projection_snapshot, mark_projection_stale
from nexus.governance.schemas import ActorRef
from nexus.governance.service_facade import ServiceCommandOutcome, ServiceOutcomeStatus, validate_service_command_envelope

from ._evidence import write_evidence


SOURCE_REFS = ("WBS V0.6", "L1GOV-SLICE-010", "eef9c05")


def projection():
    return build_projection_snapshot(
        projection_type="mission_control",
        workspace_id="workspace-001",
        source_checkpoint="kernel:9a3144b",
        payload={"state": "service_projection_ready", "modules": ("monitor_hitl",)},
        authority_refs=SOURCE_REFS,
        generated_at="2026-06-13T00:00:00+00:00",
    )


def test_projection_read_surface_is_read_only_and_not_authority() -> None:
    surface = build_projection_read_surface("mission-control-main", projection())

    result = validate_projection_read_surface(surface)

    assert result.accepted is True
    assert surface.read_only is True
    assert surface.canonical_authority is False
    write_evidence("projection-surfaces/read-only-not-authority.json", surface.to_evidence(), slice_id="l1gov-slice-010")


def test_projection_read_surface_rejects_authority_claim() -> None:
    surface = ProjectionReadSurface(
        surface_id="bad-surface",
        projection_ref="projection:mission_control",
        projection_type="mission_control",
        freshness_state="current",
        read_only=True,
        stale_affordance="none",
        authority_notice="projection is canonical authority",
        canonical_authority=True,
    )

    result = validate_projection_read_surface(surface)

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY


def test_stale_projection_surface_builds_refresh_request_only() -> None:
    surface = build_projection_read_surface("mission-control-main", mark_projection_stale(projection()))

    assert surface.freshness_state == "stale"
    assert surface.stale_affordance == "request_rebuild"

    command = build_projection_refresh_command(
        surface,
        actor=ActorRef(actor_id="agent:thunder", role="implementation"),
        authority_refs=SOURCE_REFS,
        workspace_id="workspace-001",
        source_checkpoint="kernel:9a3144b",
    )

    assert command.command_type == "RefreshProjection"
    assert command.affects_state is False
    assert validate_service_command_envelope(command).accepted is True
    write_evidence("projection-surfaces/stale-refresh-request.json", command.payload, slice_id="l1gov-slice-010")


def test_mission_control_view_model_reads_projection_without_authority() -> None:
    view = MissionControlViewModel(
        workspace_id="workspace-001",
        projection_surface=build_projection_read_surface("mission-control-main", projection()),
        project_summary={"state": "service_projection_ready"},
        module_summaries={"monitor_hitl": "review_required"},
        blocker_refs=("blocker:profile-stale",),
        hitl_refs=("HumanReviewTask:001",),
        feedback_refs=("FeedbackMetricTrend:001",),
        creates_authority=False,
    )

    result = validate_mission_control_view_model(view)

    assert result.accepted is True
    write_evidence("mission-control/view-model-contract.json", view.to_evidence(), slice_id="l1gov-slice-010")


def test_service_rejection_surfaces_without_local_override() -> None:
    outcome = ServiceCommandOutcome(
        command_id="cmd-complete-project",
        status=ServiceOutcomeStatus.BLOCKED,
        blocked_reason="blocked by local app no-go boundary",
        error_code=ErrorCode.NO_GO_BOUNDARY,
        projection_refresh="none",
    )

    view = build_service_outcome_view(outcome)

    assert view["status"] == "blocked"
    assert view["locally_overridden"] is False
    write_evidence("service-outcomes/rejection-surfaced.json", view, slice_id="l1gov-slice-010")
