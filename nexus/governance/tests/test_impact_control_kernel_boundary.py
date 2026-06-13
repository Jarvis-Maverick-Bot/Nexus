from __future__ import annotations

from dataclasses import replace

from nexus.governance.errors import ErrorCode
from nexus.governance.kernel import AggregateState, GovernanceKernel
from nexus.governance.no_go import NoGoBoundaryPolicy
from nexus.governance.service_contract import GovernanceServiceContract
from nexus.governance.tests.test_source_authority import valid_manifest as valid_source_manifest

from .fixtures.impact_control import IMPACT_SOURCE_REFS, valid_impact_request, valid_submit_request_command


def test_submit_impact_request_rejects_boolean_expected_version_before_kernel_append() -> None:
    kernel = GovernanceKernel(
        state=AggregateState(
            aggregate_id="layer1-governance",
            state="initiation_ready",
            version=1,
            authority_refs=IMPACT_SOURCE_REFS,
        )
    )
    command = replace(valid_submit_request_command(expected_version=True), expected_version=True)
    command.payload["expected_kernel_version"] = True

    response = service(kernel).handle(command)

    assert response.accepted is False
    assert response.error_code == ErrorCode.IMPACT_CONTROL_COMMAND_INVALID
    assert len(kernel.records) == 0


def test_submit_impact_request_rejects_payload_envelope_version_mismatch() -> None:
    kernel = GovernanceKernel(
        state=AggregateState(
            aggregate_id="layer1-governance",
            state="initiation_ready",
            version=7,
            authority_refs=IMPACT_SOURCE_REFS,
        )
    )
    command = valid_submit_request_command()
    command.payload["expected_kernel_version"] = 6

    response = service(kernel).handle(command)

    assert response.accepted is False
    assert response.error_code == ErrorCode.IMPACT_CONTROL_COMMAND_INVALID
    assert len(kernel.records) == 0


def test_submit_impact_request_rejects_stale_expected_version_without_append() -> None:
    kernel = GovernanceKernel(
        state=AggregateState(
            aggregate_id="layer1-governance",
            state="initiation_ready",
            version=9,
            authority_refs=IMPACT_SOURCE_REFS,
        )
    )

    response = service(kernel).handle(valid_submit_request_command())

    assert response.accepted is False
    assert response.error_code == ErrorCode.STALE_EXPECTED_VERSION
    assert len(kernel.records) == 0


def test_impact_kernel_idempotent_replay_returns_prior_record() -> None:
    kernel = GovernanceKernel(
        state=AggregateState(
            aggregate_id="layer1-governance",
            state="initiation_ready",
            version=7,
            authority_refs=IMPACT_SOURCE_REFS,
        )
    )
    command = valid_submit_request_command()

    first = service(kernel).handle(command)
    second = service(kernel).handle(command)

    assert first.accepted is True
    assert second.accepted is True
    assert second.record_ref == first.record_ref
    assert len(kernel.records) == 1


def test_impact_kernel_idempotency_reuse_with_different_payload_rejects() -> None:
    kernel = GovernanceKernel(
        state=AggregateState(
            aggregate_id="layer1-governance",
            state="initiation_ready",
            version=7,
            authority_refs=IMPACT_SOURCE_REFS,
        )
    )
    first_command = valid_submit_request_command()
    second_command = valid_submit_request_command(
        impact_request=valid_impact_request(request_id="impact-request-421-002")
    )

    first = service(kernel).handle(first_command)
    second = service(kernel).handle(second_command)

    assert first.accepted is True
    assert second.accepted is False
    assert second.error_code == ErrorCode.IDEMPOTENCY_KEY_REUSE
    assert len(kernel.records) == 1


def service(kernel: GovernanceKernel) -> GovernanceServiceContract:
    return GovernanceServiceContract(
        source_manifest=valid_source_manifest(),
        no_go_policy=NoGoBoundaryPolicy.default(),
        kernel=kernel,
    )
