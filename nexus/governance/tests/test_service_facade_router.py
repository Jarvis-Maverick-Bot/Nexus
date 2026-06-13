from __future__ import annotations

from dataclasses import replace

from nexus.governance.errors import ErrorCode
from nexus.governance.kernel import GovernanceKernel
from nexus.governance.no_go import NoGoBoundaryPolicy
from nexus.governance.service_facade import CommandDraft, GovernanceServiceFacade, ServiceOutcomeStatus
from nexus.governance.tests.test_source_authority import valid_manifest

from ._evidence import write_evidence
from .fixtures.service_facade import SERVICE_SOURCE_REFS, service_command


def service(source_wbs_version: str = "V0.6", kernel: GovernanceKernel | None = None) -> GovernanceServiceFacade:
    return GovernanceServiceFacade(
        source_manifest=valid_manifest(wbs_version=source_wbs_version),
        no_go_policy=NoGoBoundaryPolicy.default(),
        kernel=kernel or GovernanceKernel(),
    )


def test_service_facade_source_guard_runs_before_router_validation() -> None:
    response = service(source_wbs_version="V0.4").handle(service_command(expected_version=True, payload={}))

    assert response.status == ServiceOutcomeStatus.REJECTED
    assert response.error_code == ErrorCode.STALE_SOURCE_AUTHORITY
    write_evidence("service-facade/source-guard-before-router.json", response.to_evidence(), slice_id="l1gov-slice-009")


def test_service_facade_no_go_runs_before_kernel_append() -> None:
    kernel = GovernanceKernel()

    response = service(kernel=kernel).handle(
        service_command(),
        intent={"action": "service_projection_as_authority"},
    )

    assert response.status == ServiceOutcomeStatus.BLOCKED
    assert response.error_code == ErrorCode.NO_GO_BOUNDARY
    assert len(kernel.records) == 0
    write_evidence("service-facade/no-go-before-kernel.json", response.to_evidence(), slice_id="l1gov-slice-009")


def test_unknown_service_command_type_rejects_without_kernel_append() -> None:
    kernel = GovernanceKernel()
    command = replace(service_command("InventLocalAuthority"), command_type="InventLocalAuthority")

    response = service(kernel=kernel).handle(command)

    assert response.status == ServiceOutcomeStatus.REJECTED
    assert response.error_code == ErrorCode.INVALID_TRANSITION
    assert len(kernel.records) == 0
    write_evidence("service-facade/unknown-command-type-reject.json", response.to_evidence(), slice_id="l1gov-slice-009")


def test_submit_command_draft_route_blocks_read_only_draft_without_kernel_append() -> None:
    kernel = GovernanceKernel()
    draft = CommandDraft(
        draft_id="draft-readonly-001",
        command_type="SubmitCommandDraft",
        target_ref="layer1-governance",
        payload={"requested_action": "prepare_command_draft"},
        read_only_blocked=True,
        source_refs=SERVICE_SOURCE_REFS,
        draft_status="draft",
        created_by="agent:thunder",
    )
    command = service_command(payload={"command_draft": draft.__dict__})

    response = service(kernel=kernel).handle(command)

    assert response.status == ServiceOutcomeStatus.BLOCKED
    assert response.error_code == ErrorCode.NO_GO_BOUNDARY
    assert len(kernel.records) == 0
    write_evidence("service-facade/submit-read-only-draft-route-block.json", response.to_evidence(), slice_id="l1gov-slice-009")


def test_read_projection_refresh_returns_projection_outcome_without_kernel_append() -> None:
    kernel = GovernanceKernel()
    command = service_command(
        "RefreshProjection",
        expected_version=None,
        idempotency_key=None,
        affects_state=False,
        payload={"projection_type": "mission_control", "source_checkpoint": "kernel:0"},
    )

    response = service(kernel=kernel).handle(command)

    assert response.status == ServiceOutcomeStatus.ACCEPTED
    assert response.projection_ref == "projection:mission_control:kernel:0"
    assert len(kernel.records) == 0


def test_service_facade_exposes_no_runtime_dispatch_surface() -> None:
    svc = service()

    assert not hasattr(svc, "dispatch")
    assert not hasattr(svc, "start_runtime")
    assert not hasattr(svc, "resident_controller")
    assert not hasattr(svc, "activate_route")
