from __future__ import annotations

from nexus.governance.errors import ErrorCode
from nexus.governance.execution import validate_layer1_workpacket

from ._evidence import write_evidence
from .fixtures.execution import valid_workpacket


def test_layer1_workpacket_accepts_complete_review_contract() -> None:
    result = validate_layer1_workpacket(valid_workpacket())

    assert result.accepted is True
    write_evidence("execution/workpacket-valid.json", result.to_evidence(), slice_id="l1gov-slice-004")


def test_layer1_workpacket_requires_no_go_outputs_evidence_and_stop_rules() -> None:
    packet = valid_workpacket(no_go=(), expected_outputs=(), evidence_contract_ref="", stop_rules=())

    result = validate_layer1_workpacket(packet)

    assert result.accepted is False
    assert result.error_code == ErrorCode.EXECUTION_WORKPACKET_INVALID
    assert result.missing_fields == ("no_go", "expected_outputs", "evidence_contract_ref", "stop_rules")
    write_evidence("execution/workpacket-incomplete.json", result.to_evidence(), slice_id="l1gov-slice-004")


def test_layer1_workpacket_rejects_owner_self_approval() -> None:
    packet = valid_workpacket(owner_role="implementation-agent", reviewer_role="implementation-agent")

    result = validate_layer1_workpacket(packet)

    assert result.accepted is False
    assert result.error_code == ErrorCode.MISSING_HUMAN_DECISION
    assert "owner role cannot self-review packet readiness" in result.blocked_reasons
    write_evidence("execution/owner-self-approval-block.json", result.to_evidence(), slice_id="l1gov-slice-004")


def test_layer1_workpacket_rejects_dispatch_or_controller_refs() -> None:
    packet = valid_workpacket(controller_ref="4.19-controller", dispatch_ref="dispatch:wp-421-001")

    result = validate_layer1_workpacket(packet)

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    assert "Layer1WorkPacket cannot include direct 4.19 controller refs" in result.blocked_reasons
    assert "Layer1WorkPacket cannot include dispatch refs in Slice 004" in result.blocked_reasons
