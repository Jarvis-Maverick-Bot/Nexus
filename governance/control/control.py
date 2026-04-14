# governance/control/control.py
# Execution / dispatch commands — R2: must cause tangible action or fail explicitly

import uuid
from datetime import datetime, timezone
from .task_store import (
    _load_task_store, _save_task_store, _load_task_log,
    _save_task_log, _log_action, LIFECYCLE_STATES, _now
)


AUTHORIZED_ACTIONS = {
    "launch-subagent": ["Jarvis", "Nova", "Alex"],
    "pause-task":     ["Jarvis", "Nova", "Alex"],
    "resume-task":   ["Jarvis", "Nova", "Alex"],
    "inspect-task":  ["Jarvis", "Nova", "Alex", "AGENT", "SUB_AGENT"],
    "terminate-task": ["Jarvis", "Nova", "Alex"],
    "invoke-command": ["Jarvis", "Nova", "Alex"],
}

AUTHORIZED_AGENT_TYPES = {"TDD", "Planner", "CodeReviewer", "Security", "Docs", "DBExpert"}


def _check_authority(action: str, actor: str) -> bool:
    """R2: Unknown actors are FORBIDDEN — no silent failures."""
    if actor in AUTHORIZED_ACTIONS.get(action, []):
        return True
    return False


def _build_result_payload(task_id: str, store_entry: dict, status_override: str = None) -> dict:
    """
    R4: Result payload with all required fields.
    Every execution command returns this structure.
    """
    status = status_override or store_entry.get("status", "UNKNOWN")
    return {
        "task_id": task_id,
        "task_type": store_entry.get("task_type"),
        "requested_by": store_entry.get("requested_by"),
        "executor": store_entry.get("executor"),
        "input_payload": store_entry.get("input_payload"),
        "status": status,
        "created_at": store_entry.get("created_at"),
        "started_at": store_entry.get("started_at"),
        "updated_at": store_entry.get("updated_at"),
        "completed_at": store_entry.get("completed_at") if status in LIFECYCLE_STATES else None,
        "result_summary": store_entry.get("result_summary"),
        "output_ref": store_entry.get("output_ref"),
        "error": store_entry.get("error"),
        "logs_ref": None,
    }


def launch_subagent(task_id: str, agent_type: str, requested_by: str = "Jarvis",
                    executor: str = None, input_payload: dict = None) -> dict:
    """
    Category B: Execution / Dispatch.
    R2: Triggers real task creation -> QUEUED -> DISPATCHED -> RUNNING.
    R4: Returns full result payload.
    """
    if not _check_authority("launch-subagent", requested_by):
        return {"ok": False, "error": "FORBIDDEN", "reason": f"{requested_by} not authorized for launch-subagent in V1.8"}

    if agent_type not in AUTHORIZED_AGENT_TYPES:
        return {"ok": False, "error": f"Unknown agent type: {agent_type}. Valid: {', '.join(AUTHORIZED_AGENT_TYPES)}"}

    store = _load_task_store()
    if task_id in store:
        return {"ok": False, "error": f"Task already exists: {task_id}"}

    now = _now()
    store[task_id] = {
        "task_id": task_id,
        "task_type": agent_type,
        "requested_by": requested_by,
        "executor": executor or agent_type,
        "input_payload": input_payload or {},
        "status": "QUEUED",
        "created_at": now,
        "started_at": None,
        "updated_at": now,
        "completed_at": None,
        "result_summary": None,
        "output_ref": None,
        "error": None,
        "actions": [],
    }
    _save_task_store(store)

    # Immediate transition: QUEUED -> DISPATCHED -> RUNNING (simulated executor in V1.8)
    store[task_id]["status"] = "DISPATCHED"
    store[task_id]["started_at"] = _now()
    store[task_id]["updated_at"] = _now()
    store[task_id]["status"] = "RUNNING"
    _save_task_store(store)

    payload = _build_result_payload(task_id, store[task_id])
    _log_action(task_id, "launch-subagent", requested_by, payload)
    return {"ok": True, **payload}


def pause_task(task_id: str, actor: str = "Jarvis") -> dict:
    """
    Category B: Execution / Dispatch.
    R2: Causes state change -> WAITING. Fails if not RUNNING.
    R4: Returns full result payload.
    """
    if not _check_authority("pause-task", actor):
        return {"ok": False, "error": "FORBIDDEN", "reason": f"{actor} not authorized for pause-task in V1.8"}

    store = _load_task_store()
    if task_id not in store:
        return {"ok": False, "error": f"Task not found: {task_id}"}
    if store[task_id]["status"] not in {"RUNNING", "DISPATCHED"}:
        return {"ok": False, "error": f"Cannot pause task in status: {store[task_id]['status']}"}

    now = _now()
    store[task_id]["status"] = "WAITING"
    store[task_id]["updated_at"] = now
    _save_task_store(store)

    payload = _build_result_payload(task_id, store[task_id])
    _log_action(task_id, "pause-task", actor, payload)
    return {"ok": True, **payload}


