from __future__ import annotations

from nexus.governance.errors import ErrorCode
from nexus.governance.monitor_hitl import (
    validate_escalation_progress_gate,
    validate_escalation_record,
    validate_monitor_hitl_command,
)

from ._evidence import write_evidence
from .fixtures.monitor_hitl import valid_escalation, valid_record_escalation_command


def test_escalation_record_accepts_opened_authority_gap() -> None:
    result = validate_escalation_record(valid_escalation())

    assert result.accepted is True
    write_evidence("monitor-hitl/escalation-opened.json", result.to_evidence(), slice_id="l1gov-slice-006")


def test_escalation_record_rejects_closed_without_decision_ref() -> None:
    result = validate_escalation_record(valid_escalation(status="closed", decision_ref=""))

    assert result.accepted is False
    assert result.error_code == ErrorCode.MISSING_HUMAN_DECISION


def test_unresolved_escalation_blocks_state_progress() -> None:
    result = validate_escalation_progress_gate((valid_escalation(status="opened"),))

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    assert "unresolved escalation blocks state progress" in result.blocked_reasons
    write_evidence("monitor-hitl/unresolved-escalation-progress-block.json", result.to_evidence(), slice_id="l1gov-slice-006")


def test_record_escalation_command_validates_blocking_escalation_payload() -> None:
    result = validate_monitor_hitl_command(valid_record_escalation_command())

    assert result.accepted is True
