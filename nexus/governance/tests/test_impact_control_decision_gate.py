from __future__ import annotations

from nexus.governance.errors import ErrorCode
from nexus.governance.impact_control import validate_impact_assessment, validate_impact_review_task_request

from ._evidence import write_evidence
from .fixtures.impact_control import valid_assessment, valid_review_task_request


def test_trace_required_assessment_accepts_proceed_with_trace() -> None:
    result = validate_impact_assessment(
        valid_assessment(
            impact_level="trace",
            affected_surfaces=("evidence_sufficiency",),
            actual_impact_classification="evidence_gap",
            risk_level="low",
            owner_path_outcome="not_applicable",
            allowed_next_action="proceed_with_trace",
            required_reviews=(),
            monitor_task_ref="",
            status="trace_required",
        )
    )

    assert result.accepted is True
    write_evidence("impact-control/trace-required-proceed-with-trace.json", result.to_evidence(), slice_id="l1gov-slice-007")


def test_lower_layer_owner_path_required_requires_owner_path_and_review_evidence() -> None:
    result = validate_impact_assessment(
        valid_assessment(
            status="lower_layer_owner_path_required",
            allowed_next_action="create_lower_layer_request_candidate",
            owner_path_outcome="",
            required_reviews=(),
            monitor_task_ref="",
        )
    )

    assert result.accepted is False
    assert result.error_code == ErrorCode.IMPACT_CONTROL_RECORD_INVALID
    assert "owner_path_outcome" in result.missing_fields
    assert "lower-layer request candidate requires owner_path_outcome" in result.blocked_reasons


def test_baseline_affecting_assessment_cannot_proceed_locally() -> None:
    result = validate_impact_assessment(
        valid_assessment(
            affected_surfaces=("authority",),
            allowed_next_action="proceed_local",
            status="local_only",
            required_reviews=(),
            monitor_task_ref="",
        )
    )

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY


def test_missing_evidence_requirements_blocks_assessment() -> None:
    result = validate_impact_assessment(valid_assessment(evidence_requirements=()))

    assert result.accepted is False
    assert "evidence_requirements" in result.missing_fields


def test_monitor_review_task_request_is_data_only_and_accepts() -> None:
    result = validate_impact_review_task_request(valid_review_task_request())

    assert result.accepted is True
    write_evidence("impact-control/impact-review-task-request.json", result.to_evidence(), slice_id="l1gov-slice-007")


def test_direct_ui_or_controller_event_cannot_serve_as_review_decision() -> None:
    result = validate_impact_review_task_request(valid_review_task_request(options=("controller_approval",)))

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
