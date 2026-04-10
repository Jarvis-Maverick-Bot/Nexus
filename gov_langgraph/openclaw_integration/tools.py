"""
openclaw_integration.tools — OpenClaw tool definitions for gov_langgraph

Each @tool function:
- Takes structured dict input
- Returns structured dict {ok, ...} or {error, ...}
- All mutations go through Platform Core + Harness
- Events appended to EventJournal by the coordinator layer

Tool return format: {ok: bool, task_id?, project_id?, stage?, status?,
                    message: str, data?: dict}
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from gov_langgraph.harness import HarnessConfig, StateStore, Checkpointer, EventJournal
from gov_langgraph.platform_model import (
    Project, WorkItem, TaskState, Workflow,
    Role, TaskStatus, Handoff, Gate, GateDecision, Event,
    Artifact, ArtifactType, AcceptancePackage,
    get_v1_pipeline_workflow,
)
from gov_langgraph.platform_model.state_machine import StateMachine
from gov_langgraph.platform_model.authority import Action, check_authority
from gov_langgraph.platform_model.exceptions import ObjectNotFoundError, PlatformException
from gov_langgraph.langgraph_engine import init_runtime, run_workitem as langgraph_run_workitem


# Terminal stages — tasks in these states have no actionable gates
_TERMINAL_STATUSES = {TaskStatus.DONE, TaskStatus.CANCELLED}


def _error_response(error_type: str, message: str, **kwargs) -> dict:
    """Build a structured error response with error_type classification."""
    return {"ok": False, "error_type": error_type, "message": message, **kwargs}


def _is_terminal(workitem: WorkItem) -> bool:
    """Check if a workitem is at a terminal state."""
    return workitem.task_status in _TERMINAL_STATUSES


# ---------------------------------------------------------------------------
# Harness instances (created once, passed to tools)
# ---------------------------------------------------------------------------

_harness: dict[str, Any] = {}


def init_harness() -> dict:
    """
    Initialize harness layer. Call once on startup.
    Returns the harness dict with store, checkpointer, journal.
    """
    global _harness
    if _harness:
        return _harness

    cfg = HarnessConfig()
    cfg.ensure_dirs()
    store = StateStore(cfg.state_dir)
    ckpt = Checkpointer(cfg)
    journal = EventJournal(cfg.event_dir)

    _harness = {
        "config": cfg,
        "store": store,
        "checkpointer": ckpt,
        "journal": journal,
    }
    return _harness


# (removed _default_workflow — now imported from platform_model.workflows)


def _sm() -> StateMachine:
    """Get a StateMachine wired with harness instances."""
    h = _harness
    return StateMachine(
        workflow=get_v1_pipeline_workflow(),
        checkpointer=h["checkpointer"],
        event_journal=h["journal"],
    )


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


def create_project_tool(input: dict) -> dict:
    """
    Create a new project.

    Args:
        input: {project_name: str, project_goal: str, domain_type: str, project_owner: str}
    Returns:
        {ok: bool, project_id: str, message: str}
    """
    try:
        h = _harness
        project = Project(
            project_name=input["project_name"],
            project_goal=input.get("project_goal", ""),
            domain_type=input.get("domain_type", "internal"),
            project_owner=input.get("project_owner", ""),
        )
        h["store"].save_project(project)

        h["journal"].append_raw(
            project_id=project.project_id,
            event_type="project_created",
            event_summary=f"Project '{project.project_name}' created",
            actor=input.get("actor", "unknown"),
        )

        return {
            "ok": True,
            "project_id": project.project_id,
            "project_name": project.project_name,
            "message": f"Project '{project.project_name}' created",
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "message": f"Failed to create project: {e}"}


def create_task_tool(input: dict) -> dict:
    """
    Create a new workitem under a project.

    Args:
        input: {
            task_title: str,
            project_id: str,
            current_owner: str,
            current_stage: str (default "BA"),
            priority: int (default 3),
        }
    Returns:
        {ok: bool, task_id: str, message: str}
    """
    try:
        h = _harness
        project_id = input["project_id"]
        current_owner = input.get("current_owner", "")
        current_stage = input.get("current_stage", "BA")

        workitem = WorkItem(
            task_title=input["task_title"],
            project_id=project_id,
            current_owner=current_owner,
            current_stage=current_stage,
            priority=input.get("priority", 3),
        )
        h["store"].save_workitem(workitem)

        # Create initial TaskState
        task_state = TaskState(
            task_id=workitem.task_id,
            current_stage=current_stage,
            state_status=TaskStatus.BACKLOG,
            current_owner=current_owner,
        )
        h["store"].save_taskstate(task_state)

        h["journal"].append_raw(
            project_id=project_id,
            event_type="task_created",
            event_summary=f"Task '{workitem.task_title}' created in stage '{current_stage}'",
            actor=input.get("actor", "unknown"),
            task_id=workitem.task_id,
            related_stage=current_stage,
        )

        return {
            "ok": True,
            "task_id": workitem.task_id,
            "task_title": workitem.task_title,
            "current_stage": current_stage,
            "message": f"Task '{workitem.task_title}' created",
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "message": f"Failed to create task: {e}"}


def kickoff_task_tool(input: dict) -> dict:
    """
    Announce a new project kickoff — creates a workitem at INTAKE stage.

    V1.5: project_id is required. Every task must belong to an explicit project.
    No DEFAULT_PROJECT_ID fallback — use create_project_tool first if needed.

    Args:
        input: {
            title: str (required) — task title,
            project_id: str (required) — UUID of the project to create task under,
            description: str (required) — what this work is,
            priority: int (required) — 0=P0, 1=P1, 2=P2, 3=P3,
            assignee: str (optional) — initial owner, blank = unassigned,
            actor: str (required) — who is kicking off,
        }
    Returns:
        {ok: bool, task_id: str, task_title: str, current_stage: str, message: str}
    """
    try:
        h = _harness

        title = input["title"]
        project_id = input.get("project_id", "").strip()
        if not project_id:
            return _error_response(
                "validation_error",
                "project_id is required. Create a project first via POST /projects."
            )

        description = input.get("description", "")
        priority = input.get("priority", 3)
        assignee = input.get("assignee", "").strip() or "unassigned"
        actor = input.get("actor", "unknown")

        # Validate project exists
        if not h["store"].exists("project", project_id):
            return _error_response(
                "project_not_found",
                f"Project '{project_id}' not found. Create it first via POST /projects."
            )

        workitem = WorkItem(
            task_title=title,
            task_description=description,
            project_id=project_id,
            current_owner=assignee,
            current_stage="INTAKE",
            priority=priority,
        )
        h["store"].save_workitem(workitem)

        task_state = TaskState(
            task_id=workitem.task_id,
            current_stage="INTAKE",
            state_status=TaskStatus.BACKLOG,
            current_owner=assignee,
        )
        h["store"].save_taskstate(task_state)

        h["journal"].append_raw(
            project_id=project_id,
            event_type="task_kickoff",
            event_summary=f"Kickoff announced: '{title}' — assigned to {assignee}",
            actor=actor,
            task_id=workitem.task_id,
            related_stage="INTAKE",
        )

        return {
            "ok": True,
            "task_id": workitem.task_id,
            "task_title": workitem.task_title,
            "project_id": project_id,
            "current_stage": "INTAKE",
            "assignee": assignee,
            "message": f"Kickoff announced: '{title}' entered pipeline at INTAKE under project {project_id}, assigned to {assignee}.",
        }
    except PlatformException as e:
        return _error_response("platform_unavailable", str(e))
    except Exception as e:
        return _error_response("unknown", f"Failed to announce kickoff: {e}")


def advance_stage_tool(input: dict) -> dict:
    """
    Advance a task ONE stage at a time via StateMachine.

    Bounded advance: validates target is the next valid stage,
    checks authority, advances exactly one stage.

    Args:
        input: {
            task_id: str,
            target_stage: str,
            actor: str (role name),
        }
    Returns:
        {ok: bool, task_id: str, from_stage: str, to_stage: str, message: str}
    """
    try:
        task_id = input["task_id"]
        target_stage = input["target_stage"]
        actor = input.get("actor", "unknown")

        # Load workitem
        h = _harness
        workitem = h["store"].load_workitem(task_id)
        from_stage = workitem.current_stage
        project_id = workitem.project_id

        # Use StateMachine directly for bounded one-stage advance
        from gov_langgraph.langgraph_engine.runtime import get_runtime
        rt = get_runtime()

        sm = StateMachine(
            workflow=get_v1_pipeline_workflow(),
            checkpointer=rt.checkpointer,
            event_journal=rt.event_journal,
        )

        # Advance exactly one stage
        record = sm.advance_stage(
            work_item=workitem,
            target_stage=target_stage,
            actor_role=actor,
            project_id=project_id,
        )

        # Persist updated workitem
        h["store"].save_workitem(workitem)

        # Update TaskState
        ts = h["store"].load_taskstate(task_id)
        ts.current_stage = target_stage
        h["store"].save_taskstate(ts)

        return {
            "ok": True,
            "task_id": task_id,
            "from_stage": from_stage,
            "to_stage": target_stage,
            "current_action": "advance",
            "message": f"Advanced from '{from_stage}' to '{target_stage}'",
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "message": f"Failed to advance stage: {e}"}


def submit_handoff_tool(input: dict) -> dict:
    """
    Submit a handoff from one owner to another.

    Args:
        input: {
            task_id: str,
            from_owner: str,
            to_owner: str,
            actor: str,
        }
    Returns:
        {ok: bool, handoff_id: str, message: str}
    """
    try:
        h = _harness
        task_id = input["task_id"]
        from_owner = input["from_owner"]
        to_owner = input["to_owner"]
        actor = input.get("actor", "unknown")

        workitem = h["store"].load_workitem(task_id)
        handoff = Handoff(
            task_id=task_id,
            from_stage=workitem.current_stage,
            to_stage=workitem.current_stage,  # next stage implied by workflow
            from_owner=from_owner,
            to_owner=to_owner,
        )
        h["store"].save_handoff(handoff)

        # Update workitem handoff target
        workitem.handoff_target = to_owner
        h["store"].save_workitem(workitem)

        h["journal"].append_raw(
            project_id=workitem.project_id,
            event_type="handoff_submitted",
            event_summary=f"Handoff submitted for task '{task_id}' to '{to_owner}'",
            actor=actor,
            task_id=task_id,
        )

        return {
            "ok": True,
            "handoff_id": handoff.handoff_id,
            "task_id": task_id,
            "from_owner": from_owner,
            "to_owner": to_owner,
            "message": f"Handoff submitted to '{to_owner}'",
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "message": f"Failed to submit handoff: {e}"}


def approve_gate_tool(input: dict) -> dict:
    """
    Approve a gate for a task. Double-decision prevention — returns error if already decided.

    Args:
        input: {
            task_id: str,
            gate_name: str,
            actor: str,
            notes: str (optional),
        }
    Returns:
        {ok: bool, gate_id: str, gate_status: str, message: str}
    """
    try:
        h = _harness
        task_id = input["task_id"]
        gate_name = input.get("gate_name", "stage_advance")
        actor = input.get("actor", "unknown")
        notes = input.get("notes", "")

        workitem = h["store"].load_workitem(task_id)
        stage = workitem.current_stage

        # Check if already decided
        existing = h["store"].get_gate_decision_for_stage(task_id, stage)
        if existing is not None:
            return _error_response(
                "already_decided",
                f"Gate at '{stage}' already has a decision: {existing.decision.value}",
                gate_id=existing.gate_id,
                gate_status=existing.decision.value if existing.decision else "pending",
                task_id=task_id,
            )

        # Terminal state — no gate action available
        if _is_terminal(workitem):
            return _error_response(
                "terminal_state",
                f"Task is at terminal stage ('{stage}') — no gate action available.",
                task_id=task_id,
            )

        gate = Gate(
            task_id=task_id,
            stage=stage,
            gate_type=gate_name,
            decision=GateDecision.APPROVED,
            decision_by=actor,
            decision_note=notes,
        )
        h["store"].save_gate(gate)

        h["journal"].append_raw(
            project_id=workitem.project_id,
            event_type="gate_approved",
            event_summary=f"Gate at '{stage}' approved by '{actor}'",
            actor=actor,
            task_id=task_id,
            related_stage=stage,
        )

        return {
            "ok": True,
            "gate_id": gate.gate_id,
            "gate_status": "approved",
            "gate_type": gate.gate_type,
            "stage": gate.stage,
            "task_id": task_id,
            "message": f"Gate approved at stage '{stage}'.",
        }
    except ObjectNotFoundError:
        return _error_response("task_not_found", f"Task '{task_id}' not found")
    except PlatformException as e:
        return _error_response("platform_unavailable", str(e))
    except Exception as e:
        return _error_response("unknown", f"Failed to approve gate: {e}")


def reject_gate_tool(input: dict) -> dict:
    """
    Reject a gate for a task. Requires a reason.

    Args:
        input: {
            task_id: str,
            gate_name: str,
            actor: str,
            notes: str (required — reason for rejection),
        }
    Returns:
        {ok: bool, gate_id: str, gate_status: str, message: str}
    """
    try:
        h = _harness
        task_id = input["task_id"]
        gate_name = input.get("gate_name", "stage_advance")
        actor = input.get("actor", "unknown")
        notes = input.get("notes", "")

        if not notes.strip():
            return {
                "ok": False,
                "error": "reason_required",
                "message": "Rejection reason is required.",
            }

        workitem = h["store"].load_workitem(task_id)
        stage = workitem.current_stage

        # Check if already decided
        existing = h["store"].get_gate_decision_for_stage(task_id, stage)
        if existing is not None:
            return {
                "ok": False,
                "gate_id": existing.gate_id,
                "gate_status": existing.decision.value if existing.decision else "pending",
                "task_id": task_id,
                "message": f"Gate at '{stage}' already has a decision: {existing.decision.value}",
            }

        gate = Gate(
            task_id=task_id,
            stage=stage,
            gate_type=gate_name,
            decision=GateDecision.REJECTED,
            decision_by=actor,
            decision_note=notes,
        )
        h["store"].save_gate(gate)

        h["journal"].append_raw(
            project_id=workitem.project_id,
            event_type="gate_rejected",
            event_summary=f"Gate at '{stage}' rejected by '{actor}' — reason: {notes}",
            actor=actor,
            task_id=task_id,
            related_stage=stage,
        )

        return {
            "ok": True,
            "gate_id": gate.gate_id,
            "gate_status": "rejected",
            "gate_type": gate.gate_type,
            "stage": gate.stage,
            "task_id": task_id,
            "message": f"Gate rejected at stage '{stage}'. Reason: {notes}",
        }
    except ObjectNotFoundError:
        return _error_response("task_not_found", f"Task '{task_id}' not found")
    except PlatformException as e:
        return _error_response("platform_unavailable", str(e))
    except Exception as e:
        return _error_response("unknown", f"Failed to reject gate: {e}")



def get_status_tool(input: dict) -> dict:
    """
    Get current status of a task.

    Args:
        input: {task_id: str}
    Returns:
        {ok: bool, task_id, task_title, current_stage, current_owner,
         task_status, current_blocker, message: str}
    """
    try:
        h = _harness
        task_id = input["task_id"]

        workitem = h["store"].load_workitem(task_id)

        blocker = None
        try:
            ts = h["store"].load_taskstate(task_id)
            blocker = ts.current_blocker
            task_status = ts.task_status.value
        except Exception:
            task_status = workitem.task_status.value

        return {
            "ok": True,
            "task_id": task_id,
            "task_title": workitem.task_title,
            "current_stage": workitem.current_stage,
            "current_owner": workitem.current_owner,
            "task_status": task_status,
            "current_blocker": blocker,
            "message": f"Status: {workitem.task_title} is in '{workitem.current_stage}'",
        }
    except ObjectNotFoundError:
        return _error_response("task_not_found", f"Task '{task_id}' not found")
    except PlatformException as e:
        return _error_response("platform_unavailable", str(e))
    except Exception as e:
        return _error_response("unknown", f"Failed to get status: {e}")


def list_tasks_tool(input: dict) -> dict:
    """
    List all workitems for a project.

    Args:
        input: {project_id: str}
    Returns:
        {ok: bool, project_id: str, tasks: list[dict], message: str}
    """
    try:
        h = _harness
        project_id = input["project_id"]

        task_ids = h["store"].list_workitems(project_id=project_id)
        tasks = []
        for tid in task_ids:
            w = h["store"].load_workitem(tid)
            tasks.append({
                "task_id": w.task_id,
                "task_title": w.task_title,
                "current_stage": w.current_stage,
                "current_owner": w.current_owner,
                "task_status": w.task_status.value,
            })

        return {
            "ok": True,
            "project_id": project_id,
            "tasks": tasks,
            "count": len(tasks),
            "message": f"{len(tasks)} task(s) found",
        }
    except PlatformException as e:
        return _error_response("platform_unavailable", str(e))
    except Exception as e:
        return _error_response("unknown", f"Failed to list tasks: {e}")


def get_gate_panel_tool(input: dict) -> dict:
    """
    Get gate panel for a task — the PMO gate confirmation surface.

    Shows: task identity, current stage, gate status, evidence summary,
    and Alex's decision options (approve/reject).

    Args:
        input: {task_id: str}
    Returns:
        {ok: bool, task_id, task_title, current_stage, current_owner,
         gate_status, gate_stage, gate_decision, gate_decision_by,
         gate_decision_note, gate_decided_at, message}

    gate_status values:
        - "pending"   — no gate record yet, awaiting Alex decision
        - "approved"  — already approved
        - "rejected"  — already rejected
        - "no_gate"   — current stage has no gate configured
    """
    try:
        h = _harness
        task_id = input["task_id"]

        workitem = h["store"].load_workitem(task_id)
        current_stage = workitem.current_stage

        # Terminal state — no gate action available
        if _is_terminal(workitem):
            return {
                "ok": True,
                "task_id": task_id,
                "task_title": workitem.task_title,
                "current_stage": current_stage,
                "current_owner": workitem.current_owner,
                "gate_stage": current_stage,
                "gate_type": "stage_advance",
                "gate_status": "no_gate",
                "gate_decision": None,
                "gate_decision_by": None,
                "gate_decision_note": None,
                "gate_decided_at": None,
                "message": f"Task is at terminal stage ('{current_stage}') — no gate action available.",
            }

        # Check if a gate decision exists for this task+stage
        gate = h["store"].get_gate_decision_for_stage(task_id, current_stage)

        if gate is None:
            gate_status = "pending"
            gate_decision = None
            gate_decision_by = None
            gate_decision_note = ""
            gate_decided_at = None
        else:
            gate_decision = gate.decision.value if gate.decision else None
            if gate_decision == "approved":
                gate_status = "approved"
            elif gate_decision == "rejected":
                gate_status = "rejected"
            else:
                gate_status = "pending"
            gate_decision_by = gate.decision_by
            gate_decision_note = gate.decision_note
            gate_decided_at = gate.decided_at.isoformat() if gate.decided_at else None

        return {
            "ok": True,
            "task_id": task_id,
            "task_title": workitem.task_title,
            "current_stage": current_stage,
            "current_owner": workitem.current_owner,
            "gate_stage": current_stage,
            "gate_type": "stage_advance",
            "gate_status": gate_status,
            "gate_decision": gate_decision,
            "gate_decision_by": gate_decision_by,
            "gate_decision_note": gate_decision_note,
            "gate_decided_at": gate_decided_at,
            "message": _gate_message(gate_status, current_stage),
        }
    except ObjectNotFoundError:
        return _error_response("task_not_found", f"Task '{input['task_id']}' not found")
    except PlatformException as e:
        return _error_response("platform_unavailable", str(e))
    except Exception as e:
        return _error_response("unknown", f"Failed to get gate panel: {e}")


def _gate_message(status: str, stage: str) -> str:
    if status == "pending":
        return f"Gate at '{stage}' is pending your decision."
    elif status == "approved":
        return f"Gate at '{stage}' was approved."
    elif status == "rejected":
        return f"Gate at '{stage}' was rejected."
    return f"No gate configured for stage '{stage}'."


# ---------------------------------------------------------------------------
# Project tools
# ---------------------------------------------------------------------------


def get_project_tool(input: dict) -> dict:
    """
    Get details of a specific project including artifact completeness.

    Args:
        input: {project_id: str}
    Returns:
        {ok: bool, project_id, project_name, project_status, artifact_completeness, missing_artifacts, ...}
    """
    try:
        h = _harness
        project_id = input["project_id"]
        project = h["store"].load_project(project_id)

        # Build artifact completeness map
        artifact_map = project.get_artifacts_by_type()
        artifact_completeness = {}
        for at in ArtifactType.all():
            if at in artifact_map and not artifact_map[at].is_empty():
                artifact_completeness[at.value] = {
                    "artifact_id": artifact_map[at].artifact_id,
                    "produced_by": artifact_map[at].produced_by,
                    "produced_at": artifact_map[at].produced_at.isoformat(),
                    "has_content": True,
                }
            else:
                artifact_completeness[at.value] = {"has_content": False}

        missing = project.get_missing_artifacts()

        return {
            "ok": True,
            "project_id": project.project_id,
            "project_name": project.project_name,
            "project_goal": project.project_goal,
            "domain_type": project.domain_type,
            "project_owner": project.project_owner,
            "project_status": project.project_status.value,
            "created_at": project.created_at.isoformat(),
            "artifact_completeness": artifact_completeness,
            "missing_artifacts": [at.value for at in missing],
            "all_artifacts_present": len(missing) == 0,
            "message": f"Project: {project.project_name} ({project.project_status.value})",
        }
    except ObjectNotFoundError:
        return _error_response("project_not_found", f"Project '{input.get('project_id')}' not found")
    except Exception as e:
        return _error_response("unknown", f"Failed to get project: {e}")


def list_projects_tool(input: dict) -> dict:
    """
    List all projects, optionally filtered by status.

    Args:
        input: {status: str | None}  # active, on_hold, closed, shutdown
    Returns:
        {ok: bool, projects: list[dict], count: int}
    """
    try:
        h = _harness
        status_filter = input.get("status")

        project_ids = h["store"].list_projects()
        projects = []
        for pid in project_ids:
            try:
                proj = h["store"].load_project(pid)
                if status_filter is None or proj.project_status.value == status_filter:
                    projects.append({
                        "project_id": proj.project_id,
                        "project_name": proj.project_name,
                        "project_status": proj.project_status.value,
                        "project_owner": proj.project_owner,
                        "created_at": proj.created_at.isoformat(),
                    })
            except Exception:
                pass  # Skip corrupted project records

        return {
            "ok": True,
            "projects": projects,
            "count": len(projects),
            "message": f"{len(projects)} project(s) found",
        }
    except Exception as e:
        return _error_response("unknown", f"Failed to list projects: {e}")


# ---------------------------------------------------------------------------
# Artifact tools
# ---------------------------------------------------------------------------

def upsert_artifact_tool(input: dict) -> dict:
    """
    Add or update an artifact for a project.

    Args:
        input: {
            project_id: str,
            artifact_type: str,  # scope|spec|arch|testcase|testreport|guideline
            content: str,
            produced_by: str,
        }
    Returns:
        {ok: bool, artifact_id: str, message: str}
    """
    try:
        h = _harness
        project_id = input["project_id"]
        artifact_type_str = input["artifact_type"]
        content = input.get("content", "")
        produced_by = input.get("produced_by", "")

        # Validate artifact type
        try:
            artifact_type = ArtifactType(artifact_type_str)
        except ValueError:
            return _error_response(
                "validation_error",
                f"Invalid artifact_type: {artifact_type_str}. Must be one of: {[e.value for e in ArtifactType.all()]}",
            )

        project = h["store"].load_project(project_id)

        # Create artifact
        artifact = Artifact(
            artifact_type=artifact_type,
            project_id=project_id,
            content=content,
            produced_by=produced_by,
        )
        project.add_artifact(artifact)
        h["store"].save_project(project)

        h["journal"].append_raw(
            project_id=project_id,
            event_type="artifact_updated",
            event_summary=f"Artifact '{artifact_type.value}' updated by {produced_by}",
            actor=produced_by,
        )

        return {
            "ok": True,
            "artifact_id": artifact.artifact_id,
            "artifact_type": artifact_type.value,
            "message": f"Artifact '{artifact_type.display_name}' saved",
        }
    except ObjectNotFoundError:
        return _error_response("project_not_found", f"Project '{input.get('project_id')}' not found")
    except Exception as e:
        return _error_response("unknown", f"Failed to upsert artifact: {e}")


def get_artifacts_tool(input: dict) -> dict:
    """
    Get all artifacts for a project.

    Args:
        input: {project_id: str}
    Returns:
        {ok: bool, artifacts: list[dict], missing: list[str]}
    """
    try:
        h = _harness
        project_id = input["project_id"]
        project = h["store"].load_project(project_id)

        type_map = project.get_artifacts_by_type()
        artifacts = []
        for at in ArtifactType.all():
            if at in type_map and not type_map[at].is_empty():
                artifacts.append({
                    "artifact_id": type_map[at].artifact_id,
                    "artifact_type": at.value,
                    "display_name": at.display_name,
                    "produced_by": type_map[at].produced_by,
                    "produced_at": type_map[at].produced_at.isoformat(),
                    "content_preview": type_map[at].content[:200] if type_map[at].content else "",
                    "has_content": True,
                })
            else:
                artifacts.append({
                    "artifact_type": at.value,
                    "display_name": at.display_name,
                    "generated_by": at.generated_by,
                    "stage_hint": at.stage_hint,
                    "has_content": False,
                })

        missing = project.get_missing_artifacts()
        return {
            "ok": True,
            "project_id": project_id,
            "artifacts": artifacts,
            "missing": [at.value for at in missing],
            "all_present": len(missing) == 0,
        }
    except ObjectNotFoundError:
        return _error_response("project_not_found", f"Project '{input.get('project_id')}' not found")
    except Exception as e:
        return _error_response("unknown", f"Failed to get artifacts: {e}")


# ---------------------------------------------------------------------------
# Acceptance tools
# ---------------------------------------------------------------------------

def get_acceptance_package_tool(input: dict) -> dict:
    """
    Get acceptance package for a project.

    Args:
        input: {project_id: str}
    Returns:
        {ok: bool, acceptance_package: dict | None, artifact_summary: dict}
    """
    try:
        h = _harness
        project_id = input["project_id"]
        project = h["store"].load_project(project_id)

        pkg = project.acceptance_package
        if pkg is None:
            return {
                "ok": True,
                "project_id": project_id,
                "acceptance_package": None,
                "all_artifacts_present": project.is_artifact_complete(),
                "missing_artifacts": [at.value for at in project.get_missing_artifacts()],
                "message": "No acceptance package created yet",
            }

        return {
            "ok": True,
            "project_id": project_id,
            "acceptance_package": {
                "package_id": pkg.package_id,
                "task_id": pkg.task_id,
                "is_complete": pkg.is_complete(),
                "verification_notes": pkg.verification_notes,
                "acceptance_decision": pkg.acceptance_decision.value if pkg.acceptance_decision else None,
                "decision_by": pkg.decision_by,
                "decision_note": pkg.decision_note,
                "decided_at": pkg.decided_at.isoformat() if pkg.decided_at else None,
                "created_at": pkg.created_at.isoformat(),
            },
            "all_artifacts_present": project.is_artifact_complete(),
            "missing_artifacts": [at.value for at in project.get_missing_artifacts()],
            "message": f"Acceptance package: {pkg.acceptance_decision.value if pkg.acceptance_decision else 'pending'}",
        }
    except ObjectNotFoundError:
        return _error_response("project_not_found", f"Project '{input.get('project_id')}' not found")
    except Exception as e:
        return _error_response("unknown", f"Failed to get acceptance package: {e}")


def create_acceptance_package_tool(input: dict) -> dict:
    """
    Create or update acceptance package for a project.

    Args:
        input: {project_id: str, task_id: str, verification_notes: str}
    Returns:
        {ok: bool, package_id: str, is_complete: bool, missing_artifacts: list[str]}
    """
    try:
        h = _harness
        project_id = input["project_id"]
        task_id = input.get("task_id", "")
        verification_notes = input.get("verification_notes", "")

        project = h["store"].load_project(project_id)

        pkg = AcceptancePackage(
            task_id=task_id,
            project_id=project_id,
            verification_notes=verification_notes,
        )
        # Link existing artifacts
        type_map = project.get_artifacts_by_type()
        for at, artifact in type_map.items():
            pkg.artifacts[at] = artifact

        project.acceptance_package = pkg
        h["store"].save_project(project)

        missing = project.get_missing_artifacts()
        h["journal"].append_raw(
            project_id=project_id,
            event_type="acceptance_package_created",
            event_summary=f"Acceptance package created for task {task_id}",
            actor=input.get("actor", "system"),
        )

        return {
            "ok": True,
            "package_id": pkg.package_id,
            "task_id": task_id,
            "is_complete": pkg.is_complete(),
            "missing_artifacts": [at.value for at in missing],
            "message": f"Acceptance package created — {len(missing)} artifact(s) missing",
        }
    except ObjectNotFoundError:
        return _error_response("project_not_found", f"Project '{input.get('project_id')}' not found")
    except Exception as e:
        return _error_response("unknown", f"Failed to create acceptance package: {e}")


def approve_acceptance_tool(input: dict) -> dict:
    """
    Approve an acceptance package (Alex/governance decision).

    Args:
        input: {project_id: str, actor: str, note: str}
    Returns:
        {ok: bool, message: str}
    """
    try:
        h = _harness
        project_id = input["project_id"]
        actor = input.get("actor", "")
        note = input.get("note", "")

        project = h["store"].load_project(project_id)
        if project.acceptance_package is None:
            return _error_response("validation_error", "No acceptance package to approve")

        project.acceptance_package.approve(decided_by=actor, note=note)
        h["store"].save_project(project)

        h["journal"].append_raw(
            project_id=project_id,
            event_type="acceptance_approved",
            event_summary=f"Acceptance approved by {actor}: {note}",
            actor=actor,
        )

        return {
            "ok": True,
            "message": f"Acceptance approved by {actor}",
        }
    except ObjectNotFoundError:
        return _error_response("project_not_found", f"Project '{input.get('project_id')}' not found")
    except Exception as e:
        return _error_response("unknown", f"Failed to approve acceptance: {e}")


def reject_acceptance_tool(input: dict) -> dict:
    """
    Reject an acceptance package and request revision.

    Args:
        input: {project_id: str, actor: str, reason: str}
    Returns:
        {ok: bool, message: str}
    """
    try:
        h = _harness
        project_id = input["project_id"]
        actor = input.get("actor", "")
        reason = input.get("reason", "")

        if not reason:
            return _error_response("validation_error", "Rejection reason is required")

        project = h["store"].load_project(project_id)
        if project.acceptance_package is None:
            return _error_response("validation_error", "No acceptance package to reject")

        project.acceptance_package.reject(decided_by=actor, note=reason)
        h["store"].save_project(project)

        h["journal"].append_raw(
            project_id=project_id,
            event_type="acceptance_rejected",
            event_summary=f"Acceptance rejected by {actor}: {reason}",
            actor=actor,
        )

        return {
            "ok": True,
            "message": f"Acceptance rejected — revision requested: {reason}",
        }
    except ObjectNotFoundError:
        return _error_response("project_not_found", f"Project '{input.get('project_id')}' not found")
    except Exception as e:
        return _error_response("unknown", f"Failed to reject acceptance: {e}")


# ---------------------------------------------------------------------------
# Maverick spawn tools
# ---------------------------------------------------------------------------

_maverick_spawner = None


def _get_maverick_spawner():
    """Get or create MaverickSpawner singleton."""
    global _maverick_spawner
    if _maverick_spawner is None:
        from gov_langgraph.openclaw_integration.maverick_spawner import MaverickSpawner
        _maverick_spawner = MaverickSpawner()
    return _maverick_spawner


def spawn_agent_tool(input: dict) -> dict:
    """
    Spawn a known agent for a task via MaverickSpawner.

    Agent and workflow definitions are loaded from config/agents.yaml.
    No hardcoded agent IDs or sequences.

    Args:
        input: {
            project_id: str,
            task_id: str,
            role: str (optional — defaults to current_stage),
        }
    Returns:
        {ok: bool, session_key: str, status: str, error: str | None}
    """
    try:
        h = _harness

        project_id = input["project_id"]
        task_id = input["task_id"]
        role = input.get("role")

        # Load project and task for context
        try:
            project = h["store"].load_project(project_id)
        except ObjectNotFoundError:
            return _error_response("project_not_found", f"Project '{project_id}' not found")

        try:
            task = h["store"].load_workitem(task_id)
        except ObjectNotFoundError:
            return _error_response("task_not_found", f"Task '{task_id}' not found")

        spawner = _get_maverick_spawner()
        result = spawner.schedule(
            project_name=project.project_name,
            project_id=project.project_id,
            task_title=task.task_title,
            task_id=task.task_id,
            current_stage=task.current_stage,
            role=role,
        )

        if result.ok:
            h["journal"].append_raw(
                project_id=project_id,
                event_type="agent_spawned",
                event_summary=f"Agent '{role or task.current_stage}' spawned for task '{task.task_title}'",
                actor="maverick",
                task_id=task_id,
            )

        return {
            "ok": result.ok,
            "session_key": result.session_key,
            "status": result.status,
            "error": result.error,
            "message": (
                f"Agent spawned: {role or task.current_stage}"
                if result.ok
                else f"Spawn failed: {result.error}"
            ),
        }
    except Exception as e:
        return _error_response("unknown", f"Failed to spawn agent: {e}")
