from __future__ import annotations

import pytest

from nexus.governance.delivery_feedback import (
    validate_completion_continuity_packet,
    validate_feedback_record,
    validate_next_cycle_proposal,
)
from nexus.governance.errors import ErrorCode

from ._evidence import write_evidence
from .fixtures.delivery_feedback import valid_completion_packet, valid_feedback_record, valid_next_cycle_proposal


@pytest.mark.parametrize(
    "raw_summary",
    (
        "please mutate backlog now",
        "please update scope now",
        "please update success criteria now",
        "please create requirement now",
        "please approve completion now",
        "please mark complete now",
        "project accepted",
        "delivery completed",
        "mark production readiness",
        "release to production",
        "deploy to production",
        "final pass",
        "please execute workpacket now",
        "please execute work packet now",
        "please dispatch now",
        "please execute dispatch now",
        "perform actual dispatch",
        "please call controller now",
        "please execute controller now",
        "please call owner path now",
        "please request owner path now",
        "please activate route now",
        "private-agent invocation",
        "runtime invocation",
    ),
)
def test_delivery_feedback_rejects_sentence_shaped_forbidden_intent(raw_summary: str) -> None:
    result = validate_feedback_record(valid_feedback_record(raw_summary=raw_summary))

    assert result.accepted is False
    assert result.error_code in (ErrorCode.NO_GO_BOUNDARY, ErrorCode.RAW_FEEDBACK_NO_AUTHORITY_MUTATION)
    write_evidence(
        f"no-go/delivery-feedback-{raw_summary.replace(' ', '-').replace('_', '-')}.json",
        result.to_evidence(),
        slice_id="l1gov-slice-008",
    )


@pytest.mark.parametrize(
    "target_route",
    (
        "dispatch_execution",
        "actual dispatch",
        "controller call",
        "owner path call",
        "adapter call",
        "transport call",
        "route activation",
        "workpacket execution",
        "runtime invocation",
        "production_ready",
        "final_pass",
    ),
)
def test_next_cycle_proposal_rejects_forbidden_routes(target_route: str) -> None:
    result = validate_next_cycle_proposal(valid_next_cycle_proposal(target_route=target_route))

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY


@pytest.mark.parametrize(
    "requested_decision",
    ("complete project", "activate continuity", "production readiness", "deploy", "final pass"),
)
def test_completion_packet_rejects_forbidden_decision_terms(requested_decision: str) -> None:
    result = validate_completion_continuity_packet(valid_completion_packet(requested_decision=requested_decision))

    assert result.accepted is False
    assert result.error_code in (ErrorCode.NO_GO_BOUNDARY, ErrorCode.MISSING_HUMAN_DECISION)
