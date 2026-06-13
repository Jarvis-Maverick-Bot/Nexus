from __future__ import annotations

from nexus.governance.app_contract import (
    CommandAffordance,
    MenuCommandMap,
    build_command_draft_route,
    validate_menu_command_map,
)
from nexus.governance.errors import ErrorCode
from nexus.governance.service_facade import validate_service_command_envelope

from ._evidence import write_evidence


SOURCE_REFS = ("WBS V0.6", "L1GOV-SLICE-010", "eef9c05")


def command_affordance(**overrides: object) -> CommandAffordance:
    values = {
        "command_id": "cmd-request-hitl-review",
        "label": "Request HITL review",
        "module_id": "monitor_hitl",
        "surface": "menu",
        "creates_command_draft": True,
        "service_command_type": "SubmitCommandDraft",
        "requires_human_decision": True,
        "disabled": False,
        "disabled_reason": "",
        "source_refs": SOURCE_REFS,
        "payload": {
            "requested_action": "create_human_review_task",
            "target_ref": "deliverable:001",
        },
    }
    values.update(overrides)
    return CommandAffordance(**values)


def valid_menu(**overrides: object) -> MenuCommandMap:
    values = {
        "groups": {
            "File": (command_affordance(command_id="cmd-refresh", label="Refresh projection", creates_command_draft=False, service_command_type="RefreshProjection"),),
            "Monitor/HITL": (command_affordance(),),
            "View": (command_affordance(command_id="cmd-show-notes", label="Show evidence notes", creates_command_draft=False, service_command_type=""),),
        },
        "read_only_preview": False,
    }
    values.update(overrides)
    return MenuCommandMap(**values)


def test_menu_command_map_accepts_approved_groups_and_command_routing() -> None:
    result = validate_menu_command_map(valid_menu())

    assert result.accepted is True
    write_evidence("command-map/menu-map-valid.json", result.to_evidence(), slice_id="l1gov-slice-010")


def test_menu_command_map_rejects_unknown_group() -> None:
    result = validate_menu_command_map(MenuCommandMap(groups={"Project Execution": (command_affordance(),)}, read_only_preview=False))

    assert result.accepted is False
    assert result.error_code == ErrorCode.INVALID_TRANSITION


def test_read_only_menu_rejects_enabled_mutation() -> None:
    result = validate_menu_command_map(valid_menu(read_only_preview=True))

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY


def test_command_affordance_builds_submit_command_draft_route() -> None:
    result, command = build_command_draft_route(
        command_affordance(),
        actor_id="agent:thunder",
        expected_version=0,
        expected_state="local_app_preview",
        idempotency_key="ui-draft-001",
    )

    assert result.accepted is True
    assert command is not None
    assert command.command_type == "SubmitCommandDraft"
    assert command.payload["command_draft"]["source_refs"] == SOURCE_REFS
    assert command.payload["source_refs"] == SOURCE_REFS
    assert command.payload["expected_version"] == 0
    assert command.payload["idempotency_key"] == "ui-draft-001"
    assert validate_service_command_envelope(command).accepted is True
    write_evidence("command-drafts/routes-to-submit-command-draft.json", command.payload, slice_id="l1gov-slice-010")
