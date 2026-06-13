from __future__ import annotations

import pytest

from nexus.governance.errors import ErrorCode
from nexus.governance.impact_control import (
    validate_lower_layer_request_candidate,
    validate_lower_layer_request_outcome,
    validate_scope_revision_candidate,
)

from ._evidence import write_evidence
from .fixtures.impact_control import valid_lower_layer_candidate, valid_lower_layer_outcome, valid_scope_revision


def test_lower_layer_request_candidate_is_candidate_only_and_accepts() -> None:
    result = validate_lower_layer_request_candidate(valid_lower_layer_candidate())

    assert result.accepted is True
    write_evidence("impact-control/lower-layer-candidate.json", result.to_evidence(), slice_id="l1gov-slice-007")


def test_lower_layer_request_candidate_without_monitor_decision_rejects() -> None:
    result = validate_lower_layer_request_candidate(valid_lower_layer_candidate(monitor_decision_ref=""))

    assert result.accepted is False
    assert result.error_code == ErrorCode.MISSING_HUMAN_DECISION


@pytest.mark.parametrize(
    "requested_capability",
    (
        "submit lower layer request now",
        "controller_call",
        "owner_path_call",
        "route_activation",
        "workpacket_execution",
        "runtime invocation",
        "dispatch_execution",
    ),
)
def test_lower_layer_request_candidate_rejects_call_or_submission_intent(requested_capability: str) -> None:
    result = validate_lower_layer_request_candidate(
        valid_lower_layer_candidate(requested_capability_or_clarification=requested_capability)
    )

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    write_evidence(
        f"impact-control/lower-layer-candidate-no-go-{requested_capability.replace(' ', '-').replace('_', '-')}.json",
        result.to_evidence(),
        slice_id="l1gov-slice-007",
    )


def test_accepted_by_owner_candidate_does_not_imply_project_acceptance() -> None:
    result = validate_lower_layer_request_candidate(
        valid_lower_layer_candidate(status="accepted_by_owner", owner_acceptance_ref="owner-record:421")
    )

    assert result.accepted is True


def test_lower_layer_request_outcome_normalizes_owner_path_result() -> None:
    result = validate_lower_layer_request_outcome(valid_lower_layer_outcome())

    assert result.accepted is True
    write_evidence("impact-control/lower-layer-outcome.json", result.to_evidence(), slice_id="l1gov-slice-007")


@pytest.mark.parametrize(
    "expected_follow_up",
    (
        "project accepted",
        "delivery completed",
        "production readiness",
    ),
)
def test_lower_layer_request_outcome_cannot_mark_project_complete(expected_follow_up: str) -> None:
    result = validate_lower_layer_request_outcome(valid_lower_layer_outcome(expected_follow_up=expected_follow_up))

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY


def test_scope_revision_requires_monitor_decision() -> None:
    result = validate_scope_revision_candidate(valid_scope_revision(monitor_decision_ref=""))

    assert result.accepted is False
    assert result.error_code == ErrorCode.MISSING_HUMAN_DECISION
