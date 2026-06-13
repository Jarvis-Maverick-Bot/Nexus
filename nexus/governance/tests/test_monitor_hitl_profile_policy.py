from __future__ import annotations

import pytest

from nexus.governance.errors import ErrorCode
from nexus.governance.monitor_hitl import (
    validate_deliverable_evaluation_profile_ref,
    validate_deliverable_evaluation_result,
    validate_monitor_hitl_command,
)

from ._evidence import write_evidence
from .fixtures.monitor_hitl import (
    valid_evaluate_deliverable_command,
    valid_evaluation_result,
    valid_profile_ref,
)


def test_deliverable_evaluation_profile_ref_accepts_approved_profile() -> None:
    result = validate_deliverable_evaluation_profile_ref(valid_profile_ref())

    assert result.accepted is True
    write_evidence("monitor-hitl/profile-ref-approved.json", result.to_evidence(), slice_id="l1gov-slice-006")


@pytest.mark.parametrize("status", ("missing", "stale", "draft", "superseded", "deprecated", "conflicting"))
def test_deliverable_evaluation_profile_ref_rejects_missing_or_stale_profile(status: str) -> None:
    profile = valid_profile_ref(status=status)

    result = validate_deliverable_evaluation_profile_ref(profile)

    assert result.accepted is False
    assert result.error_code == ErrorCode.MISSING_EVALUATION_PROFILE
    write_evidence(f"monitor-hitl/profile-{status}-block.json", result.to_evidence(), slice_id="l1gov-slice-006")


def test_deliverable_evaluation_result_rejects_acceptance_without_evidence_mapping() -> None:
    result = validate_deliverable_evaluation_result(valid_evaluation_result(evidence_mapping_result=""))

    assert result.accepted is False
    assert result.error_code == ErrorCode.MISSING_EVALUATION_PROFILE
    assert "evidence_mapping_result" in result.missing_fields


def test_evaluate_deliverable_command_rejects_stale_profile_before_acceptance() -> None:
    command = valid_evaluate_deliverable_command(
        evaluation_profile_ref=valid_profile_ref(status="stale"),
        evaluation_result=valid_evaluation_result(evaluation_profile_ref=valid_profile_ref(status="stale").__dict__),
    )

    result = validate_monitor_hitl_command(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.MISSING_EVALUATION_PROFILE
    write_evidence("monitor-hitl/evaluate-deliverable-stale-profile-block.json", result.to_evidence(), slice_id="l1gov-slice-006")


@pytest.mark.parametrize("status", ("pending", "accepted", "revise", "rejected", "blocked", "stale", "superseded"))
def test_deliverable_evaluation_result_accepts_legal_verdict_states(status: str) -> None:
    verdict = "accepted" if status == "accepted" else status

    result = validate_deliverable_evaluation_result(valid_evaluation_result(status=status, verdict=verdict))

    assert result.accepted is True
