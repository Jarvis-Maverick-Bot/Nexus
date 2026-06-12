from __future__ import annotations

from nexus.governance.dispatch_contract import (
    validate_returned_blocked_reason,
    validate_returned_result_candidate,
)
from nexus.governance.errors import ErrorCode

from ._evidence import write_evidence
from .fixtures.dispatch_contract import valid_blocked_reason, valid_result_candidate


def test_returned_result_candidate_requires_evidence_refs() -> None:
    candidate = valid_result_candidate(evidence_refs=())

    result = validate_returned_result_candidate(candidate)

    assert result.accepted is False
    assert result.error_code == ErrorCode.DISPATCH_RETURN_INVALID
    assert result.missing_fields == ("evidence_refs",)


def test_returned_result_candidate_is_not_acceptance() -> None:
    candidate = valid_result_candidate(status="accepted")

    result = validate_returned_result_candidate(candidate)

    assert result.accepted is False
    assert result.error_code == ErrorCode.ACK_NOT_ACCEPTANCE
    assert "returned result candidate cannot accept progress" in result.blocked_reasons
    write_evidence("dispatch/result-candidate-not-acceptance.json", result.to_evidence(), slice_id="l1gov-slice-005")


def test_returned_result_candidate_accepts_evidence_backed_candidate() -> None:
    result = validate_returned_result_candidate(valid_result_candidate())

    assert result.accepted is True
    write_evidence("dispatch/result-candidate.json", result.to_evidence(), slice_id="l1gov-slice-005")


def test_returned_blocked_reason_requires_category_action_and_source_refs() -> None:
    blocked = valid_blocked_reason(category="", required_decision_or_action="", source_refs=())

    result = validate_returned_blocked_reason(blocked)

    assert result.accepted is False
    assert result.error_code == ErrorCode.DISPATCH_RETURN_INVALID
    assert result.missing_fields == ("category", "required_decision_or_action", "source_refs")


def test_returned_blocked_reason_accepts_routable_blocker() -> None:
    result = validate_returned_blocked_reason(valid_blocked_reason())

    assert result.accepted is True
    write_evidence("dispatch/returned-blocked.json", result.to_evidence(), slice_id="l1gov-slice-005")
