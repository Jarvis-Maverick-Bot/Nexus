from __future__ import annotations

import pytest

from nexus.governance.app_contract import (
    CommandAffordance,
    build_command_draft_route,
    build_read_only_desktop_shell,
    disabled_mutation_command_ids,
    validate_command_affordance,
)
from nexus.governance.errors import ErrorCode

from ._evidence import write_evidence


def affordance(**overrides: object) -> CommandAffordance:
    values = {
        "command_id": "cmd-open-review",
        "label": "Open review",
        "module_id": "monitor_hitl",
        "surface": "toolbar",
        "creates_command_draft": False,
        "service_command_type": "",
        "requires_human_decision": False,
        "disabled": False,
        "disabled_reason": "",
        "source_refs": ("WBS V0.6", "L1GOV-SLICE-010", "eef9c05"),
        "payload": {},
    }
    values.update(overrides)
    return CommandAffordance(**values)


def test_read_only_shell_disables_mutation_affordances() -> None:
    shell = build_read_only_desktop_shell(
        workspace_id="workspace-001",
        workspace_display_name="Layer 1 Governance",
        kernel_source_ref="kernel:9a3144b",
    )

    expected = disabled_mutation_command_ids()
    assert set(expected).issubset(set(shell.disabled_commands))
    write_evidence(
        "read-only/disabled-mutation-affordances.json",
        {"disabled_commands": list(shell.disabled_commands)},
        slice_id="l1gov-slice-010",
    )


@pytest.mark.parametrize(
    "label",
    (
        "approve now",
        "complete project",
        "archive workspace",
        "mark baseline",
        "mark production ready",
        "activate continuity",
        "claim final PASS",
    ),
)
def test_enabled_sentence_shaped_mutation_affordances_reject(label: str) -> None:
    result = validate_command_affordance(
        affordance(
            command_id="cmd-forbidden",
            label=label,
            creates_command_draft=True,
            service_command_type="SubmitCommandDraft",
            payload={"requested_action": label},
        )
    )

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY


def test_disabled_mutation_affordance_does_not_create_command_draft() -> None:
    disabled = affordance(
        command_id="cmd-complete-project",
        label="Complete project",
        disabled=True,
        disabled_reason="read-only preview",
        creates_command_draft=False,
        service_command_type="",
    )

    result, command = build_command_draft_route(
        disabled,
        actor_id="agent:thunder",
        expected_version=0,
        expected_state="local_app_preview",
        idempotency_key="ui-disabled-001",
    )

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    assert command is None
