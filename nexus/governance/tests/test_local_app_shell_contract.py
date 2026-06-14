from __future__ import annotations

from nexus.governance.app_contract import (
    CommandAffordance,
    LocalDesktopShellViewModel,
    build_read_only_desktop_shell,
    validate_local_desktop_shell,
)
from nexus.governance.errors import ErrorCode

from ._evidence import write_evidence


def valid_affordance(**overrides: object) -> CommandAffordance:
    values = {
        "command_id": "cmd-refresh-projection",
        "label": "Refresh projection",
        "module_id": "mission_control",
        "surface": "header",
        "creates_command_draft": False,
        "service_command_type": "RefreshProjection",
        "requires_human_decision": False,
        "disabled": False,
        "disabled_reason": "",
        "source_refs": ("WBS V0.6", "L1GOV-SLICE-010", "eef9c05"),
        "payload": {"projection_type": "mission_control"},
    }
    values.update(overrides)
    return CommandAffordance(**values)


def valid_shell(**overrides: object) -> LocalDesktopShellViewModel:
    affordance = valid_affordance()
    values = {
        "workspace_id": "workspace-001",
        "workspace_display_name": "Layer 1 Governance",
        "read_only_preview": False,
        "show_archived_parked": False,
        "service_state": "connected",
        "projection_freshness": "current",
        "sync_state": "ok",
        "kernel_source_ref": "kernel:9a3144b",
        "active_module": "mission_control",
        "module_navigation": ("mission_control", "monitor_hitl", "delivery_feedback"),
        "header_actions": (affordance,),
        "disabled_commands": (),
        "toolbar": (affordance,),
        "inspector": {"selected_ref": "projection:mission_control"},
        "status_bar": {
            "service_state": "connected",
            "projection_freshness": "current",
            "sync_state": "ok",
            "kernel_source_ref": "kernel:9a3144b",
        },
        "framework": None,
        "persistent_workspace_explorer": False,
        "canonical_authority": False,
    }
    values.update(overrides)
    return LocalDesktopShellViewModel(**values)


def test_valid_local_desktop_shell_accepts_projection_backed_state() -> None:
    result = validate_local_desktop_shell(valid_shell())

    assert result.accepted is True
    write_evidence("app-shell/view-model-valid.json", result.to_evidence(), slice_id="l1gov-slice-010")


def test_shell_rejects_final_framework_selection() -> None:
    result = validate_local_desktop_shell(valid_shell(framework="electron"))

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    write_evidence("app-shell/no-framework-selection.json", result.to_evidence(), slice_id="l1gov-slice-010")


def test_shell_rejects_persistent_workspace_explorer() -> None:
    result = validate_local_desktop_shell(valid_shell(persistent_workspace_explorer=True))

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY


def test_shell_rejects_runtime_server_database_or_api_fields() -> None:
    for inspector in (
        {"server_url": "http://localhost:8080"},
        {"database": "local.sqlite"},
        {"api_schema": "selected"},
        {"runtime_transport": "ipc channel"},
    ):
        result = validate_local_desktop_shell(valid_shell(inspector=inspector))

        assert result.accepted is False
        assert result.error_code == ErrorCode.NO_GO_BOUNDARY


def test_shell_rejects_unknown_module() -> None:
    result = validate_local_desktop_shell(valid_shell(active_module="project_execution"))

    assert result.accepted is False
    assert result.error_code == ErrorCode.INVALID_TRANSITION


def test_read_only_desktop_shell_carries_status_without_authority() -> None:
    shell = build_read_only_desktop_shell(
        workspace_id="workspace-001",
        workspace_display_name="Layer 1 Governance",
        kernel_source_ref="kernel:9a3144b",
    )

    assert shell.read_only_preview is True
    assert shell.canonical_authority is False
    assert shell.status_bar["kernel_source_ref"] == "kernel:9a3144b"
    assert validate_local_desktop_shell(shell).accepted is True
