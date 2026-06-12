from __future__ import annotations

from nexus.governance.errors import ErrorCode
from nexus.governance.kernel import AggregateState, GovernanceKernel
from nexus.governance.schemas import ActorRef
from nexus.governance.workspace_init import (
    submit_workspace_init_record,
    validate_workspace_manifest,
)

from ._evidence import write_evidence
from .fixtures.workspace_init import SOURCE_REFS, valid_manifest


def kernel_ready_for_workspace_init() -> GovernanceKernel:
    return GovernanceKernel(
        state=AggregateState(
            aggregate_id="layer1-governance",
            state="projection_contract_ready",
            version=3,
            authority_refs=SOURCE_REFS,
        )
    )


def test_submit_workspace_init_record_is_kernel_mediated() -> None:
    kernel = kernel_ready_for_workspace_init()
    manifest = valid_manifest()
    validation = validate_workspace_manifest(manifest)

    result = submit_workspace_init_record(
        kernel=kernel,
        manifest=manifest,
        validation=validation,
        actor=ActorRef("agent:thunder", "implementation"),
        expected_version=3,
        authority_refs=SOURCE_REFS,
        idempotency_key="submit-workspace-init-ws-421",
    )

    assert result.accepted is True
    assert result.record is not None
    assert result.record.command_type == "SubmitWorkspaceInitRecord"
    assert result.new_state.state == "initiation_ready"
    write_evidence("workspace/kernel-submit-init-record.json", result.to_evidence(), slice_id="l1gov-slice-002")


def test_stale_expected_version_blocks_workspace_init_without_append() -> None:
    kernel = kernel_ready_for_workspace_init()
    manifest = valid_manifest()
    validation = validate_workspace_manifest(manifest)

    result = submit_workspace_init_record(
        kernel=kernel,
        manifest=manifest,
        validation=validation,
        actor=ActorRef("agent:thunder", "implementation"),
        expected_version=2,
        authority_refs=SOURCE_REFS,
        idempotency_key="submit-workspace-init-ws-421",
    )

    assert result.accepted is False
    assert result.error_code == ErrorCode.STALE_EXPECTED_VERSION
    assert len(kernel.records) == 0
    write_evidence("workspace/stale-version-block.json", result.to_evidence(), slice_id="l1gov-slice-002")


def test_idempotent_workspace_init_submit_returns_prior_record() -> None:
    kernel = kernel_ready_for_workspace_init()
    manifest = valid_manifest()
    validation = validate_workspace_manifest(manifest)
    actor = ActorRef("agent:thunder", "implementation")

    first = submit_workspace_init_record(kernel, manifest, validation, actor, 3, SOURCE_REFS, "submit-ws-421")
    second = submit_workspace_init_record(kernel, manifest, validation, actor, 3, SOURCE_REFS, "submit-ws-421")

    assert first.accepted is True
    assert second.accepted is True
    assert second.record == first.record
    assert len(kernel.records) == 1