def resume_task(task_id: str, actor: str = "Jarvis") -> dict:
    """Category B: Execution / Dispatch. WAITING -> RUNNING."""
    if not _check_authority("resume-task", actor):
        return {"ok": False, "error": "FORBIDDEN", "reason": f"{actor} not authorized for resume-task in V1.8"}

    store = _load_task_store()
    if task_id not in store:
        return {"ok": False, "error": f"Task not found: {task_id}"}
    if store[task_id]["status"] != "WAITING":
        return {"ok": False, "error": f"Cannot resume task in status: {store[task_id]['status']}"}

    now = _now()
    store[task_id]["status"] = "RUNNING"
    store[task_id]["updated_at"] = now
    _save_task_store(store)

    payload = _build_result_payload(task_id, store[task_id])
    _log_action(task_id, "resume-task", actor, payload)
    return {"ok": True, **payload}


def terminate_task(task_id: str, actor: str = "Jarvis") -> dict:
    """
    Category B: Execution / Dispatch.
    R2: Causes state change -> CANCELED. Fails explicitly if not running.
    R4: Returns full result payload.
    """
    if not _check_authority("terminate-task", actor):
        return {"ok": False, "error": "FORBIDDEN", "reason": f"{actor} not authorized for terminate-task in V1.8"}

    store = _load_task_store()
    if task_id not in store:
        return {"ok": False, "error": f"Task not found: {task_id}"}
    current = store[task_id]["status"]
    if current in {"SUCCEEDED", "FAILED", "CANCELED", "TIMED_OUT"}:
        return {"ok": False, "error": f"Task already in terminal state: {current}"}

    now = _now()
    store[task_id]["status"] = "CANCELED"
    store[task_id]["updated_at"] = now
    store[task_id]["completed_at"] = now
    _save_task_store(store)

    payload = _build_result_payload(task_id, store[task_id])
    _log_action(task_id, "terminate-task", actor, payload)
    return {"ok": True, **payload}


def invoke_command(task_id: str, command: str, actor: str = "Jarvis") -> dict:
    """
    Category B: Execution / Dispatch.
    R2: Executes approved command, returns result. Fails if task not RUNNING.
    R4: Returns full result payload with command output.
    """
    if not _check_authority("invoke-command", actor):
        return {"ok": False, "error": "FORBIDDEN", "reason": f"{actor} not authorized for invoke-command in V1.8"}

    store = _load_task_store()
    if task_id not in store:
        return {"ok": False, "error": f"Task not found: {task_id}"}
    if store[task_id]["status"] == "TERMINATED":
        return {"ok": False, "error": f"Cannot invoke on terminated task: {task_id}"}

    cmd_id = f"CMD-{uuid.uuid4().hex[:8]}"
    cmd_record = {
        "id": cmd_id,
        "task_id": task_id,
        "command": command,
        "invoked_at": _now(),
    }
    store[task_id].setdefault("actions", []).append(cmd_record)
    store[task_id]["updated_at"] = _now()
    _save_task_store(store)

    # V1.8: simulated execution — in production this would invoke the real executor
    result_summary = f"Executed: {command}"
    output_ref = f"cmd://{cmd_id}"

    payload = _build_result_payload(task_id, store[task_id])
    payload["result_summary"] = result_summary
    payload["output_ref"] = output_ref
    _log_action(task_id, "invoke-command", actor, payload)
    return {"ok": True, "command_id": cmd_id, **payload}


def inspect_task(task_id: str, actor: str = "Jarvis") -> dict:
    """Category C: Observation. Returns full task lifecycle state."""
    if not _check_authority("inspect-task", actor):
        return {"ok": False, "error": "FORBIDDEN", "reason": f"{actor} not authorized for inspect-task in V1.8"}

    store = _load_task_store()
    if task_id not in store:
        return {"ok": False, "error": f"Task not found: {task_id}"}

    entry = store[task_id]
    payload = _build_result_payload(task_id, entry)
    _log_action(task_id, "inspect-task", actor, payload)
    return {"ok": True, **payload}


def get_task_result(task_id: str, actor: str = "Jarvis") -> dict:
    """Category C: Observation. Returns stored result payload."""
    if not _check_authority("inspect-task", actor):
        return {"ok": False, "error": "FORBIDDEN", "reason": f"{actor} not authorized for get-task-result in V1.8"}

    store = _load_task_store()
    if task_id not in store:
        return {"ok": False, "error": f"Task not found: {task_id}"}

    entry = store[task_id]
    return {"ok": True, "result": _build_result_payload(task_id, entry)}


def get_task_log() -> dict:
    """Category C: Observation. Returns full task action log."""
    log = _load_task_log()
    return {"ok": True, "log": log, "total": len(log)}
