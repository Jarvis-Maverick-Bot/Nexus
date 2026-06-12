from __future__ import annotations

from nexus.governance.app_contract import build_read_only_view_model

from ._evidence import write_evidence


def test_read_only_view_model_disables_mutation_affordances() -> None:
    view_model = build_read_only_view_model(workspace_id="workspace-001")

    assert view_model.read_only is True
    assert "approve" in view_model.disabled_commands
    assert "complete" in view_model.disabled_commands
    assert "baseline" in view_model.disabled_commands
    write_evidence("app/read-only-view-model.json", view_model.to_evidence())


def test_workspace_picker_opens_projection_only() -> None:
    view_model = build_read_only_view_model(workspace_id="workspace-001")

    assert view_model.workspace_picker_mode == "projection_overlay"
    assert view_model.workspace_picker_creates_authority is False


def test_app_contract_does_not_include_runtime_framework_choice() -> None:
    view_model = build_read_only_view_model(workspace_id="workspace-001")

    assert view_model.framework is None
