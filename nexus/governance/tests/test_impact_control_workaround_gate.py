from __future__ import annotations

import pytest

from nexus.governance.errors import ErrorCode
from nexus.governance.impact_control import validate_impact_assessment, validate_workaround_decision_request

from ._evidence import write_evidence
from .fixtures.impact_control import valid_assessment, valid_workaround_request


def test_workaround_review_request_without_decision_remains_review_required() -> None:
    result = validate_workaround_decision_request(valid_workaround_request(status="review_required", decision_ref=""))

    assert result.accepted is True
    write_evidence("impact-control/workaround-review-required.json", result.to_evidence(), slice_id="l1gov-slice-007")


def test_workaround_approved_without_human_decision_rejects() -> None:
    result = validate_workaround_decision_request(valid_workaround_request(status="approved", decision_ref=""))

    assert result.accepted is False
    assert result.error_code == ErrorCode.MISSING_HUMAN_DECISION


@pytest.mark.parametrize("field_name", ("expiry", "rollback_condition", "evidence_requirement"))
def test_workaround_approved_requires_expiry_rollback_and_evidence(field_name: str) -> None:
    result = validate_workaround_decision_request(valid_workaround_request(**{field_name: ""}))

    assert result.accepted is False
    assert field_name in result.missing_fields


def test_assessment_can_only_request_workaround_decision_not_approve_workaround() -> None:
    result = validate_impact_assessment(
        valid_assessment(
            actual_impact_classification="manual_workaround_requested",
            allowed_next_action="workaround_approved",
            status="monitor_required",
        )
    )

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
