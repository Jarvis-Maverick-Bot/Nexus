"""
openclaw_integration.coordinator — Jarvis coordinates Telegram → Tool → Result

Maps Telegram commands to tool calls.
Formats structured dict results for Telegram output.
Handles errors gracefully.
"""

from __future__ import annotations

from typing import Any

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


# ---------------------------------------------------------------------------
# Command router
# ---------------------------------------------------------------------------

# Maps Telegram command text to tool function + required fields
_COMMAND_MAP: dict[str, tuple[Any, list[str]]] = {
    "create_project": (create_project_tool, ["project_name"]),
    "create_task": (create_task_tool, ["task_title", "project_id"]),
    "advance_stage": (advance_stage_tool, ["task_id", "actor"]),
    "submit_handoff": (submit_handoff_tool, ["task_id", "from_owner", "to_owner", "actor"]),
    "approve_gate": (approve_gate_tool, ["task_id", "gate_name", "actor"]),
    "reject_gate": (reject_gate_tool, ["task_id", "gate_name", "actor"]),
    "get_status": (get_status_tool, ["task_id"]),
    "list_tasks": (list_tasks_tool, ["project_id"]),
}


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------


class Coordinator:
    """
    Jarvis coordinates Telegram messages to tool calls.

    On init: initializes harness layer.
    On message: routes to appropriate tool, formats result for Telegram.
    """

    def __init__(self):
        self.harness = init_harness()

    def handle(self, command: str, args: dict) -> dict:
        """
        Route a Telegram command + args to the appropriate tool.

        Args:
            command: command name (e.g. "create_project")
            args: dict of arguments from Telegram

        Returns:
            Telegram-formatted string or dict for the channel
        """
        if command not in _COMMAND_MAP:
            return {
                "ok": False,
                "message": f"Unknown command: '{command}'. "
                           f"Available: {', '.join(_COMMAND_MAP.keys())}",
            }

        tool_fn, required_fields = _COMMAND_MAP[command]

        # Check required fields
        missing = [f for f in required_fields if f not in args]
        if missing:
            return {
                "ok": False,
                "message": f"Missing required fields for '{command}': {', '.join(missing)}",
            }

        # Call tool
        result = tool_fn(args)

        # Format for Telegram
        return self._format_for_telegram(command, result)

    def _format_for_telegram(self, command: str, result: dict) -> dict:
        """
        Format tool result as a Telegram-ready message.

        Returns a dict with at minimum {ok, message}.
        """
        if not result.get("ok", False):
            return {
                "ok": False,
                "message": f"❌ {result.get('message', 'Unknown error')}",
            }

        # Format success message based on command
        if command == "create_project":
            msg = f"✅ Project created: `{result['project_name']}`\nID: `{result['project_id']}`"
        elif command == "create_task":
            msg = f"✅ Task created: `{result['task_title']}`\nStage: `{result['current_stage']}`\nID: `{result['task_id']}`"
        elif command == "advance_stage":
            msg = f"✅ Advanced: `{result['from_stage']}` → `{result['to_stage']}`\nTask: `{result['task_id'][:8]}`"
        elif command == "submit_handoff":
            msg = f"✅ Handoff to `{result['to_owner']}`\nTask: `{result['task_id'][:8]}`"
        elif command == "approve_gate":
            msg = f"✅ Gate approved at stage `{result['stage']}`\nTask: `{result['task_id'][:8]}`"
        elif command == "reject_gate":
            msg = f"❌ Gate rejected at stage `{result['stage']}`\nTask: `{result['task_id'][:8]}`"
        elif command == "get_status":
            msg = self._format_status(result)
        elif command == "list_tasks":
            msg = self._format_task_list(result)
        else:
            msg = result.get("message", "Done")
        return {"ok": True, "message": msg, "data": result}

    def _format_status(self, result: dict) -> str:
        blocker = ""
        if result.get("current_blocker"):
            blocker = f"\n⚠️ Blocked: {result['current_blocker']}"
        return (
            f"📋 *{result['task_title']}*\n"
            f"Stage: `{result['current_stage']}` | "
            f"Status: `{result['task_status']}` | "
            f"Owner: `{result['current_owner']}`"
            f"{blocker}"
        )

    def _format_task_list(self, result: dict) -> str:
        tasks = result.get("tasks", [])
        if not tasks:
            return "No tasks found."
        lines = [f"📋 *{result['count']} task(s) in project:*"]
        for t in tasks:
            lines.append(
                f"  [`{t['current_stage']}`] {t['task_title']} "
                f"| {t['task_status']} | owner={t['current_owner']}"
            )
        return "\n".join(lines)
