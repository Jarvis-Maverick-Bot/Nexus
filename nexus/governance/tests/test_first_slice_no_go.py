from __future__ import annotations

import pytest

from nexus.governance.errors import ErrorCode
from nexus.governance.no_go import NoGoBoundaryPolicy

from ._evidence import write_evidence
from .fixtures.first_slice_no_go import FIRST_SLICE_NO_GO_FIXTURES


@pytest.mark.parametrize("fixture_name", sorted(FIRST_SLICE_NO_GO_FIXTURES))
def test_first_slice_no_go_fixtures_block_forbidden_actions(fixture_name: str) -> None:
    fixture = FIRST_SLICE_NO_GO_FIXTURES[fixture_name]

    result = NoGoBoundaryPolicy.default().evaluate({"action": fixture["action"]})

    assert result.blocked is True
    assert result.error_code.value == fixture["expected_error"]
    payload = result.to_evidence()
    payload["fixture"] = fixture
    write_evidence(f"no-go/{fixture_name.replace('_', '-')}.json", payload)


def test_missing_evaluation_profile_uses_specific_error() -> None:
    result = NoGoBoundaryPolicy.default().evaluate({"action": "accept_without_evaluation_profile"})

    assert result.blocked is True
    assert result.error_code == ErrorCode.MISSING_EVALUATION_PROFILE


def test_raw_feedback_terms_are_preserved_for_future_feedback_slice() -> None:
    fixture = FIRST_SLICE_NO_GO_FIXTURES["raw_feedback_mutation"]

    assert "FeedbackMetricExtraction" in fixture["required_terms"]
    assert "FeedbackMetricTrend" in fixture["required_terms"]


def test_dispatch_decision_term_is_preserved_for_ack_not_acceptance() -> None:
    fixture = FIRST_SLICE_NO_GO_FIXTURES["ack_as_acceptance"]

    assert "DispatchDecision" in fixture["required_terms"]
