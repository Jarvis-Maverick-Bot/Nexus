# governance/cli/commands/inspect_cmd.py
# T9.2 — Universal inspect command
# Inspects items across all state domains: queue, task, work-item, escalation

import json
from typing import Optional


def inspect_item(item_id: str) -> dict:
    """
    Universal inspection across all state domains.

    Checks in order:
    1. Queue messages (governance/queue/data/messages.json)
    2. Tasks (governance/task/data/tasks.json)
    3. Work items (governance/cli/data/pmo_state.json)
    4. Escalations (governance/escalation/data/)

    Returns domain, type, state, and linked IDs where applicable.
    """
    # 1. Check queue messages
    msg = _inspect_queue(item_id)
    if msg:
        return msg

    # 2. Check tasks
    task = _inspect_task(item_id)
    if task:
        return task

    # 3. Check work items
    wi = _inspect_workitem(item_id)
    if wi:
        return wi

    # 4. Check escalations
    esc = _inspect_escalation(item_id)
    if esc:
        return esc

    return {"ok": False, "error": f"Item not found: {item_id}"}


def _read_json(path: str) -> Optional[dict]:
    """Read a JSON file, return None if missing or empty."""
    try:
        from pathlib import Path
        p = Path(path)
        if p.exists() and p.stat().st_size > 0:
            return json.loads(p.read_text())
        return None
    except Exception:
        return None


def _inspect_queue(item_id: str) -> Optional[dict]:
    from pathlib import Path
    # 4 levels: commands/ -> cli/ -> governance/ -> repo root
    base = Path(__file__).parent.parent.parent.parent
    data = _read_json(base / "governance" / "queue" / "data" / "messages.json")
    if not data:
        return None
    # messages.json may be a list directly or wrapped in {"messages": [...]}
    msgs = data if isinstance(data, list) else data.get("messages", [])
    for msg in msgs:
        if msg.get("message_id") == item_id or msg.get("id") == item_id:
            return {
                "ok": True,
                "domain": "queue",
                "type": "message",
                "item_id": item_id,
                "state": msg.get("state"),
                "sender": msg.get("sender"),
                "receiver": msg.get("receiver"),
                "message_type": msg.get("type"),
                "linked_response_id": msg.get("linked_response_id"),
                "created_at": msg.get("created_at"),
                "updated_at": msg.get("updated_at"),
            }
    return None


def _inspect_task(item_id: str) -> Optional[dict]:
    from pathlib import Path
    # 4 levels: commands/ -> cli/ -> governance/ -> repo root
    base = Path(__file__).parent.parent.parent.parent
    data = _read_json(base / "governance" / "task" / "data" / "tasks.json")
    if not data:
        return None
    # tasks.json may be a list directly or wrapped in {"tasks": [...]}
    tasks = data if isinstance(data, list) else data.get("tasks", [])
    for task in tasks:
        if task.get("task_id") == item_id or task.get("id") == item_id:
            return {
                "ok": True,
                "domain": "task",
                "type": task.get("task_type", "task"),
                "item_id": item_id,
                "state": task.get("state"),
                "assigned_to": task.get("assigned_to"),
                "owned_by": task.get("owned_by"),
                "created_at": task.get("created_at"),
                "updated_at": task.get("updated_at"),
            }
    return None


def _inspect_workitem(item_id: str) -> Optional[dict]:
    from pathlib import Path
    # 4 levels: commands/ -> cli/ -> governance/ -> repo root
    base = Path(__file__).parent.parent.parent.parent
    data = _read_json(base / "governance" / "cli" / "data" / "pmo_state.json")
    if not data or "items" not in data:
        return None
    if item_id in data.get("items", {}):
        wi = data["items"][item_id]
        return {
            "ok": True,
            "domain": "work-item",
            "type": "work_item",
            "item_id": item_id,
            "name": wi.get("name"),
            "stage": wi.get("stage"),
            "artifacts_count": len(wi.get("artifacts", [])),
            "validations_count": len(wi.get("validations", [])),
            "blockers_count": len(wi.get("blockers", [])),
            "active_blockers": [
                b for b in wi.get("blockers", []) if not b.get("resolved", False)
            ],
            "delivery_package": wi.get("delivery_package"),
            "created_at": wi.get("created_at"),
            "updated_at": wi.get("updated_at"),
        }
    return None


def _inspect_escalation(item_id: str) -> Optional[dict]:
    from pathlib import Path
    # 4 levels: commands/ -> cli/ -> governance/ -> repo root
    base = Path(__file__).parent.parent.parent.parent

    # Check JSON store first (if exists)
    esc_data = _read_json(base / "governance" / "escalation" / "data" / "escalations.json")
    dec_data = _read_json(base / "governance" / "escalation" / "data" / "decisions.json")

    # Check escalation records from JSON store
    if esc_data and "escalations" in esc_data:
        for rec in esc_data.get("escalations", []):
            if rec.get("escalation_id") == item_id or rec.get("id") == item_id:
                result = _build_escalation_result(rec, dec_data)
                if result:
                    return result

    # Fall back to evidence log (append-only, most up-to-date)
    evidence_path = base / "evidence" / "escalation"
    if evidence_path.exists():
        # Read all .jsonl files, parse all events
        for log_file in sorted(evidence_path.glob("*.jsonl")):
            try:
                content = log_file.read_text()
                for line in content.split("\n"):
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    after = event.get("after", {})
                    esc_id = after.get("escalation_id")
                    # Match by escalation_id OR by item_id (for items escalated by signal-blocker)
                    if (esc_id and esc_id == item_id) or (after.get("item_id") == item_id):
                        if event.get("event_type") == "escalation_create":
                            result = _build_escalation_result(after, dec_data)
                            if result:
                                return result
            except Exception:
                continue

    return None


def _build_escalation_result(rec: dict, dec_data: Optional[dict]) -> Optional[dict]:
    """Build escalation result dict from a record dict, optionally with linked decision."""
    if not rec:
        return None
    result = {
        "ok": True,
        "domain": "escalation",
        "type": "escalation_record",
        "item_id": rec.get("escalation_id") or rec.get("id"),
        "state": rec.get("state"),
        "item_ref": rec.get("item_id"),
        "reason": rec.get("reason"),
        "escalated_by": rec.get("escalated_by"),
        "escalated_at": rec.get("escalated_at"),
    }
    # Check for linked decision
    if dec_data and "decisions" in dec_data:
        esc_id = rec.get("escalation_id") or rec.get("id")
        for dec in dec_data.get("decisions", []):
            if dec.get("escalation_id") == esc_id:
                result["decision"] = {
                    "decision_id": dec.get("decision_id"),
                    "outcome": dec.get("outcome") or dec.get("decision"),
                    "decided_by": dec.get("decided_by"),
                    "decided_at": dec.get("decided_at"),
                    "note": dec.get("note"),
                }
                break
    return result