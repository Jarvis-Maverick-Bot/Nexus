from __future__ import annotations

import pytest

from nexus.governance.errors import ErrorCode
from nexus.governance.monitor_hitl import (
    validate_component_return_action,
    validate_deliverable_evaluation_result,
    validate_human_decision,
    validate_human_review_task,
    validate_review_disposition,
)

from ._evidence import write_evidence
from .fixtures.monitor_hitl import (
    valid_evaluation_result,
    valid_human_decision,
    valid_return_action,
    valid_review_disposition,
    valid_review_task,
)


def test_human_review_task_accepts_complete_decision_task() -> None:
    result = validate_human_review_task(valid_review_task())

    assert result.accepted is True
    write_evidence("monitor-hitl/human-review-task-accepted.json", result.to_evidence(), slice_id="l1gov-slice-006")


def test_human_review_task_rejects_missing_source_refs() -> None:
    result = validate_human_review_task(valid_review_task(source_refs=()))

    assert result.accepted is False
    assert result.error_code == ErrorCode.MONITOR_HITL_RECORD_INVALID
    assert "source_refs" in result.missing_fields


@pytest.mark.parametrize("status", ("approved", "accepted", "complete", "final_pass", "production_ready"))
def test_human_review_task_rejects_completion_or_acceptance_statuses(status: str) -> None:
    result = validate_human_review_task(valid_review_task(status=status))

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    write_evidence(f"monitor-hitl/review-task-status-{status}-block.json", result.to_evidence(), slice_id="l1gov-slice-006")


def test_human_decision_accepts_authorized_recorded_decision() -> None:
    result = validate_human_decision(valid_human_decision())

    assert result.accepted is True
    write_evidence("monitor-hitl/human-decision-recorded.json", result.to_evidence(), slice_id="l1gov-slice-006")


def test_human_decision_rejects_unauthorized_actor_role() -> None:
    result = validate_human_decision(valid_human_decision(actor_role="owner"))

    assert result.accepted is False
    assert result.error_code == ErrorCode.MISSING_HUMAN_DECISION
    assert "actor role is not authorized for this decision" in result.blocked_reasons


def test_human_decision_rejects_missing_kernel_record_ref() -> None:
    result = validate_human_decision(valid_human_decision(kernel_record_ref=""))

    assert result.accepted is False
    assert result.error_code == ErrorCode.MISSING_HUMAN_DECISION
    assert "kernel_record_ref" in result.missing_fields


def test_deliverable_evaluation_result_accepts_profile_backed_acceptance() -> None:
    result = validate_deliverable_evaluation_result(valid_evaluation_result())

    assert result.accepted is True
    write_evidence("monitor-hitl/deliverable-evaluation-accepted.json", result.to_evidence(), slice_id="l1gov-slice-006")


def test_review_disposition_accepts_revise_return_protocol() -> None:
    result = validate_review_disposition(valid_review_disposition())

    assert result.accepted is True
    write_evidence("monitor-hitl/review-disposition-revise.json", result.to_evidence(), slice_id="l1gov-slice-006")


def test_component_return_action_rejects_controller_execution_action() -> None:
    result = validate_component_return_action(valid_return_action(action_type="controller execution"))

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    write_evidence("monitor-hitl/return-action-controller-execution-block.json", result.to_evidence(), slice_id="l1gov-slice-006")


@pytest.mark.parametrize(
    ("field_name", "text"),
    (
        ("reason", "please perform controller execution now"),
        ("required_correction", "perform actual dispatch"),
        ("resume_condition", "route activation is complete"),
    ),
)
def test_component_return_action_rejects_sentence_shaped_forbidden_intent(field_name: str, text: str) -> None:
    result = validate_component_return_action(valid_return_action(**{field_name: text}))

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
