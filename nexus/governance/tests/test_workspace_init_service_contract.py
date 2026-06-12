from __future__ import annotations

from nexus.governance.errors import ErrorCode
from nexus.governance.kernel import AggregateState, GovernanceKernel
from nexus.governance.no_go import NoGoBoundaryPolicy
from nexus.governance.schemas import ActorRef
from nexus.governance.schemas import CommandEnvelope
from nexus.governance.service_contract import GovernanceServiceContract
from nexus.governance.tests.test_source_authority import valid_manifest as valid_source_manifest
from nexus.governance.workspace_init import (
    create_workspace_candidate_command,
    validate_workspace_init_command,
)

from ._evidence import write_evidence
from .fixtures.workspace_init import SOURCE_REFS, WORKSPACE_ROOT


def test_create_workspace_candidate_command_payload_is_normalized() -> None:
    command = create_workspace_candidate_command(
        actor=ActorRef("agent:thunder", "implementation"),
        authority_refs=SOURCE_REFS,
        workspace_id="ws-421",
        requested_project_ref="project-authority:421",
        requested_root_path=WORKSPACE_ROOT,
        template_profile_ref="workspace-template:standard-init:v1",
        expected_version=0,
        idempotency_key="slice002-create-ws-421",
    )

    result = validate_workspace_init_command(command)

    assert result.accepted is True
    assert command.command_type == "CreateWorkspaceCandidate"
    assert command.payload["workspace_id"] == "ws-421"
    assert command.payload["source_refs"] == SOURCE_REFS
    assert command.payload["expected_version"] == 0
    write_evidence(
        "workspace/create-command-envelope.json",
        {"command_type": command.command_type, "payload": command.payload, "validation": result.to_evidence()},
        slice_id="l1gov-slice-002",
    )


def test_malformed_workspace_init_command_is_rejected() -> None:
    command = create_workspace_candidate_command(
        actor=ActorRef("agent:thunder", "implementation"),
        authority_refs=SOURCE_REFS,
        workspace_id="",
        requested_project_ref="project-authority:421",
        requested_root_path=WORKSPACE_ROOT,
        template_profile_ref="workspace-template:standard-init:v1",
        expected_version=0,
        idempotency_key="slice002-create-ws-421",
    )

    result = validate_workspace_init_command(command)

    assert result.accepted is False
    assert result.message == "workspace_id is required"


def workspace_command(command_type: str, payload: dict[str, object]) -> CommandEnvelope:
    return CommandEnvelope(
        command_type=command_type,
        actor=ActorRef("agent:thunder", "implementation"),
        authority_refs=SOURCE_REFS,
        expected_version=0,
        idempotency_key=f"{command_type}-ws-421",
        payload=payload,
    )


def test_validate_workspace_manifest_payload_requires_source_refs_and_expected_version() -> None:
    command = workspace_command(
        "ValidateWorkspaceManifest",
        {
            "workspace_id": "ws-421",
            "manifest_id": "manifest-ws-421",
            "manifest_version": 1,
            "required_surfaces": ("evidence_path",),
            "source_refs": SOURCE_REFS,
            "expected_version": 1,
        },
    )

    result = validate_workspace_init_command(command)

    assert result.accepted is True
    write_evidence(
        "workspace/validate-command-envelope.json",
        {"command_type": command.command_type, "payload": command.payload, "validation": result.to_evidence()},
        slice_id="l1gov-slice-002",
    )


