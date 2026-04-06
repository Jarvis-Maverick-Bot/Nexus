"""
harness.state_store — Layer 2 State Persistence

JSON file I/O for WorkItem, Project, TaskState, Workflow.
Provides save/load operations for all platform core objects.

Layer 2: Workflow checkpoint/state = resumability + operational runtime state
Layer 3: Event journal = append-only trace (handled separately in events.py)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from gov_langgraph.platform_model import (
    Project,
    WorkItem,
    TaskState,
    Workflow,
    ObjectNotFoundError,
)


# ---------------------------------------------------------------------------
# Serialization Helpers
# ---------------------------------------------------------------------------


def _serialize(obj: Any) -> dict[str, Any]:
    """
    Serialize a platform object to a JSON-serializable dict.
    Handles enums, datetime, and dataclasses.
    """
    if hasattr(obj, "__dataclass_fields__"):
        result = {}
        for name, field in obj.__dataclass_fields__.items():
            value = getattr(obj, name)
            result[name] = _serialize(value)
        return result
    elif isinstance(obj, enum_class := type(None).__class__.__mro__[0]):
        if hasattr(obj, "value"):
            return obj.value
        return str(obj)
    elif isinstance(obj, enum.Enum):
        return obj.value
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, list):
        return [_serialize(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    else:
        return obj


# ---------------------------------------------------------------------------
# StateStore
# ---------------------------------------------------------------------------


class StateStore:
    """
    JSON file persistence for Platform Core objects.

    Files are stored under a configurable root directory.
    File naming: {object_type}_{id}.json

    Supports: Project, WorkItem, TaskState, Workflow
    """

    def __init__(self, state_dir: Path | str):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    # --- Path helpers ---

    def _path(self, object_type: str, object_id: str) -> Path:
        return self.state_dir / f"{object_type}_{object_id}.json"

    # --- Save ---

    def save_project(self, project: Project) -> None:
        path = self._path("project", project.project_id)
        data = _serialize(project)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def save_workitem(self, item: WorkItem) -> None:
        path = self._path("workitem", item.task_id)
        data = _serialize(item)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def save_taskstate(self, state: TaskState) -> None:
        path = self._path("taskstate", state.task_id)
        data = _serialize(state)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def save_workflow(self, workflow: Workflow) -> None:
        path = self._path("workflow", workflow.workflow_id)
        data = _serialize(workflow)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # --- Load ---

    def _load_dict(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def load_project(self, project_id: str) -> Project:
        path = self._path("project", project_id)
        if not path.exists():
            raise ObjectNotFoundError("Project", project_id)
        data = self._load_dict(path)
        return _dict_to_project(data)

    def load_workitem(self, task_id: str) -> WorkItem:
        path = self._path("workitem", task_id)
        if not path.exists():
            raise ObjectNotFoundError("WorkItem", task_id)
        data = self._load_dict(path)
        return _dict_to_workitem(data)

    def load_taskstate(self, task_id: str) -> TaskState:
        path = self._path("taskstate", task_id)
        if not path.exists():
            raise ObjectNotFoundError("TaskState", task_id)
        data = self._load_dict(path)
        return _dict_to_taskstate(data)

    def load_workflow(self, workflow_id: str) -> Workflow:
        path = self._path("workflow", workflow_id)
        if not path.exists():
            raise ObjectNotFoundError("Workflow", workflow_id)
        data = self._load_dict(path)
        return _dict_to_workflow(data)

    # --- Exists ---

    def exists(self, object_type: str, object_id: str) -> bool:
        return self._path(object_type, object_id).exists()

    # --- Delete ---

    def delete_project(self, project_id: str) -> None:
        path = self._path("project", project_id)
        if path.exists():
            path.unlink()

    def delete_workitem(self, task_id: str) -> None:
        path = self._path("workitem", task_id)
        if path.exists():
            path.unlink()

    def delete_taskstate(self, task_id: str) -> None:
        path = self._path("taskstate", task_id)
        if path.exists():
            path.unlink()

    # --- List ---

    def list_projects(self) -> list[str]:
        return [p.stem.split("_", 1)[1] for p in self.state_dir.glob("project_*.json")]

    def list_workitems(self, project_id: str | None = None) -> list[str]:
        """List workitems, optionally filtered by project_id."""
        items = []
        for p in self.state_dir.glob("workitem_*.json"):
            task_id = p.stem.split("_", 1)[1]
            if project_id is None:
                items.append(task_id)
            else:
                try:
                    wi = self.load_workitem(task_id)
                    if wi.project_id == project_id:
                        items.append(task_id)
                except Exception:
                    pass
        return items


# ---------------------------------------------------------------------------
# Dict → Object reconstruction
# ---------------------------------------------------------------------------

import enum

from gov_langgraph.platform_model.objects import (
    ProjectStatus,
    TaskStatus,
    HandoffStatus,
    GateDecision,
)


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _dict_to_project(data: dict) -> Project:
    return Project(
        project_id=data["project_id"],
        project_name=data["project_name"],
        project_goal=data["project_goal"],
        domain_type=data["domain_type"],
        workflow_template_id=data.get("workflow_template_id"),
        project_status=ProjectStatus(data.get("project_status", "active")),
        project_summary=data.get("project_summary", ""),
        project_owner=data["project_owner"],
        created_at=_parse_datetime(data.get("created_at")) or datetime.utcnow(),
        closed_at=_parse_datetime(data.get("closed_at")),
    )


def _dict_to_workitem(data: dict) -> WorkItem:
    return WorkItem(
        task_id=data["task_id"],
        task_title=data["task_title"],
        project_id=data["project_id"],
        task_description=data.get("task_description", ""),
        workflow_id=data.get("workflow_id"),
        current_owner=data.get("current_owner"),
        dependency_task_ids=data.get("dependency_task_ids", []),
        expected_deliverable=data.get("expected_deliverable"),
        current_stage=data.get("current_stage", "BA"),
        task_status=TaskStatus(data.get("task_status", "backlog")),
        handoff_target=data.get("handoff_target"),
        priority=data.get("priority", 0),
        created_at=_parse_datetime(data.get("created_at")) or datetime.utcnow(),
    )


def _dict_to_taskstate(data: dict) -> TaskState:
    return TaskState(
        task_id=data["task_id"],
        current_stage=data["current_stage"],
        state_status=TaskStatus(data.get("state_status", "backlog")),
        current_owner=data.get("current_owner"),
        current_blocker=data.get("current_blocker"),
        next_expected_action=data.get("next_expected_action"),
        last_updated_at=_parse_datetime(data.get("last_updated_at")) or datetime.utcnow(),
    )


def _dict_to_workflow(data: dict) -> Workflow:
    return Workflow(
        workflow_id=data["workflow_id"],
        workflow_name=data["workflow_name"],
        domain_type=data["domain_type"],
        stage_list=data["stage_list"],
        allowed_transitions=data.get("allowed_transitions", {}),
        stage_role_map=data.get("stage_role_map", {}),
        default_handoff_points=data.get("default_handoff_points", []),
        default_gate_points=data.get("default_gate_points", []),
    )
