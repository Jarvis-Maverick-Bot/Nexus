from __future__ import annotations

from nexus.governance.app_contract import WorkspacePickerOverlayViewModel, validate_workspace_picker_overlay
from nexus.governance.errors import ErrorCode

from ._evidence import write_evidence


def valid_overlay(**overrides: object) -> WorkspacePickerOverlayViewModel:
    values = {
        "overlay_id": "workspace-picker-001",
        "trigger": "header_workspace_dropdown",
        "mode": "temporary_overlay",
        "open_mode": "normal",
        "show_archived_parked": False,
        "current_workspace_ref": "workspace-001",
        "recent_workspace_refs": ("workspace-001", "workspace-002"),
        "active_workspace_refs": ("workspace-001",),
        "archived_or_parked_workspace_refs": (),
        "freshness_by_workspace": {"workspace-001": "current"},
        "actions": ("open", "open_read_only", "create_workspace_candidate", "cancel"),
        "creates_authority": False,
        "persistent_left_rail": False,
    }
    values.update(overrides)
    return WorkspacePickerOverlayViewModel(**values)


def test_workspace_picker_header_overlay_is_projection_only() -> None:
    result = validate_workspace_picker_overlay(valid_overlay())

    assert result.accepted is True
    write_evidence("workspace-picker/overlay-not-authority.json", result.to_evidence(), slice_id="l1gov-slice-010")


def test_workspace_picker_rejects_persistent_left_rail() -> None:
    result = validate_workspace_picker_overlay(valid_overlay(persistent_left_rail=True))

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    write_evidence("workspace-picker/no-persistent-left-rail.json", result.to_evidence(), slice_id="l1gov-slice-010")


def test_workspace_picker_blocks_archived_refs_when_toggle_off() -> None:
    result = validate_workspace_picker_overlay(
        valid_overlay(archived_or_parked_workspace_refs=("workspace-archived",), show_archived_parked=False)
    )

    assert result.accepted is False
    assert result.error_code == ErrorCode.INVALID_TRANSITION


def test_workspace_picker_rejects_authority_creation() -> None:
    result = validate_workspace_picker_overlay(valid_overlay(creates_authority=True))

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY


def test_workspace_picker_rejects_non_temporary_mode() -> None:
    result = validate_workspace_picker_overlay(valid_overlay(mode="persistent_sidebar"))

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
