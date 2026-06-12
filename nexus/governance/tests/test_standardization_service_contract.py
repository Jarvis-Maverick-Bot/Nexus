from __future__ import annotations

from nexus.governance.errors import ErrorCode
from nexus.governance.kernel import AggregateState, GovernanceKernel
from nexus.governance.no_go import NoGoBoundaryPolicy
from nexus.governance.schemas import ActorRef, CommandEnvelope
from nexus.governance.service_contract import GovernanceServiceContract
from nexus.governance.standardization import validate_standardization_command
from nexus.governance.tests.test_source_authority import valid_manifest as valid_source_manifest

from ._evidence import write_evidence
from .fixtures.standardization import (
    SOURCE_REFS,
    valid_create_approval_packet_command,
    valid_submit_draft_command,
    valid_supersede_plan_command,
)


def test_submit_standardization_draft_command_payload_is_normalized() -> None:
    command = valid_submit_draft_command()

    result = validate_standardization_command(command)

    assert result.accepted is True
    assert command.command_type == "SubmitStandardizationDraft"
    assert command.payload["source_refs"] == SOURCE_REFS
    assert command.payload["expected_version"] == command.expected_version
    assert command.payload["idempotency_key"] == command.idempotency_key
    write_evidence(
        "standardization/submit-draft-command-envelope.json",
        {"command_type": command.command_type, "payload": command.payload, "validation": result.to_evidence()},
        slice_id="l1gov-slice-003",
    )


def test_standardization_command_rejects_boolean_expected_version() -> None:
    command = valid_submit_draft_command(expected_version=True)

    result = validate_standardization_command(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.STANDARDIZATION_COMMAND_INVALID
    assert result.message == "expected_version must be a non-negative integer"
    write_evidence(
        "standardization/expected-version-bool-block.json",
        result.to_evidence(),
        slice_id="l1gov-slice-003",
    )


def test_standardization_command_rejects_payload_envelope_mismatch() -> None:
    command = valid_supersede_plan_command()
    command.payload["expected_version"] = command.expected_version + 1
    command.payload["idempotency_key"] = "different-idempotency-key"

    result = validate_standardization_command(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.STANDARDIZATION_COMMAND_INVALID
    assert result.message == "payload expected_version must match envelope expected_version"


def test_create_approval_packet_rejects_self_approval() -> None:
    command = valid_create_approval_packet_command(requested_decision="approved")

    result = validate_standardization_command(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.MISSING_HUMAN_DECISION
    assert result.message == "approval packet cannot approve itself"
    write_evidence(
        "standardization/self-approval-block.json",
        result.to_evidence(),
        slice_id="l1gov-slice-003",
    )


def test_create_approval_packet_rejects_embedded_decision_result() -> None:
    command = valid_create_approval_packet_command()
    command.payload["decision_result_ref"] = "human-decision:approved"

    result = validate_standardization_command(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.MISSING_HUMAN_DECISION
    assert result.message == "approval packet cannot include decision_result_ref"


def test_service_source_guard_runs_before_standardization_validation() -> None:
    command = CommandEnvelope(
        command_type="SubmitStandardizationDraft",
        actor=ActorRef("agent:thunder", "implementation"),
        authority_refs=SOURCE_REFS,
        expected_version=True,
        idempotency_key="bad-command",
        payload={},
        affects_state=False,
    )

    response = standardization_service(source_wbs_version="V0.4").handle(command)

    assert response.accepted is False
    assert response.error_code == ErrorCode.STALE_SOURCE_AUTHORITY
    assert response.message == "WBS version mismatch"
    write_evidence("service/source-before-standardization.json", response.to_evidence(), slice_id="l1gov-slice-003")


def test_service_no_go_runs_before_kernel_for_standardization_command() -> None:
    kernel = kernel_ready_for_standardization_projection()
    command = valid_create_approval_packet_command()

    response = standardization_service(kernel=kernel).handle(
        command,
        intent={"action": "standardization_runtime_dispatch"},
    )

    assert response.accepted is False
    assert response.error_code == ErrorCode.NO_GO_BOUNDARY
    assert len(kernel.records) == 0
    write_evidence("service/no-go-before-standardization.json", response.to_evidence(), slice_id="l1gov-slice-003")


def test_service_returns_normalized_projection_response_for_approval_packet() -> None:
    response = standardization_service(kernel=kernel_ready_for_standardization_projection()).handle(
        valid_create_approval_packet_command()
    )

    assert response.accepted is True
    assert response.projection_ref == "projection:standardization-approval-packet"
    assert response.aggregate_ref is None
    assert response.record_ref is None
    assert response.to_evidence() == {
        "accepted": True,
        "aggregate_ref": None,
        "error_code": None,
        "evidence_refs": [],
        "message": "",
        "projection_ref": "projection:standardization-approval-packet",
        "record_ref": None,
        "retryable": False,
    }
    write_evidence(
        "service/approval-packet-response.json",
        response.to_evidence(),
        slice_id="l1gov-slice-003",
    )


def standardization_service(
    source_wbs_version: str = "V0.6",
    kernel: GovernanceKernel | None = None,
) -> GovernanceServiceContract:
    return GovernanceServiceContract(
        source_manifest=valid_source_manifest(wbs_version=source_wbs_version),
        no_go_policy=NoGoBoundaryPolicy.default(),
        kernel=kernel or GovernanceKernel(),
    )


def kernel_ready_for_standardization_projection() -> GovernanceKernel:
    return GovernanceKernel(
        state=AggregateState(
            aggregate_id="layer1-governance",
            state="initiation_ready",
            version=4,
            authority_refs=SOURCE_REFS,
        )
    )
