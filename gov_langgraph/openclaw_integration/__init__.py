"""
openclaw_integration — OpenClaw tool definitions and coordinator

tools.py   — @tool functions (create_project, create_task, advance_stage, etc.)
coordinator.py — Jarvis routes Telegram commands to tools, formats responses
"""

from .tools import (
    init_harness,
    create_project_tool,
    create_task_tool,
    advance_stage_tool,
    submit_handoff_tool,
    approve_gate_tool,
    reject_gate_tool,
    get_status_tool,
    list_tasks_tool,
)
from .coordinator import Coordinator

__all__ = [
    "init_harness",
    "create_project_tool",
    "create_task_tool",
    "advance_stage_tool",
    "submit_handoff_tool",
    "approve_gate_tool",
    "reject_gate_tool",
    "get_status_tool",
    "list_tasks_tool",
    "Coordinator",
]
