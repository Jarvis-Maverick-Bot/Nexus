from __future__ import annotations

import json
from pathlib import Path

import pytest

from nexus.governance.real_uat import (
    cleanup_real_test_project,
    create_real_test_project,
    load_real_test_project_state,
    save_real_test_project_init,
)


INIT_VALUES = {
    "project_charter": "TestProject charter for real UAT.",
    "stakeholder_authority": "Alex owns UAT decisions for this local test.",
    "scope": "Exercise the 4.21 desktop client path.",
    "requirements": "Create project, record init draft, and display projection.",
    "risks": "No live execution is allowed.",
    "dependencies": "Governance Service and Kernel local test contracts.",
    "backlog_wbs": "UAT-001 create TestProject; UAT-002 draft init.",
    "execution_plan": "Run local verification, capture screenshots, then clean up.",
}


def test_create_real_testproject_records_kernel_and_projection(tmp_path: Path) -> None:
    result = create_real_test_project(root=tmp_path, project_name="TestProject")

    assert result.project_name == "TestProject"
    assert result.service_outcome.status == "accepted"
    assert result.kernel_state.state == "initiation_ready"
    assert result.kernel_state.version == 4
    assert result.canonical_records_path.exists()
    assert result.projection_path.exists()
    assert result.desktop_state_path.exists()

    canonical = json.loads(result.canonical_records_path.read_text(encoding="utf-8"))
    assert canonical["project_name"] == "TestProject"
    assert canonical["kernel_state"]["state"] == "initiation_ready"
    assert canonical["kernel_state"]["version"] == 4
    assert [record["command_type"] for record in canonical["records"]] == [
        "InitializeAuthority",
        "MarkKernelReady",
        "RefreshProjectionCheckpoint",
        "SubmitWorkspaceInitRecord",
    ]
    assert canonical["records"][-1]["payload"]["workspace_id"] == result.workspace_id

    projection = json.loads(result.projection_path.read_text(encoding="utf-8"))
    assert projection["projection_type"] == "mission-control"
    assert projection["source_checkpoint"] == canonical["records"][-1]["record_id"]
    assert projection["payload"]["project_name"] == "TestProject"
    assert projection["payload"]["kernel_record_count"] == 4
    assert projection["payload"]["workspace_root"] == str(result.workspace_root)

    desktop_state = load_real_test_project_state(result.desktop_state_path)
    assert desktop_state["source_mode"] == "real_test_project"
    assert desktop_state["fixture_only"] is False
    assert desktop_state["display_state"]["workspace_name"] == "TestProject"
    assert desktop_state["display_state"]["init_status"] == "draft_required"
    assert desktop_state["display_state"]["service_state"] == "real local test"
    assert desktop_state["display_state"]["sync_state"] == "projection current"
    assert desktop_state["display_state"]["project_summary"]["canonical_records"] == 4
    init_requirements = desktop_state["display_state"]["init_requirements"]
    assert [item["field"] for item in init_requirements] == [
        "Project charter",
        "Stakeholder authority",
        "Scope",
        "Requirements",
        "Risks",
        "Dependencies",
        "Backlog/WBS",
        "Execution plan",
    ]
    assert all(item["status"] == "needs_input" for item in init_requirements)
    assert all(str(result.workspace_root) in item["path"] for item in init_requirements)


def test_save_real_testproject_init_writes_workspace_files_without_kernel_mutation(tmp_path: Path) -> None:
    result = create_real_test_project(root=tmp_path, project_name="TestProject")

    updated_state = save_real_test_project_init(
        root=tmp_path,
        project_name="TestProject",
        init_values=INIT_VALUES,
    )

    canonical = json.loads(result.canonical_records_path.read_text(encoding="utf-8"))
    assert len(canonical["records"]) == 4
    assert updated_state["display_state"]["init_status"] == "drafted_local"
    assert all(item["status"] == "drafted" for item in updated_state["display_state"]["init_requirements"])
    assert updated_state["projection"]["payload"]["init_status"] == "drafted_local"

    for item in updated_state["display_state"]["init_requirements"]:
        path = Path(item["path"])
        assert path.exists()
        assert "Generated for real TestProject UAT" not in path.read_text(encoding="utf-8")

    assert "TestProject charter for real UAT." in Path(
        updated_state["display_state"]["init_requirements"][0]["path"]
    ).read_text(encoding="utf-8")


def test_save_real_testproject_init_rejects_missing_required_fields(tmp_path: Path) -> None:
    create_real_test_project(root=tmp_path, project_name="TestProject")
    incomplete = dict(INIT_VALUES)
    incomplete["scope"] = ""

    with pytest.raises(ValueError, match="missing init fields: scope"):
        save_real_test_project_init(root=tmp_path, project_name="TestProject", init_values=incomplete)


def test_real_testproject_cleanup_is_scoped_to_test_root(tmp_path: Path) -> None:
    result = create_real_test_project(root=tmp_path, project_name="TestProject")
    keep_file = tmp_path / "keep.txt"
    keep_file.write_text("outside project", encoding="utf-8")

    cleanup_result = cleanup_real_test_project(project_root=result.project_root)

    assert cleanup_result.removed is True
    assert result.project_root.exists() is False
    assert keep_file.exists() is True


def test_cleanup_missing_testproject_is_noop(tmp_path: Path) -> None:
    missing = tmp_path / "missing-testproject"

    cleanup_result = cleanup_real_test_project(project_root=missing)

    assert cleanup_result.removed is False
    assert cleanup_result.project_root == missing.resolve()


def test_cleanup_rejects_unscoped_project_root(tmp_path: Path) -> None:
    unsafe = tmp_path / "not-a-real-uat-project"
    unsafe.mkdir()

    with pytest.raises(ValueError, match="real UAT project marker"):
        cleanup_real_test_project(project_root=unsafe)
