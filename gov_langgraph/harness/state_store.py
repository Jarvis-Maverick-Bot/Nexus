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
    Gate,
    Handoff,
    ObjectNotFoundError,
)


# ---------------------------------------------------------------------------
# Serialization Helpers
# ---------------------------------------------------------------------------


def _serialize(obj: Any) -> Any:
    """
    Serialize a value to a JSON-serializable type.
    Handles: dataclasses, enums, datetime, list, dict.
    """
    if hasattr(obj, "__dataclass_fields__"):
        # Dataclass → dict
        return {name: _serialize(getattr(obj, name)) for name in obj.__dataclass_fields__}
    elif isinstance(obj, enum.Enum):
        # Enum → its value
        return obj.value
    elif isinstance(obj, datetime):
        # Datetime → ISO string
        return obj.isoformat()
    elif isinstance(obj, list):
        return [_serialize(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    else:
        # Primitives (str, int, float, bool, None) pass through
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

    def save_gate(self, gate: Gate) -> None:
        path = self._path("gate", gate.gate_id)
        data = _serialize(gate)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def save_handoff(self, handoff: Handoff) -> None:
        path = self._path("handoff", handoff.handoff_id)
        data = _serialize(handoff)
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

    def load_gate(self, gate_id: str) -> Gate:
        path = self._path("gate", gate_id)
        if not path.exists():
            raise ObjectNotFoundError("Gate", gate_id)
        data = self._load_dict(path)
        return _dict_to_gate(data)

    def load_handoff(self, handoff_id: str) -> Handoff:
        path = self._path("handoff", handoff_id)
        if not path.exists():
            raise ObjectNotFoundError("Handoff", handoff_id)
        data = self._load_dict(path)
        return _dict_to_handoff(data)

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

    def list_all_gates(self) -> list[str]:
        """List all gate IDs."""
        return [p.stem.split("_", 1)[1] for p in self.state_dir.glob("gate_*.json")]

    def list_gates_for_task(self, task_id: str) -> list[Gate]:
        """List all gates for a given task_id, newest first."""
        gates = []
        for p in self.state_dir.glob("gate_*.json"):
            gate_id = p.stem.split("_", 1)[1]
            try:
                gate = self.load_gate(gate_id)
                if gate.task_id == task_id:
                    gates.append(gate)
            except Exception:
                pass
        # Sort newest first
        gates.sort(key=lambda g: g.decided_at or datetime.min, reverse=True)
        return gates

    def get_gate_decision_for_stage(self, task_id: str, stage: str) -> Gate | None:
        """Return the gate decision for a task+stage, or None if no decision recorded yet.

        Returns the existing Gate record (approved/rejected) if one exists.
        Returns None if no gate record exists for this task+stage (gate is still pending).
        """
        for p in self.state_dir.glob("gate_*.json"):
            gate_id = p.stem.split("_", 1)[1]
            try:
                gate = self.load_gate(gate_id)
                if gate.task_id == task_id and gate.stage == stage:
                    return gate  # exists = already decided
            except Exception:
                pass
        return None  # no gate record = pending


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
    from gov_langgraph.platform_model import (
        Artifact, ArtifactType, AcceptancePackage,
        AdvisorySignal, AdvisoryType,
        Blocker, BlockerSeverity,
    )

    # Reconstruct artifacts dict
    artifacts: dict[str, Artifact] = {}
    for artifact_id, artifact_data in data.get("artifacts", {}).items():
        at = ArtifactType(artifact_data["artifact_type"])
        artifacts[artifact_id] = Artifact(
            artifact_id=artifact_data.get("artifact_id", artifact_id),
            artifact_type=at,
            project_id=artifact_data["project_id"],
            content=artifact_data.get("content", ""),
            produced_by=artifact_data.get("produced_by", ""),
            produced_at=_parse_datetime(artifact_data.get("produced_at")) or datetime.utcnow(),
        )

    # Reconstruct acceptance package
    acceptance_package: AcceptancePackage | None = None
    pkg_data = data.get("acceptance_package")
    if pkg_data:
        pkg_artifacts: dict[ArtifactType, Artifact] = {}
        for at_str, art_data in pkg_data.get("artifacts", {}).items():
            at = ArtifactType(at_str)
            pkg_artifacts[at] = Artifact(
                artifact_type=at,
                project_id=art_data["project_id"],
                content=art_data.get("content", ""),
                produced_by=art_data.get("produced_by", ""),
                produced_at=_parse_datetime(art_data.get("produced_at")) or datetime.utcnow(),
            )
        acceptance_package = AcceptancePackage(
            package_id=pkg_data.get("package_id", ""),
            task_id=pkg_data.get("task_id", ""),
            project_id=pkg_data.get("project_id", ""),
            artifacts=pkg_artifacts,
            verification_notes=pkg_data.get("verification_notes", ""),
            acceptance_decision=GateDecision(pkg_data["acceptance_decision"]) if pkg_data.get("acceptance_decision") else None,
            decision_by=pkg_data.get("decision_by"),
            decision_note=pkg_data.get("decision_note", ""),
            decided_at=_parse_datetime(pkg_data.get("decided_at")),
            created_at=_parse_datetime(pkg_data.get("created_at")) or datetime.utcnow(),
        )

    # Reconstruct advisories
    advisories: dict[str, AdvisorySignal] = {}
    for adv_id, adv_data in data.get("advisories", {}).items():
        advisories[adv_id] = AdvisorySignal(
            advisory_id=adv_data.get("advisory_id", adv_id),
            advisory_type=AdvisoryType(adv_data["advisory_type"]),
            project_id=adv_data["project_id"],
            message=adv_data.get("message", ""),
            severity=adv_data.get("severity", "info"),
            task_id=adv_data.get("task_id"),
            stage=adv_data.get("stage"),
            actor=adv_data.get("actor", "maverick"),
            created_at=_parse_datetime(adv_data.get("created_at")) or datetime.utcnow(),
            acknowledged=adv_data.get("acknowledged", False),
        )

    # Reconstruct blockers
    blockers: dict[str, Blocker] = {}
    for blk_id, blk_data in data.get("blockers", {}).items():
        blockers[blk_id] = Blocker(
            blocker_id=blk_data.get("blocker_id", blk_id),
            task_id=blk_data["task_id"],
            project_id=blk_data["project_id"],
            reason=blk_data.get("reason", ""),
            severity=BlockerSeverity(blk_data.get("severity", "medium")),
            detected_at=_parse_datetime(blk_data.get("detected_at")) or datetime.utcnow(),
            resolved_at=_parse_datetime(blk_data.get("resolved_at")),
            resolved_by=blk_data.get("resolved_by"),
        )

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
        artifacts=artifacts,
        acceptance_package=acceptance_package,
        advisories=advisories,
        blockers=blockers,
        # V1.6 intake fields
        intake_complete=data.get("intake_complete", False),
        intake_summary=data.get("intake_summary", ""),
        intake_deliverable=data.get("intake_deliverable", ""),
        intake_business_context=data.get("intake_business_context", ""),
        output_package=data.get("output_package", {}),
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


def _dict_to_gate(data: dict) -> Gate:
    from gov_langgraph.platform_model import GateDecision  # avoid circular
    return Gate(
        task_id=data["task_id"],
        stage=data["stage"],
        gate_type=data.get("gate_type", "approval"),
        decision=GateDecision(data["decision"]) if data.get("decision") else None,
        decision_by=data.get("decision_by"),
        decision_note=data.get("decision_note", ""),
        gate_id=data["gate_id"],
        decided_at=datetime.fromisoformat(data["decided_at"]) if data.get("decided_at") else None,
    )


def _dict_to_handoff(data: dict) -> Handoff:
    from gov_langgraph.platform_model import HandoffStatus  # avoid circular
    return Handoff(
        task_id=data["task_id"],
        from_stage=data["from_stage"],
        to_stage=data["to_stage"],
        from_owner=data["from_owner"],
        to_owner=data["to_owner"],
        deliverable_reference=data.get("deliverable_reference"),
        handoff_note=data.get("handoff_note", ""),
        handoff_id=data["handoff_id"],
        handoff_status=HandoffStatus(data["handoff_status"]) if data.get("handoff_status") else HandoffStatus.PENDING,
        created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
    )
