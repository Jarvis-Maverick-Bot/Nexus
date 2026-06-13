from __future__ import annotations

import pytest

from nexus.governance.errors import ErrorCode
from nexus.governance.impact_control import (
    APPROVED_AFFECTED_SURFACES,
    APPROVED_GAP_TYPES,
    validate_impact_assessment,
    validate_impact_control_request,
    validate_layer_impact_detected,
)

from ._evidence import write_evidence
from .fixtures.impact_control import valid_assessment, valid_impact_request, valid_layer_impact, valid_local_assessment


def test_valid_impact_control_request_accepts() -> None:
    result = validate_impact_control_request(valid_impact_request())

    assert result.accepted is True
    write_evidence("impact-control/valid-impact-request.json", result.to_evidence(), slice_id="l1gov-slice-007")


@pytest.mark.parametrize(
    "field_name",
    ("caller_component", "source_refs", "evidence_refs", "target_refs", "suspected_impact_surfaces"),
)
def test_impact_control_request_rejects_missing_required_fields(field_name: str) -> None:
    result = validate_impact_control_request(valid_impact_request(**{field_name: () if field_name.endswith("refs") or field_name == "suspected_impact_surfaces" else ""}))

    assert result.accepted is False
    assert result.error_code == ErrorCode.IMPACT_CONTROL_RECORD_INVALID
    assert field_name in result.missing_fields


@pytest.mark.parametrize(
    "proposed_action",
    (
        "direct 4.19 controller call",
        "direct_35_controller_call",
        "please call owner path now",
        "please activate route now",
        "please execute workpacket now",
        "perform actual dispatch",
        "mark production readiness",
        "mark project accepted",
        "mark delivery completed",
        "submit_lower_layer_request",
        "runtime invocation",
        "private_agent_invocation",
        "config_mutation",
        "credential_mutation",
    ),
)
def test_impact_control_request_rejects_forbidden_action_intent(proposed_action: str) -> None:
    result = validate_impact_control_request(valid_impact_request(proposed_action=proposed_action))

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    write_evidence(
        f"impact-control/request-no-go-{proposed_action.replace(' ', '-').replace('_', '-')}.json",
        result.to_evidence(),
        slice_id="l1gov-slice-007",
    )


def test_valid_local_assessment_accepts_proceed_local() -> None:
    result = validate_impact_assessment(valid_local_assessment())

    assert result.accepted is True
    write_evidence("impact-control/local-assessment-proceed-local.json", result.to_evidence(), slice_id="l1gov-slice-007")


def test_monitor_required_assessment_requires_review_and_monitor_task() -> None:
    result = validate_impact_assessment(valid_assessment(required_reviews=(), monitor_task_ref=""))

    assert result.accepted is False
    assert result.error_code == ErrorCode.IMPACT_CONTROL_RECORD_INVALID
    assert "monitor_required assessments require required_reviews" in result.blocked_reasons
    assert "monitor_task_ref" in result.missing_fields


def test_unclear_affected_surface_must_fail_closed_as_blocked() -> None:
    result = validate_impact_assessment(
        valid_assessment(
            affected_surfaces=("unclear",),
            allowed_next_action="open_monitor_review",
            status="monitor_required",
            blocked_reason="",
        )
    )

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    write_evidence("impact-control/unclear-surface-fail-closed.json", result.to_evidence(), slice_id="l1gov-slice-007")


def test_blocked_assessment_requires_blocked_reason() -> None:
    result = validate_impact_assessment(valid_assessment(status="blocked", allowed_next_action="block", blocked_reason=""))

    assert result.accepted is False
    assert "blocked assessments require blocked_reason" in result.blocked_reasons


def test_unknown_allowed_next_action_rejects() -> None:
    result = validate_impact_assessment(valid_assessment(allowed_next_action="dispatch_execute"))

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY


def test_approved_affected_surfaces_and_gap_types_are_declared() -> None:
    assert "lower_layer_dependency" in APPROVED_AFFECTED_SURFACES
    assert "unclear" in APPROVED_AFFECTED_SURFACES
    assert "capability_gap_layer2" in APPROVED_GAP_TYPES
    assert "manual_workaround_requested" in APPROVED_GAP_TYPES


def test_layer_impact_detected_accepts_approved_taxonomy() -> None:
    result = validate_layer_impact_detected(valid_layer_impact())

    assert result.accepted is True
    write_evidence("impact-control/layer-impact-detected.json", result.to_evidence(), slice_id="l1gov-slice-007")


def test_layer_impact_detected_rejects_unknown_layer_or_gap_type() -> None:
    layer_result = validate_layer_impact_detected(valid_layer_impact(affected_layer="layer_9"))
    gap_result = validate_layer_impact_detected(valid_layer_impact(gap_type="ship_it"))

    assert layer_result.accepted is False
    assert gap_result.accepted is False
    assert "affected_layer rejected: layer_9" in layer_result.blocked_reasons
    assert "gap_type rejected: ship_it" in gap_result.blocked_reasons
