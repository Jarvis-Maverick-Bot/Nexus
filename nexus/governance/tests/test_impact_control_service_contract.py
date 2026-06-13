from __future__ import annotations

from dataclasses import replace

from nexus.governance.errors import ErrorCode
from nexus.governance.kernel import AggregateState, GovernanceKernel
from nexus.governance.no_go import NoGoBoundaryPolicy
from nexus.governance.schemas import ActorRef, CommandEnvelope
from nexus.governance.service_contract import GovernanceServiceContract
from nexus.governance.tests.test_source_authority import valid_manifest as valid_source_manifest

from ._evidence import write_evidence
from .fixtures.impact_control import (
    IMPACT_SOURCE_REFS,
    valid_create_review_task_command,
    valid_record_assessment_command,
    valid_record_outcome_command,
    valid_submit_request_command,
)


def test_submit_impact_request_command_payload_is_normalized() -> None:
    command = valid_submit_request_command()

    assert command.command_type == "SubmitImpactControlRequest"
    assert command.affects_state is True
    assert command.payload["source_refs"] == IMPACT_SOURCE_REFS
    assert command.payload["expected_kernel_version"] == command.expected_version
    assert command.payload["idempotency_key"] == command.idempotency_key


def test_impact_service_source_guard_runs_before_impact_validation() -> None:
    command = CommandEnvelope(
        command_type="SubmitImpactControlRequest",
        actor=ActorRef("agent:thunder", "implementation"),
        authority_refs=IMPACT_SOURCE_REFS,
        expected_version=True,
        idempotency_key="bad-impact-command",
        payload={},
        affects_state=True,
    )

    response = impact_service(source_wbs_version="V0.4").handle(command)

    assert response.accepted is False
    assert response.error_code == ErrorCode.STALE_SOURCE_AUTHORITY
    assert response.message == "WBS version mismatch"
    write_evidence("service/source-before-impact-control.json", response.to_evidence(), slice_id="l1gov-slice-007")


def test_impact_service_no_go_runs_before_kernel_append() -> None:
    kernel = kernel_ready_for_impact_request()

    response = impact_service(kernel=kernel).handle(
        valid_submit_request_command(),
        intent={"action": "impact_direct_419_controller_call"},
    )

    assert response.accepted is False
    assert response.error_code == ErrorCode.NO_GO_BOUNDARY
    assert len(kernel.records) == 0
    write_evidence("service/no-go-before-impact-kernel.json", response.to_evidence(), slice_id="l1gov-slice-007")


def test_submit_impact_request_appends_kernel_record() -> None:
    kernel = kernel_ready_for_impact_request()

    response = impact_service(kernel=kernel).handle(valid_submit_request_command())

    assert response.accepted is True
    assert response.record_ref == "krn-000001"
    assert kernel.state.state == "impact_request_recorded"
    assert len(kernel.records) == 1
    write_evidence("service/submit-impact-request-kernel-record.json", response.to_evidence(), slice_id="l1gov-slice-007")


def test_record_impact_assessment_appends_kernel_record() -> None:
    kernel = GovernanceKernel(
        state=AggregateState(
            aggregate_id="layer1-governance",
            state="impact_request_recorded",
            version=8,
            authority_refs=IMPACT_SOURCE_REFS,
        )
    )

    response = impact_service(kernel=kernel).handle(valid_record_assessment_command())

    assert response.accepted is True
    assert kernel.state.state == "impact_assessment_recorded"
    assert len(kernel.records) == 1
    write_evidence("service/record-impact-assessment-kernel-record.json", response.to_evidence(), slice_id="l1gov-slice-007")


def test_create_monitor_task_for_impact_appends_kernel_record() -> None:
    kernel = GovernanceKernel(
        state=AggregateState(
            aggregate_id="layer1-governance",
            state="impact_assessment_recorded",
            version=9,
            authority_refs=IMPACT_SOURCE_REFS,
        )
    )

    response = impact_service(kernel=kernel).handle(valid_create_review_task_command())

    assert response.accepted is True
    assert kernel.state.state == "impact_monitor_review_requested"
    assert len(kernel.records) == 1
    write_evidence("service/create-impact-review-task-kernel-record.json", response.to_evidence(), slice_id="l1gov-slice-007")


def test_record_lower_layer_outcome_returns_projection_without_kernel_append() -> None:
    kernel = kernel_ready_for_impact_request()

    response = impact_service(kernel=kernel).handle(valid_record_outcome_command())

    assert response.accepted is True
    assert response.projection_ref == "projection:impact-lower-layer-outcome"
    assert response.record_ref is None
    assert len(kernel.records) == 0
    write_evidence("service/lower-layer-outcome-projection.json", response.to_evidence(), slice_id="l1gov-slice-007")


def test_impact_service_response_envelope_covers_rejected_command() -> None:
    kernel = kernel_ready_for_impact_request()
    command = replace(valid_submit_request_command(), expected_version=True)
    command.payload["expected_kernel_version"] = True

    response = impact_service(kernel=kernel).handle(command)

    assert response.accepted is False
    assert response.error_code == ErrorCode.IMPACT_CONTROL_COMMAND_INVALID
    assert response.record_ref is None
    assert len(kernel.records) == 0


def impact_service(
    source_wbs_version: str = "V0.6",
    kernel: GovernanceKernel | None = None,
) -> GovernanceServiceContract:
    return GovernanceServiceContract(
        source_manifest=valid_source_manifest(wbs_version=source_wbs_version),
        no_go_policy=NoGoBoundaryPolicy.default(),
        kernel=kernel or GovernanceKernel(),
    )


def kernel_ready_for_impact_request() -> GovernanceKernel:
    return GovernanceKernel(
        state=AggregateState(
            aggregate_id="layer1-governance",
            state="initiation_ready",
            version=7,
            authority_refs=IMPACT_SOURCE_REFS,
        )
    )
