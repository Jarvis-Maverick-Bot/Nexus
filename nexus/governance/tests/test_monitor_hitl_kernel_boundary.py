from __future__ import annotations

from nexus.governance.errors import ErrorCode
from nexus.governance.kernel import AggregateState, GovernanceKernel
from nexus.governance.no_go import NoGoBoundaryPolicy
from nexus.governance.service_contract import GovernanceServiceContract
from nexus.governance.tests.test_source_authority import valid_manifest as valid_source_manifest

from .fixtures.monitor_hitl import MONITOR_SOURCE_REFS, valid_create_review_task_command, valid_submit_decision_command


def test_create_review_task_rejects_boolean_expected_version_before_kernel_append() -> None:
    kernel = GovernanceKernel(
        state=AggregateState(
            aggregate_id="layer1-governance",
            state="initiation_ready",
            version=1,
            authority_refs=MONITOR_SOURCE_REFS,
        )
    )

    response = service(kernel).handle(valid_create_review_task_command(expected_version=True))

    assert response.accepted is False
    assert response.error_code == ErrorCode.MONITOR_HITL_COMMAND_INVALID
    assert len(kernel.records) == 0


def test_submit_human_decision_rejects_payload_envelope_version_mismatch() -> None:
    kernel = GovernanceKernel(
        state=AggregateState(
            aggregate_id="layer1-governance",
            state="monitor_review_open",
            version=8,
            authority_refs=MONITOR_SOURCE_REFS,
        )
    )
    command = valid_submit_decision_command()
    command.payload["expected_kernel_version"] = 7

    response = service(kernel).handle(command)

    assert response.accepted is False
    assert response.error_code == ErrorCode.MONITOR_HITL_COMMAND_INVALID
    assert len(kernel.records) == 0


def test_monitor_kernel_idempotent_replay_returns_prior_record() -> None:
    kernel = GovernanceKernel(
        state=AggregateState(
            aggregate_id="layer1-governance",
            state="initiation_ready",
            version=7,
            authority_refs=MONITOR_SOURCE_REFS,
        )
    )
    command = valid_create_review_task_command()

    first = service(kernel).handle(command)
    second = service(kernel).handle(command)

    assert first.accepted is True
    assert second.accepted is True
    assert second.record_ref == first.record_ref
    assert len(kernel.records) == 1


def service(kernel: GovernanceKernel) -> GovernanceServiceContract:
    return GovernanceServiceContract(
        source_manifest=valid_source_manifest(),
        no_go_policy=NoGoBoundaryPolicy.default(),
        kernel=kernel,
    )
