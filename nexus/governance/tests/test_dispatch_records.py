from __future__ import annotations

import pytest

from nexus.governance.dispatch_contract import (
    validate_dispatch_decision,
    validate_dispatch_output_base,
    validate_dispatch_readiness_review,
    validate_handoff_candidate,
)
from nexus.governance.errors import ErrorCode

from ._evidence import write_evidence
from .fixtures.dispatch_contract import (
    valid_dispatch_decision,
    valid_handoff_candidate,
    valid_readiness_review,
)


def test_dispatch_output_base_requires_packet_kernel_and_correlation_refs() -> None:
    item = valid_readiness_review(packet_id="", kernel_packet_record_ref="", correlation_id="", idempotency_key="")

    result = validate_dispatch_output_base(item)

    assert result.accepted is False
    assert result.error_code == ErrorCode.DISPATCH_RECORD_INVALID
    assert result.missing_fields == ("packet_id", "kernel_packet_record_ref", "correlation_id", "idempotency_key")
    write_evidence("dispatch/base-required-field-block.json", result.to_evidence(), slice_id="l1gov-slice-005")


def test_dispatch_readiness_review_accepts_passed_matrix() -> None:
    result = validate_dispatch_readiness_review(valid_readiness_review())

    assert result.accepted is True
    write_evidence("dispatch/readiness-accepted.json", result.to_evidence(), slice_id="l1gov-slice-005")


def test_dispatch_readiness_review_requires_blocked_reasons_when_failed() -> None:
    review = valid_readiness_review(status="failed", result="failed", blocked_reasons=())

    result = validate_dispatch_readiness_review(review)

    assert result.accepted is False
    assert result.error_code == ErrorCode.DISPATCH_RECORD_INVALID
    assert "failed readiness review requires blocked reasons" in result.blocked_reasons


def test_dispatch_decision_accepts_boundary_only_accepted_for_dispatch() -> None:
    result = validate_dispatch_decision(valid_dispatch_decision())

    assert result.accepted is True
    write_evidence("dispatch/decision-accepted.json", result.to_evidence(), slice_id="l1gov-slice-005")


@pytest.mark.parametrize("status", ("dispatched", "accepted", "complete", "final_pass"))
def test_dispatch_decision_rejects_runtime_or_acceptance_statuses(status: str) -> None:
    decision = valid_dispatch_decision(status=status)

    result = validate_dispatch_decision(decision)

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    assert f"DispatchDecision cannot claim {status}" in result.blocked_reasons
    write_evidence(f"dispatch/decision-status-{status}-block.json", result.to_evidence(), slice_id="l1gov-slice-005")


def test_handoff_candidate_accepts_non_live_contract() -> None:
    result = validate_handoff_candidate(valid_handoff_candidate())

    assert result.accepted is True
    write_evidence("dispatch/handoff-candidate.json", result.to_evidence(), slice_id="l1gov-slice-005")


def test_handoff_candidate_rejects_live_controller_payload() -> None:
    candidate = valid_handoff_candidate(controller_call={"controller": "4.19", "action": "dispatch"})

    result = validate_handoff_candidate(candidate)

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    assert "handoff candidate must remain non-live" in result.blocked_reasons
    write_evidence("dispatch/direct-controller-block.json", result.to_evidence(), slice_id="l1gov-slice-005")


def test_handoff_candidate_rejects_runtime_dispatch_as_expected_output() -> None:
    candidate = valid_handoff_candidate(expected_outputs=("runtime dispatch",))

    result = validate_handoff_candidate(candidate)

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    assert "handoff candidate expected_outputs cannot request runtime dispatch" in result.blocked_reasons
    write_evidence("dispatch/handoff-expected-output-runtime-block.json", result.to_evidence(), slice_id="l1gov-slice-005")


@pytest.mark.parametrize(
    "expected_output",
    (
        "dispatch",
        "controller call",
        "private-agent invocation",
        "controller execution",
        "controller request",
        "controller action",
        "adapter call",
        "route activation",
    ),
)
def test_handoff_candidate_rejects_execution_intent_expected_outputs(expected_output: str) -> None:
    candidate = valid_handoff_candidate(expected_outputs=(expected_output,))

    result = validate_handoff_candidate(candidate)

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    assert "handoff candidate expected_outputs cannot request dispatch/controller/runtime execution" in result.blocked_reasons
    write_evidence(
        f"dispatch/handoff-expected-output-{expected_output.replace(' ', '-').replace('/', '-')}-block.json",
        result.to_evidence(),
        slice_id="l1gov-slice-005",
    )
