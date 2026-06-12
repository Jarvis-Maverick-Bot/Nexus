from __future__ import annotations

from nexus.governance.errors import ErrorCode
from nexus.governance.kernel import GovernanceKernel
from nexus.governance.no_go import NoGoBoundaryPolicy
from nexus.governance.schemas import ActorRef, CommandEnvelope
from nexus.governance.service_contract import GovernanceServiceContract
from nexus.governance.source_authority import SourceAuthorityManifest
from nexus.governance.tests.test_source_authority import valid_manifest

from ._evidence import write_evidence


def service(manifest: SourceAuthorityManifest | None = None) -> GovernanceServiceContract:
    return GovernanceServiceContract(
        source_manifest=manifest or valid_manifest(),
        no_go_policy=NoGoBoundaryPolicy.default(),
        kernel=GovernanceKernel(),
    )


def state_command() -> CommandEnvelope:
    return CommandEnvelope(
        command_type="InitializeAuthority",
        actor=ActorRef(actor_id="alex", role="decision_authority"),
        authority_refs=("WBS V0.6", "f9eaa5b"),
        expected_version=0,
        idempotency_key="cmd-001",
        payload={},
        affects_state=True,
    )


def test_service_rejects_command_when_source_authority_stale() -> None:
    response = service(valid_manifest(wbs_version="V0.4")).handle(state_command())

    assert response.accepted is False
    assert response.error_code == ErrorCode.STALE_SOURCE_AUTHORITY


def test_service_rejects_no_go_intent_before_kernel() -> None:
    response = service().handle(state_command(), intent={"action": "runtime_live_invocation"})

    assert response.accepted is False
    assert response.error_code == ErrorCode.NO_GO_BOUNDARY
    write_evidence("service/no-go-before-kernel.json", response.to_evidence())


def test_service_routes_legal_state_command_to_kernel_contract() -> None:
    response = service().handle(state_command())

    assert response.accepted is True
    assert response.record_ref is not None
    write_evidence("service/command-envelope.json", response.to_evidence())


def test_service_exposes_no_runtime_dispatch_surface() -> None:
    svc = service()

    assert not hasattr(svc, "dispatch")
    assert not hasattr(svc, "start_runtime")
    assert not hasattr(svc, "resident_controller")
