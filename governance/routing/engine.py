# governance/routing/engine.py
# PMO Event Routing — intake, determine, route, resolve, relay

import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

DATA_DIR = Path(__file__).parent.parent / "data"
EVENT_LOG_FILE = DATA_DIR / "pmo_event_log.json"


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_event_log():
    _ensure_data_dir()
    if EVENT_LOG_FILE.exists():
        return json.loads(EVENT_LOG_FILE.read_text())
    return []


def _save_event_log(log):
    _ensure_data_dir()
    EVENT_LOG_FILE.write_text(json.dumps(log, indent=2))


# Routing rules — V1.8 deterministic set
ROUTING_RULES = {
    "UNKNOWN_TOOL": "AGENT",
    "BLOCKER_ESCALATION": "PMO",
    "CLARIFICATION_NEEDED": "NOVA",
    "TASK_COMPLETE": "PMO",
    "TASK_FAILED": "PMO",
    "DELIVERY_REQUEST": "PMO",
}


def route_event(event_json: str) -> dict:
    """
    Accept a routing request, determine destination, forward, log.
    Returns FORWARDED with destination. Relay to initiator is scoped to V1.8.
    """
    try:
        event = json.loads(event_json)
    except json.JSONDecodeError:
        return {"ok": False, "error": "Invalid JSON"}

    event_type = event.get("type", "UNKNOWN")
    context = event.get("context", {})
    initiator = event.get("initiator", "unknown")
    payload = event.get("payload", {})

    event_id = f"EVT-{uuid.uuid4().hex[:8]}"
    determined_destination = ROUTING_RULES.get(event_type, "PMO")
    timestamp = _now()

    routing_record = {
        "event_id": event_id,
        "type": event_type,
        "initiator": initiator,
        "context": context,
        "payload": payload,
        "determined_destination": determined_destination,
        "status": "FORWARDED",
        "forwarded_at": timestamp,
    }

    log = _load_event_log()
    log.append(routing_record)
    _save_event_log(log)

    return {
        "ok": True,
        "event_id": event_id,
        "status": "FORWARDED",
        "destination": determined_destination,
        "at": timestamp,
    }


def get_event_log(event_id: str | None = None) -> dict:
    """Return full event log or single event."""
    log = _load_event_log()
    if event_id:
        for entry in log:
            if entry["event_id"] == event_id:
                return {"ok": True, "event": entry}
        return {"ok": False, "error": f"Event not found: {event_id}"}
    return {"ok": True, "events": log, "total": len(log)}
