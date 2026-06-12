from __future__ import annotations

from nexus.governance.schemas import ActorRef
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
