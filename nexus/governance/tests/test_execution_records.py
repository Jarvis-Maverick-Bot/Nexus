from __future__ import annotations

import pytest

from nexus.governance.errors import ErrorCode
from nexus.governance.execution import (
    validate_approved_plan_ref,
    validate_execution_output_base,
    validate_packet_map,
    validate_packet_readiness_decision,
)

from ._evidence import write_evidence
from .fixtures.execution import (
    valid_approved_plan_ref,
    valid_packet_map,
    valid_readiness_decision,
)


def test_execution_output_base_requires_approved_plan_and_workspace_manifest() -> None:
    item = valid_packet_map(approved_plan_ref="", workspace_manifest_ref="")

    result = validate_execution_output_base(item)

    assert result.accepted is False
    assert result.error_code == ErrorCode.EXECUTION_RECORD_INVALID
    assert result.missing_fields == ("approved_plan_ref", "workspace_manifest_ref")
    write_evidence("execution/base-required-field-block.json", result.to_evidence(), slice_id="l1gov-slice-004")


def test_approved_plan_ref_requires_human_decision_and_kernel_baseline() -> None:
    ref = valid_approved_plan_ref(approval_decision_ref="", kernel_acceptance_record_ref="")

    result = validate_approved_plan_ref(ref)

    assert result.accepted is False
    assert result.error_code == ErrorCode.MISSING_HUMAN_DECISION
    assert "approved plan ref requires HumanDecision evidence" in result.blocked_reasons
    assert "approved plan ref requires Kernel baseline-entry evidence" in result.blocked_reasons
    write_evidence("execution/unapproved-plan-ref-block.json", result.to_evidence(), slice_id="l1gov-slice-004")


def test_approved_plan_ref_accepts_human_decision_and_kernel_baseline() -> None:
    result = validate_approved_plan_ref(valid_approved_plan_ref())

    assert result.accepted is True
    write_evidence("execution/approved-plan-ref-valid.json", result.to_evidence(), slice_id="l1gov-slice-004")


def test_packet_map_accepts_complete_packet_index() -> None:
    result = validate_packet_map(valid_packet_map())

    assert result.accepted is True
    write_evidence("execution/packet-map-valid.json", result.to_evidence(), slice_id="l1gov-slice-004")


def test_packet_map_requires_packet_ids_and_dependency_graph() -> None:
    item = valid_packet_map(packet_ids=(), dependency_graph_ref="")

    result = validate_packet_map(item)

    assert result.accepted is False
    assert result.error_code == ErrorCode.EXECUTION_RECORD_INVALID
    assert result.missing_fields == ("packet_ids", "dependency_graph_ref")
    write_evidence("execution/packet-map-field-block.json", result.to_evidence(), slice_id="l1gov-slice-004")


def test_packet_readiness_decision_rejects_downstream_dispatch_statuses() -> None:
    item = valid_readiness_decision(status="dispatched", readiness_status="dispatched")

    result = validate_packet_readiness_decision(item)

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    assert "Slice 004 readiness cannot claim dispatched" in result.blocked_reasons
    write_evidence(
        "execution/readiness-dispatch-boundary-block.json",
        result.to_evidence(),
        slice_id="l1gov-slice-004",
    )


@pytest.mark.parametrize("status", ("submitted", "active", "closed"))
def test_packet_readiness_decision_rejects_non_slice004_lifecycle_statuses(status: str) -> None:
    item = valid_readiness_decision(status=status, readiness_status=status)

    result = validate_packet_readiness_decision(item)

    assert result.accepted is False
    assert result.error_code == ErrorCode.EXECUTION_RECORD_INVALID
    assert f"PacketReadinessDecision status is not legal in Slice 004: {status}" in result.blocked_reasons
    write_evidence(
        f"execution/readiness-status-{status}-block.json",
        result.to_evidence(),
        slice_id="l1gov-slice-004",
    )
