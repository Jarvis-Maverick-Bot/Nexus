"""
openclaw_integration — OpenClaw tool definitions and coordinator

tools.py   — @tool functions (create_project, create_task, advance_stage, etc.)
coordinator.py — Jarvis routes Telegram commands to tools, formats responses
"""

from .tools import (
    init_harness,
    create_project_tool,
    create_task_tool,
    kickoff_task_tool,
    advance_stage_tool,
    submit_handoff_tool,
    approve_gate_tool,
    reject_gate_tool,
    get_status_tool,
    get_gate_panel_tool,
    list_tasks_tool,
    get_project_tool,
    list_projects_tool,
    upsert_artifact_tool,
    get_artifacts_tool,
    create_acceptance_package_tool,
    get_acceptance_package_tool,
    approve_acceptance_tool,
    reject_acceptance_tool,
    get_advisories_tool,
    raise_advisory_tool,
    acknowledge_advisory_tool,
    get_blockers_tool,
    raise_blocker_tool,
    resolve_blocker_tool,
    spawn_agent_tool,
)
from .coordinator import Coordinator

__all__ = [
    "init_harness",
    "create_project_tool",
    "create_task_tool",
    "kickoff_task_tool",
    "advance_stage_tool",
    "submit_handoff_tool",
    "approve_gate_tool",
    "reject_gate_tool",
    "get_status_tool",
    "get_gate_panel_tool",
    "list_tasks_tool",
    "get_project_tool",
    "list_projects_tool",
    "upsert_artifact_tool",
    "get_artifacts_tool",
    "create_acceptance_package_tool",
    "get_acceptance_package_tool",
    "approve_acceptance_tool",
    "reject_acceptance_tool",
    "get_advisories_tool",
    "raise_advisory_tool",
    "acknowledge_advisory_tool",
    "get_blockers_tool",
    "raise_blocker_tool",
    "resolve_blocker_tool",
    "spawn_agent_tool",
    "Coordinator",
]
