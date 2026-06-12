from __future__ import annotations

import pytest

from nexus.governance.errors import ErrorCode
from nexus.governance.no_go import NoGoBoundaryPolicy
from nexus.governance.source_authority import (
    REQUIRED_AUTHORITY_COMMITS,
    SourceAuthorityManifest,
    verify_source_authority,
)

from ._evidence import write_evidence
from .fixtures.first_slice_no_go import FIRST_SLICE_NO_GO_FIXTURES


ACTION_FIXTURE_NAMES = sorted(
    fixture_name for fixture_name, fixture in FIRST_SLICE_NO_GO_FIXTURES.items() if "action" in fixture
)


def source_authority_manifest(**overrides: object) -> SourceAuthorityManifest:
    values = {
        "parent_solution_design_version": "V0.8.5",
        "wbs_version": "V0.6",
        "accepted_subtopics": tuple(f"L1.11.{i}" for i in range(1, 11)),
        "integration_review_version": "V0.2",
        "integration_review_status": "Accepted",
        "final_assessment_disposition": "READY_FOR_IMPLEMENTATION_TASK_PACKAGE_PREPARATION",
        "direct_coding_disposition": "NO_GO_FOR_DIRECT_CODING",
        "slice001_package_decision": "APPROVE_FIRST_SLICE_TASK_PACKAGE",
        "slice001_authorization_decision": "AUTHORIZE_SLICE_001_IMPLEMENTATION",
        "required_commits": REQUIRED_AUTHORITY_COMMITS,
        "shared_docs_remote": "git@github.com:Nova-Mini/Nova-Jarvis-Shared-Docs.git",
        "source_root": "D:\\Nova-Jarvis-Shared-Docs",
    }
    values.update(overrides)
    return SourceAuthorityManifest(**values)


@pytest.mark.parametrize("fixture_name", ACTION_FIXTURE_NAMES)
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


def test_first_slice_no_go_fixture_suite_includes_stale_wbs() -> None:
    assert "stale_wbs_source_authority" in FIRST_SLICE_NO_GO_FIXTURES


def test_first_slice_no_go_stale_wbs_fixture_blocks_stale_source_authority() -> None:
    fixture = FIRST_SLICE_NO_GO_FIXTURES["stale_wbs_source_authority"]

    result = verify_source_authority(source_authority_manifest(**fixture["manifest_overrides"]))

    assert result.accepted is False
    assert result.error_code == fixture["expected_error"]
    assert result.expected == fixture["expected"]
    assert result.observed == fixture["observed"]
    payload = result.to_evidence()
    payload["fixture"] = fixture
    write_evidence("no-go/stale-wbs-source-authority.json", payload)


def test_raw_feedback_terms_are_preserved_for_future_feedback_slice() -> None:
    fixture = FIRST_SLICE_NO_GO_FIXTURES["raw_feedback_mutation"]

    assert "FeedbackMetricExtraction" in fixture["required_terms"]
    assert "FeedbackMetricTrend" in fixture["required_terms"]


def test_dispatch_decision_term_is_preserved_for_ack_not_acceptance() -> None:
    fixture = FIRST_SLICE_NO_GO_FIXTURES["ack_as_acceptance"]

    assert "DispatchDecision" in fixture["required_terms"]
