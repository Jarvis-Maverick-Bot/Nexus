from __future__ import annotations

from dataclasses import replace

from nexus.governance.errors import ErrorCode
from nexus.governance.kernel import AggregateState, GovernanceKernel
from nexus.governance.no_go import NoGoBoundaryPolicy
from nexus.governance.schemas import ActorRef, CommandEnvelope
from nexus.governance.service_contract import GovernanceServiceContract
from nexus.governance.tests.test_source_authority import valid_manifest as valid_source_manifest

from ._evidence import write_evidence
from .fixtures.delivery_feedback import (
    DELIVERY_SOURCE_REFS,
    valid_record_delivery_command,
    valid_record_feedback_command,
)


def test_record_delivery_command_payload_is_normalized() -> None:
    command = valid_record_delivery_command()

    assert command.command_type == "RecordDelivery"
    assert command.affects_state is True
    assert command.payload["source_refs"] == DELIVERY_SOURCE_REFS
    assert command.payload["expected_kernel_version"] == command.expected_version
    assert command.payload["idempotency_key"] == command.idempotency_key


def test_record_feedback_command_uses_expected_version_payload_contract() -> None:
    command = valid_record_feedback_command()

    assert command.command_type == "RecordFeedback"
    assert command.affects_state is True
    assert command.payload["source_refs"] == DELIVERY_SOURCE_REFS
    assert command.payload["expected_version"] == command.expected_version
    assert "expected_kernel_version" not in command.payload
    assert command.payload["idempotency_key"] == command.idempotency_key


def test_delivery_service_source_guard_runs_before_delivery_validation() -> None:
    command = CommandEnvelope(
        command_type="RecordDelivery",
        actor=ActorRef("agent:thunder", "implementation"),
        authority_refs=DELIVERY_SOURCE_REFS,
        expected_version=True,
        idempotency_key="bad-delivery-command",
        payload={},
        affects_state=True,
    )

    response = delivery_service(source_wbs_version="V0.4").handle(command)

    assert response.accepted is False
    assert response.error_code == ErrorCode.STALE_SOURCE_AUTHORITY
    assert response.message == "WBS version mismatch"
    write_evidence("service/source-before-delivery-feedback.json", response.to_evidence(), slice_id="l1gov-slice-008")


def test_delivery_service_no_go_runs_before_kernel_append() -> None:
    kernel = kernel_ready_for_delivery()

    response = delivery_service(kernel=kernel).handle(
        valid_record_delivery_command(),
        intent={"action": "delivery_raw_feedback_authority_mutation"},
    )

    assert response.accepted is False
    assert response.error_code == ErrorCode.RAW_FEEDBACK_NO_AUTHORITY_MUTATION
    assert len(kernel.records) == 0
    write_evidence("service/no-go-before-delivery-kernel.json", response.to_evidence(), slice_id="l1gov-slice-008")


def test_record_delivery_appends_kernel_record() -> None:
    kernel = kernel_ready_for_delivery()

    response = delivery_service(kernel=kernel).handle(valid_record_delivery_command())

    assert response.accepted is True
    assert response.record_ref == "krn-000001"
    assert kernel.state.state == "delivery_recorded"
    assert len(kernel.records) == 1
    write_evidence("service/record-delivery-kernel-record.json", response.to_evidence(), slice_id="l1gov-slice-008")


def test_record_feedback_appends_after_delivery_record() -> None:
    kernel = GovernanceKernel(
        state=AggregateState(
            aggregate_id="layer1-governance",
            state="delivery_recorded",
            version=9,
            authority_refs=DELIVERY_SOURCE_REFS,
        )
    )

    response = delivery_service(kernel=kernel).handle(valid_record_feedback_command())

    assert response.accepted is True
    assert kernel.state.state == "feedback_recorded"
    assert len(kernel.records) == 1
    write_evidence("service/record-feedback-kernel-record.json", response.to_evidence(), slice_id="l1gov-slice-008")


def test_delivery_service_response_envelope_covers_rejected_command() -> None:
    kernel = kernel_ready_for_delivery()
    command = replace(valid_record_delivery_command(), expected_version=True)
    command.payload["expected_kernel_version"] = True

    response = delivery_service(kernel=kernel).handle(command)

    assert response.accepted is False
    assert response.error_code == ErrorCode.DELIVERY_FEEDBACK_COMMAND_INVALID
    assert response.record_ref is None
    assert len(kernel.records) == 0


def test_record_feedback_rejects_boolean_expected_version_without_append() -> None:
    kernel = GovernanceKernel(
        state=AggregateState(
            aggregate_id="layer1-governance",
            state="delivery_recorded",
            version=9,
            authority_refs=DELIVERY_SOURCE_REFS,
        )
    )
    command = replace(valid_record_feedback_command(), expected_version=True)
    command.payload["expected_version"] = True

    response = delivery_service(kernel=kernel).handle(command)

    assert response.accepted is False
    assert response.error_code == ErrorCode.DELIVERY_FEEDBACK_COMMAND_INVALID
    assert len(kernel.records) == 0


def delivery_service(
    source_wbs_version: str = "V0.6",
    kernel: GovernanceKernel | None = None,
) -> GovernanceServiceContract:
    return GovernanceServiceContract(
        source_manifest=valid_source_manifest(wbs_version=source_wbs_version),
        no_go_policy=NoGoBoundaryPolicy.default(),
        kernel=kernel or GovernanceKernel(),
    )


def kernel_ready_for_delivery() -> GovernanceKernel:
    return GovernanceKernel(
        state=AggregateState(
            aggregate_id="layer1-governance",
            state="monitor_decision_recorded",
            version=8,
            authority_refs=DELIVERY_SOURCE_REFS,
        )
    )