def test_validate_workspace_manifest_payload_rejects_missing_expected_version() -> None:
    command = workspace_command(
        "ValidateWorkspaceManifest",
        {
            "workspace_id": "ws-421",
            "manifest_id": "manifest-ws-421",
            "manifest_version": 1,
            "required_surfaces": ("evidence_path",),
            "source_refs": SOURCE_REFS,
        },
    )

    result = validate_workspace_init_command(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.WORKSPACE_COMMAND_INVALID
    assert result.message == "expected_version is required"


def test_validate_workspace_manifest_payload_rejects_missing_source_refs() -> None:
    command = workspace_command(
        "ValidateWorkspaceManifest",
        {
            "workspace_id": "ws-421",
            "manifest_id": "manifest-ws-421",
            "manifest_version": 1,
            "required_surfaces": ("evidence_path",),
            "expected_version": 1,
        },
    )

    result = validate_workspace_init_command(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.WORKSPACE_COMMAND_INVALID
    assert result.message == "source_refs is required"


def test_submit_workspace_init_record_payload_requires_source_refs_and_expected_kernel_version() -> None:
    command = workspace_command(
        "SubmitWorkspaceInitRecord",
        {
            "workspace_id": "ws-421",
            "manifest_ref": "manifest-ws-421",
            "validation_report_ref": "validation-ws-421",
            "source_refs": SOURCE_REFS,
            "expected_kernel_version": 3,
        },
    )

    result = validate_workspace_init_command(command)

    assert result.accepted is True
    write_evidence(
        "workspace/submit-command-envelope.json",
        {"command_type": command.command_type, "payload": command.payload, "validation": result.to_evidence()},
        slice_id="l1gov-slice-002",
    )


def test_submit_workspace_init_record_payload_rejects_missing_expected_kernel_version() -> None:
    command = workspace_command(
        "SubmitWorkspaceInitRecord",
        {
            "workspace_id": "ws-421",
            "manifest_ref": "manifest-ws-421",
            "validation_report_ref": "validation-ws-421",
            "source_refs": SOURCE_REFS,
        },
    )

    result = validate_workspace_init_command(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.WORKSPACE_COMMAND_INVALID
    assert result.message == "expected_kernel_version is required"


def test_submit_workspace_init_record_payload_rejects_missing_source_refs() -> None:
    command = workspace_command(
        "SubmitWorkspaceInitRecord",
        {
            "workspace_id": "ws-421",
            "manifest_ref": "manifest-ws-421",
            "validation_report_ref": "validation-ws-421",
            "expected_kernel_version": 3,
        },
    )

    result = validate_workspace_init_command(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.WORKSPACE_COMMAND_INVALID
    assert result.message == "source_refs is required"


def workspace_service(
    source_wbs_version: str = "V0.6",
    kernel: GovernanceKernel | None = None,
) -> GovernanceServiceContract:
    return GovernanceServiceContract(
        source_manifest=valid_source_manifest(wbs_version=source_wbs_version),
        no_go_policy=NoGoBoundaryPolicy.default(),
        kernel=kernel or GovernanceKernel(),
    )


def kernel_ready_for_workspace_init() -> GovernanceKernel:
    return GovernanceKernel(
        state=AggregateState(
            aggregate_id="layer1-governance",
            state="projection_contract_ready",
            version=3,
            authority_refs=SOURCE_REFS,
        )
    )


def test_service_source_guard_runs_before_workspace_validation() -> None:
    command = workspace_command("CreateWorkspaceCandidate", {})

    response = workspace_service(source_wbs_version="V0.4").handle(command)

    assert response.accepted is False
    assert response.error_code == ErrorCode.STALE_SOURCE_AUTHORITY
    assert response.message == "WBS version mismatch"
    write_evidence("service/source-before-workspace.json", response.to_evidence(), slice_id="l1gov-slice-002")


def test_service_no_go_runs_before_kernel_for_workspace_command() -> None:
    kernel = kernel_ready_for_workspace_init()
    command = workspace_command(
        "SubmitWorkspaceInitRecord",
        {
            "workspace_id": "ws-421",
            "manifest_ref": "manifest-ws-421",
            "validation_report_ref": "validation-ws-421",
            "source_refs": SOURCE_REFS,
            "expected_kernel_version": 3,
        },
    )

    response = workspace_service(kernel=kernel).handle(command, intent={"action": "workspace_init_runtime_dispatch"})

    assert response.accepted is False
    assert response.error_code == ErrorCode.NO_GO_BOUNDARY
    assert len(kernel.records) == 0
    write_evidence("service/no-go-before-kernel.json", response.to_evidence(), slice_id="l1gov-slice-002")


def test_service_returns_normalized_response_for_workspace_submit() -> None:
    command = workspace_command(
        "SubmitWorkspaceInitRecord",
        {
            "workspace_id": "ws-421",
            "manifest_ref": "manifest-ws-421",
            "validation_report_ref": "validation-ws-421",
            "source_refs": SOURCE_REFS,
            "expected_kernel_version": 3,
        },
    )

    response = workspace_service(kernel=kernel_ready_for_workspace_init()).handle(command)

    assert response.accepted is True
    assert response.aggregate_ref == "layer1-governance"
    assert response.record_ref == "krn-000001"
    assert response.error_code is None
    assert response.to_evidence() == {
        "accepted": True,
        "aggregate_ref": "layer1-governance",
        "error_code": None,
        "evidence_refs": [],
        "message": "",
        "projection_ref": None,
        "record_ref": "krn-000001",
        "retryable": False,
    }
    write_evidence("service/workspace-submit-response.json", response.to_evidence(), slice_id="l1gov-slice-002")
