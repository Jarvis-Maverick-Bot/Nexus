from __future__ import annotations

from nexus.governance.errors import ErrorCode
from nexus.governance.kernel import AggregateState, GovernanceKernel
from nexus.governance.no_go import NoGoBoundaryPolicy
from nexus.governance.schemas import ActorRef, CommandEnvelope
from nexus.governance.service_contract import GovernanceServiceContract
from nexus.governance.tests.test_source_authority import valid_manifest as valid_source_manifest

from ._evidence import write_evidence
from .fixtures.monitor_hitl import (
    MONITOR_SOURCE_REFS,
    valid_create_review_task_command,
    valid_evaluate_deliverable_command,
    valid_submit_decision_command,
)


def test_create_human_review_task_command_payload_is_normalized() -> None:
    command = valid_create_review_task_command()

    assert command.command_type == "CreateHumanReviewTask"
    assert command.affects_state is True
    assert command.payload["source_refs"] == MONITOR_SOURCE_REFS
    assert command.payload["expected_kernel_version"] == command.expected_version
    assert command.payload["idempotency_key"] == command.idempotency_key


def test_monitor_service_source_guard_runs_before_monitor_validation() -> None:
    command = CommandEnvelope(
        command_type="CreateHumanReviewTask",
        actor=ActorRef("agent:thunder", "implementation"),
        authority_refs=MONITOR_SOURCE_REFS,
        expected_version=True,
        idempotency_key="bad-monitor-command",
        payload={},
        affects_state=True,
    )

    response = monitor_service(source_wbs_version="V0.4").handle(command)

    assert response.accepted is False
    assert response.error_code == ErrorCode.STALE_SOURCE_AUTHORITY
    assert response.message == "WBS version mismatch"
    write_evidence("service/source-before-monitor-hitl.json", response.to_evidence(), slice_id="l1gov-slice-006")


def test_monitor_service_no_go_runs_before_kernel_append() -> None:
    kernel = kernel_ready_for_monitor()

    response = monitor_service(kernel=kernel).handle(
        valid_create_review_task_command(),
        intent={"action": "monitor_direct_ui_approval"},
    )

    assert response.accepted is False
    assert response.error_code == ErrorCode.NO_GO_BOUNDARY
    assert len(kernel.records) == 0
    write_evidence("service/no-go-before-monitor-kernel.json", response.to_evidence(), slice_id="l1gov-slice-006")


def test_monitor_service_appends_review_task_through_kernel() -> None:
    kernel = kernel_ready_for_monitor()

    response = monitor_service(kernel=kernel).handle(valid_create_review_task_command())

    assert response.accepted is True
    assert response.aggregate_ref == "layer1-governance"
    assert response.record_ref == "krn-000001"
    assert kernel.state.state == "monitor_review_open"
    assert len(kernel.records) == 1
    write_evidence("service/create-review-task-kernel-record.json", response.to_evidence(), slice_id="l1gov-slice-006")


def test_monitor_service_appends_human_decision_through_kernel() -> None:
    kernel = GovernanceKernel(
        state=AggregateState(
            aggregate_id="layer1-governance",
            state="monitor_review_open",
            version=8,
            authority_refs=MONITOR_SOURCE_REFS,
        )
    )

    response = monitor_service(kernel=kernel).handle(valid_submit_decision_command())

    assert response.accepted is True
    assert response.record_ref == "krn-000001"
    assert kernel.state.state == "monitor_decision_recorded"
    assert len(kernel.records) == 1
    write_evidence("service/submit-human-decision-kernel-record.json", response.to_evidence(), slice_id="l1gov-slice-006")


def test_evaluate_deliverable_returns_projection_without_kernel_append() -> None:
    kernel = kernel_ready_for_monitor()

    response = monitor_service(kernel=kernel).handle(valid_evaluate_deliverable_command())

    assert response.accepted is True
    assert response.projection_ref == "projection:monitor-deliverable-evaluation"
    assert response.aggregate_ref is None
    assert response.record_ref is None
    assert len(kernel.records) == 0
    write_evidence("service/evaluate-deliverable-projection.json", response.to_evidence(), slice_id="l1gov-slice-006")


def monitor_service(
    source_wbs_version: str = "V0.6",
    kernel: GovernanceKernel | None = None,
) -> GovernanceServiceContract:
    return GovernanceServiceContract(
        source_manifest=valid_source_manifest(wbs_version=source_wbs_version),
        no_go_policy=NoGoBoundaryPolicy.default(),
        kernel=kernel or GovernanceKernel(),
    )


def kernel_ready_for_monitor() -> GovernanceKernel:
    return GovernanceKernel(
        state=AggregateState(
            aggregate_id="layer1-governance",
            state="initiation_ready",
            version=7,
            authority_refs=MONITOR_SOURCE_REFS,
        )
    )
