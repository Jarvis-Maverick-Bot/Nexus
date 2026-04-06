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
    get_v1_pipeline_workflow,
)
from gov_langgraph.platform_model.state_machine import StateMachine
from gov_langgraph.platform_model.authority import Action, check_authority
from gov_langgraph.langgraph_engine import init_runtime, run_workitem as langgraph_run_workitem


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
        try:
            ts = h["store"].load_taskstate(task_id)
            ts.current_stage = target_stage
            h["store"].save_taskstate(ts)
        except Exception:
            pass

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
    Approve a gate for a task.

    Args:
        input: {
            task_id: str,
            gate_name: str,
            actor: str,
            notes: str (optional),
        }
    Returns:
        {ok: bool, gate_id: str, message: str}
    """
    try:
        h = _harness
        task_id = input["task_id"]
        gate_name = input.get("gate_name", "DEFAULT")
        actor = input.get("actor", "unknown")
        notes = input.get("notes", "")

        workitem = h["store"].load_workitem(task_id)
        gate = Gate(
            task_id=task_id,
            stage=workitem.current_stage,
            gate_type="approval",
            decision=GateDecision.APPROVED,
            decision_by=actor,
            decision_note=notes,
        )
        h["store"].save_gate(gate)

        h["journal"].append_raw(
            project_id=workitem.project_id,
            event_type="gate_approved",
            event_summary=f"Gate '{gate_name}' approved for task '{task_id}'",
            actor=actor,
            task_id=task_id,
            related_stage=workitem.current_stage,
        )

        return {
            "ok": True,
            "gate_id": gate.gate_id,
            "gate_type": gate.gate_type,
            "stage": gate.stage,
            "task_id": task_id,
            "message": f"Gate approved at stage '{gate.stage}'",
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "message": f"Failed to approve gate: {e}"}


def reject_gate_tool(input: dict) -> dict:
    """
    Reject a gate for a task.

    Args:
        input: {
            task_id: str,
            gate_name: str,
            actor: str,
            notes: str (optional),
        }
    Returns:
        {ok: bool, gate_id: str, message: str}
    """
    try:
        h = _harness
        task_id = input["task_id"]
        gate_name = input.get("gate_name", "DEFAULT")
        actor = input.get("actor", "unknown")
        notes = input.get("notes", "")

        workitem = h["store"].load_workitem(task_id)
        gate = Gate(
            task_id=task_id,
            stage=workitem.current_stage,
            gate_type="approval",
            decision=GateDecision.REJECTED,
            decision_by=actor,
            decision_note=notes,
        )
        h["store"].save_gate(gate)

        h["journal"].append_raw(
            project_id=workitem.project_id,
            event_type="gate_rejected",
            event_summary=f"Gate '{gate_name}' rejected for task '{task_id}'",
            actor=actor,
            task_id=task_id,
            related_stage=workitem.current_stage,
        )

        return {
            "ok": True,
            "gate_id": gate.gate_id,
            "gate_type": gate.gate_type,
            "stage": gate.stage,
            "task_id": task_id,
            "message": f"Gate rejected at stage '{gate.stage}'",
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "message": f"Failed to reject gate: {e}"}


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
    except Exception as e:
        return {"ok": False, "error": str(e), "message": f"Failed to get status: {e}"}


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
    except Exception as e:
        return {"ok": False, "error": str(e), "message": f"Failed to list tasks: {e}"}
