from __future__ import annotations

from nexus.governance.dispatch_contract import validate_dispatch_command
from nexus.governance.errors import ErrorCode
from nexus.governance.kernel import AggregateState, GovernanceKernel
from nexus.governance.no_go import NoGoBoundaryPolicy
from nexus.governance.schemas import ActorRef, CommandEnvelope
from nexus.governance.service_contract import GovernanceServiceContract
from nexus.governance.tests.test_source_authority import valid_manifest as valid_source_manifest

from ._evidence import write_evidence
from .fixtures.dispatch_contract import (
    DISPATCH_SOURCE_REFS,
    valid_evaluate_dispatch_readiness_command,
    valid_handoff_candidate_command,
    valid_normalize_return_command,
)


def test_evaluate_dispatch_readiness_command_payload_is_normalized() -> None:
    command = valid_evaluate_dispatch_readiness_command()

    result = validate_dispatch_command(command)

    assert result.accepted is True
    assert command.affects_state is False
    assert command.payload["source_refs"] == DISPATCH_SOURCE_REFS
    assert command.payload["expected_version"] == command.expected_version
    assert command.payload["idempotency_key"] == command.idempotency_key
    write_evidence(
        "dispatch/evaluate-readiness-command.json",
        {"command_type": command.command_type, "payload": command.payload, "validation": result.to_evidence()},
        slice_id="l1gov-slice-005",
    )


def test_handoff_candidate_command_rejects_runtime_invocation_payload() -> None:
    command = valid_handoff_candidate_command()
    command.payload["runtime_invocation"] = {"agent": "private-agent", "route": "live"}

    result = validate_dispatch_command(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    assert result.message == "Dispatch Contract command cannot execute runtime or controller work"


def test_handoff_candidate_command_rejects_actual_dispatch_action() -> None:
    command = valid_handoff_candidate_command()
    command.payload["requested_action"] = "dispatch_execute"

    result = validate_dispatch_command(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    write_evidence("dispatch/actual-dispatch-block.json", result.to_evidence(), slice_id="l1gov-slice-005")


def test_normalize_dispatch_return_rejects_ack_as_acceptance() -> None:
    command = valid_normalize_return_command(return_kind="ack", result_refs=(), evidence_refs=())
    command.payload["status"] = "accepted"

    result = validate_dispatch_command(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.ACK_NOT_ACCEPTANCE
    assert result.message == "ACK/progress/controller output is not Layer 1 acceptance"


def test_dispatch_command_rejects_boolean_expected_version() -> None:
    command = valid_evaluate_dispatch_readiness_command(expected_version=True)

    result = validate_dispatch_command(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.DISPATCH_COMMAND_INVALID
    assert result.message == "expected_version must be a non-negative integer"


def test_dispatch_command_rejects_idempotency_mismatch() -> None:
    command = valid_normalize_return_command()
    command.payload["idempotency_key"] = "different-key"

    result = validate_dispatch_command(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.DISPATCH_COMMAND_INVALID
    assert result.message == "payload idempotency_key must match envelope idempotency_key"


def test_dispatch_service_source_guard_runs_before_dispatch_validation() -> None:
    command = CommandEnvelope(
        command_type="EvaluateDispatchReadiness",
        actor=ActorRef("agent:thunder", "implementation"),
        authority_refs=DISPATCH_SOURCE_REFS,
        expected_version=True,
        idempotency_key="bad-dispatch-command",
        payload={},
        affects_state=False,
    )

    response = dispatch_service(source_wbs_version="V0.4").handle(command)

    assert response.accepted is False
    assert response.error_code == ErrorCode.STALE_SOURCE_AUTHORITY
    assert response.message == "WBS version mismatch"
    write_evidence("service/source-before-dispatch.json", response.to_evidence(), slice_id="l1gov-slice-005")


def test_dispatch_service_no_go_runs_before_kernel() -> None:
    kernel = kernel_ready_for_dispatch_projection()
    command = valid_evaluate_dispatch_readiness_command()

    response = dispatch_service(kernel=kernel).handle(command, intent={"action": "dispatch_actual_execution"})

    assert response.accepted is False
    assert response.error_code == ErrorCode.NO_GO_BOUNDARY
    assert len(kernel.records) == 0
    write_evidence("service/no-go-before-dispatch.json", response.to_evidence(), slice_id="l1gov-slice-005")


def test_dispatch_service_returns_projection_without_kernel_append() -> None:
    kernel = kernel_ready_for_dispatch_projection()

    response = dispatch_service(kernel=kernel).handle(valid_evaluate_dispatch_readiness_command())

    assert response.accepted is True
    assert response.projection_ref == "projection:dispatch-readiness"
    assert response.aggregate_ref is None
    assert response.record_ref is None
    assert len(kernel.records) == 0
    write_evidence("service/dispatch-projection-response.json", response.to_evidence(), slice_id="l1gov-slice-005")


def dispatch_service(
    source_wbs_version: str = "V0.6",
    kernel: GovernanceKernel | None = None,
) -> GovernanceServiceContract:
    return GovernanceServiceContract(
        source_manifest=valid_source_manifest(wbs_version=source_wbs_version),
        no_go_policy=NoGoBoundaryPolicy.default(),
        kernel=kernel or GovernanceKernel(),
    )


def kernel_ready_for_dispatch_projection() -> GovernanceKernel:
    return GovernanceKernel(
        state=AggregateState(
            aggregate_id="layer1-governance",
            state="initiation_ready",
            version=7,
            authority_refs=DISPATCH_SOURCE_REFS,
        )
    )
