from __future__ import annotations

from nexus.governance.delivery_feedback import validate_completion_continuity_packet, validate_next_cycle_proposal
from nexus.governance.errors import ErrorCode

from ._evidence import write_evidence
from .fixtures.delivery_feedback import valid_completion_packet, valid_next_cycle_proposal


def test_next_cycle_proposal_requires_impact_assessment_for_standardization_route() -> None:
    result = validate_next_cycle_proposal(valid_next_cycle_proposal(impact_assessment_ref=""))

    assert result.accepted is False
    assert result.error_code == ErrorCode.IMPACT_CONTROL_RECORD_INVALID


def test_next_cycle_proposal_accepts_candidate_only_route_with_approval_and_impact_ref() -> None:
    result = validate_next_cycle_proposal(valid_next_cycle_proposal())

    assert result.accepted is True
    write_evidence("delivery-feedback/next-cycle-proposal-candidate-only.json", result.to_evidence(), slice_id="l1gov-slice-008")


def test_next_cycle_proposal_rejects_dispatch_or_workpacket_execution_route() -> None:
    result = validate_next_cycle_proposal(valid_next_cycle_proposal(target_route="execute workpacket now"))

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY


def test_completion_packet_requires_impact_preflight_when_requesting_review() -> None:
    result = validate_completion_continuity_packet(valid_completion_packet(impact_assessment_ref=""))

    assert result.accepted is False
    assert result.error_code == ErrorCode.IMPACT_CONTROL_RECORD_INVALID


def test_completion_packet_with_impact_ref_still_does_not_claim_completion() -> None:
    result = validate_completion_continuity_packet(valid_completion_packet())

    assert result.accepted is True
    write_evidence("delivery-feedback/completion-continuity-packet-monitor-required.json", result.to_evidence(), slice_id="l1gov-slice-008")
