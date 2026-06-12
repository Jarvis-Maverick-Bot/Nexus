from __future__ import annotations

from nexus.governance.errors import ErrorCode
from nexus.governance.kernel import AggregateState, GovernanceKernel
from nexus.governance.no_go import NoGoBoundaryPolicy
from nexus.governance.schemas import ActorRef, CommandEnvelope
from nexus.governance.service_contract import GovernanceServiceContract
from nexus.governance.execution import validate_execution_command
from nexus.governance.tests.test_source_authority import valid_manifest as valid_source_manifest

from ._evidence import write_evidence
from .fixtures.execution import (
    SOURCE_REFS,
    valid_create_workpacket_command,
    valid_mark_packet_ready_command,
    valid_repair_request_command,
    valid_supersede_command,
    valid_validate_packet_map_command,
)


def test_create_layer1_workpacket_command_payload_is_normalized() -> None:
    command = valid_create_workpacket_command()

    result = validate_execution_command(command)

    assert result.accepted is True
    assert command.command_type == "CreateLayer1WorkPacket"
    assert command.payload["source_refs"] == SOURCE_REFS
    assert command.payload["expected_version"] == command.expected_version
    assert command.payload["idempotency_key"] == command.idempotency_key
    write_evidence(
        "execution/create-workpacket-command.json",
        {"command_type": command.command_type, "payload": command.payload, "validation": result.to_evidence()},
        slice_id="l1gov-slice-004",
    )


def test_validate_packet_map_command_payload_is_normalized() -> None:
    command = valid_validate_packet_map_command()

    result = validate_execution_command(command)

    assert result.accepted is True
    assert command.command_type == "ValidatePacketMap"
    assert command.payload["source_refs"] == SOURCE_REFS
    write_evidence(
        "execution/validate-packet-map-command.json",
        {"command_type": command.command_type, "payload": command.payload, "validation": result.to_evidence()},
        slice_id="l1gov-slice-004",
    )


def test_execution_command_rejects_boolean_expected_version() -> None:
    command = valid_mark_packet_ready_command(expected_version=True)

    result = validate_execution_command(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.EXECUTION_COMMAND_INVALID
    assert result.message == "expected_version must be a non-negative integer"
    write_evidence("execution/expected-version-bool-block.json", result.to_evidence(), slice_id="l1gov-slice-004")


def test_execution_command_rejects_payload_envelope_mismatch() -> None:
    command = valid_repair_request_command()
    command.payload["expected_version"] = command.expected_version + 1

    result = validate_execution_command(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.EXECUTION_COMMAND_INVALID
    assert result.message == "payload expected_version must match envelope expected_version"


def test_create_workpacket_command_requires_plan_decision_and_kernel_evidence() -> None:
    command = valid_create_workpacket_command()
    command.payload["approval_decision_ref"] = ""
    command.payload["kernel_acceptance_record_ref"] = ""

    result = validate_execution_command(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.EXECUTION_COMMAND_INVALID
    assert result.message == "approval_decision_ref is required"


def test_create_workpacket_command_rejects_boolean_packet_version() -> None:
    command = valid_create_workpacket_command()
    command.payload["packet_version"] = True

    result = validate_execution_command(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.EXECUTION_COMMAND_INVALID
    assert result.message == "packet_version must be a positive integer"


def test_execution_command_rejects_idempotency_key_mismatch() -> None:
    command = valid_supersede_command()
    command.payload["idempotency_key"] = "different-key"

    result = validate_execution_command(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.EXECUTION_COMMAND_INVALID
    assert result.message == "payload idempotency_key must match envelope idempotency_key"


def test_mark_packet_ready_rejects_root_dispatch_status() -> None:
    command = valid_mark_packet_ready_command()
    command.payload["status"] = "accepted_for_dispatch"

    result = validate_execution_command(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    assert result.message == "packet readiness command cannot dispatch or complete work"


def test_mark_packet_ready_rejects_dispatch_or_completion_payloads() -> None:
    command = valid_mark_packet_ready_command()
    command.payload["readiness_status"] = "dispatched"
    command.payload["dispatch_ref"] = "dispatch:wp-421-001"

    result = validate_execution_command(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    assert result.message == "packet readiness command cannot dispatch or complete work"


def test_supersede_workpacket_rejects_new_payload_controller_ref() -> None:
    command = valid_supersede_command()
    command.payload["new_packet_payload"]["controller_ref"] = "controller:4.19"

    result = validate_execution_command(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    assert result.message == "packet readiness command cannot dispatch or complete work"


def test_repair_request_rejects_scope_change_without_human_decision() -> None:
    command = valid_repair_request_command()
    command.payload["scope_change_ref"] = "scope-change:wp-421-001"

    result = validate_execution_command(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.MISSING_HUMAN_DECISION
    assert result.message == "scope-changing repair requires HumanDecision ref"


def test_service_source_guard_runs_before_execution_validation() -> None:
    command = CommandEnvelope(
        command_type="CreateLayer1WorkPacket",
        actor=ActorRef("agent:thunder", "implementation"),
        authority_refs=SOURCE_REFS,
        expected_version=True,
        idempotency_key="bad-command",
        payload={},
        affects_state=False,
    )

    response = execution_service(source_wbs_version="V0.4").handle(command)

    assert response.accepted is False
    assert response.error_code == ErrorCode.STALE_SOURCE_AUTHORITY
    assert response.message == "WBS version mismatch"
    write_evidence("service/source-before-execution.json", response.to_evidence(), slice_id="l1gov-slice-004")


def test_service_no_go_runs_before_kernel_for_execution_command() -> None:
    kernel = kernel_ready_for_execution_projection()
    command = valid_create_workpacket_command()

    response = execution_service(kernel=kernel).handle(
        command,
        intent={"action": "execution_direct_419_controller_call"},
    )

    assert response.accepted is False
    assert response.error_code == ErrorCode.NO_GO_BOUNDARY
    assert len(kernel.records) == 0
    write_evidence("service/no-go-before-execution.json", response.to_evidence(), slice_id="l1gov-slice-004")


def test_service_returns_normalized_projection_response_for_workpacket() -> None:
    response = execution_service(kernel=kernel_ready_for_execution_projection()).handle(valid_create_workpacket_command())

    assert response.accepted is True
    assert response.projection_ref == "projection:execution-workpacket"
    assert response.aggregate_ref is None
    assert response.record_ref is None
    write_evidence("service/workpacket-response.json", response.to_evidence(), slice_id="l1gov-slice-004")


def execution_service(
    source_wbs_version: str = "V0.6",
    kernel: GovernanceKernel | None = None,
) -> GovernanceServiceContract:
    return GovernanceServiceContract(
        source_manifest=valid_source_manifest(wbs_version=source_wbs_version),
        no_go_policy=NoGoBoundaryPolicy.default(),
        kernel=kernel or GovernanceKernel(),
    )


def kernel_ready_for_execution_projection() -> GovernanceKernel:
    return GovernanceKernel(
        state=AggregateState(
            aggregate_id="layer1-governance",
            state="initiation_ready",
            version=5,
            authority_refs=SOURCE_REFS,
        )
    )
