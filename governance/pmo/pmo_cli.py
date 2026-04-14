"""PMO Smart Agent — State store and CLI for V1.8 delivery management."""

import json
import os
import sys
import uuid
from pathlib import Path
from datetime import datetime, timezone


DATA_DIR = Path(__file__).parent / "data"
STATE_FILE = DATA_DIR / "pmo_state.json"


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_state():
    _ensure_data_dir()
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"items": {}, "sequences": {"work_item": 0}}


def _save_state(state):
    _ensure_data_dir()
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ─── Commands ────────────────────────────────────────────────────────────────


def create_work_item(name: str) -> dict:
    state = _load_state()
    state["sequences"]["work_item"] += 1
    seq = state["sequences"]["work_item"]
    item_id = f"WI-{seq:03d}"
    item = {
        "id": item_id,
        "name": name,
        "stage": "BACKLOG",
        "created_at": _now(),
        "updated_at": _now(),
        "artifacts": [],
        "validations": [],
        "blockers": [],
        "transitions": [],
        "delivery_package": None,
    }
    state["items"][item_id] = item
    _save_state(state)
    return {"ok": True, "item_id": item_id, "name": name, "stage": "BACKLOG"}


def submit_artifact(item_id: str, path: str) -> dict:
    state = _load_state()
    if item_id not in state["items"]:
        return {"ok": False, "error": f"Item not found: {item_id}"}
    p = Path(path)
    if not p.exists():
        return {"ok": False, "error": f"Artifact path does not exist: {path}"}
    artifact = {
        "id": f"ART-{uuid.uuid4().hex[:8]}",
        "item_id": item_id,
        "path": str(p.resolve()),
        "name": p.name,
        "submitted_at": _now(),
    }
    state["items"][item_id]["artifacts"].append(artifact)
    state["items"][item_id]["updated_at"] = _now()
    _save_state(state)
    return {
        "ok": True,
        "artifact_id": artifact["id"],
        "item_id": item_id,
        "path": artifact["path"],
    }


def request_transition(item_id: str, stage: str) -> dict:
    state = _load_state()
    if item_id not in state["items"]:
        return {"ok": False, "error": f"Item not found: {item_id}"}
    valid_stages = ["BACKLOG", "IN_PROGRESS", "IN_REVIEW", "APPROVED", "DELIVERED"]
    if stage not in valid_stages:
        return {"ok": False, "error": f"Invalid stage. Valid: {', '.join(valid_stages)}"}
    item = state["items"][item_id]
    old_stage = item["stage"]
    item["stage"] = stage
    item["transitions"].append({
        "from": old_stage,
        "to": stage,
        "at": _now(),
    })
    item["updated_at"] = _now()
    _save_state(state)
    return {"ok": True, "item_id": item_id, "from": old_stage, "to": stage}


def record_validation(item_id: str, result: str) -> dict:
    state = _load_state()
    if item_id not in state["items"]:
        return {"ok": False, "error": f"Item not found: {item_id}"}
    valid_results = ["PASS", "FAIL", "PENDING"]
    if result not in valid_results:
        return {"ok": False, "error": f"Invalid result. Valid: {', '.join(valid_results)}"}
    validation = {
        "id": f"VAL-{uuid.uuid4().hex[:8]}",
        "item_id": item_id,
        "result": result,
        "recorded_at": _now(),
    }
    state["items"][item_id]["validations"].append(validation)
    state["items"][item_id]["updated_at"] = _now()
    _save_state(state)
    return {"ok": True, "validation_id": validation["id"], "item_id": item_id, "result": result}


def signal_blocker(item_id: str, desc: str) -> dict:
    state = _load_state()
    if item_id not in state["items"]:
        return {"ok": False, "error": f"Item not found: {item_id}"}
    blocker = {
        "id": f"BLK-{uuid.uuid4().hex[:8]}",
        "item_id": item_id,
        "description": desc,
        "signaled_at": _now(),
        "resolved": False,
    }
    state["items"][item_id]["blockers"].append(blocker)
    state["items"][item_id]["updated_at"] = _now()
    _save_state(state)
    return {"ok": True, "blocker_id": blocker["id"], "item_id": item_id, "description": desc}


def package_delivery(item_id: str) -> dict:
    state = _load_state()
    if item_id not in state["items"]:
        return {"ok": False, "error": f"Item not found: {item_id}"}
    item = state["items"][item_id]
    pkg_id = f"PKG-{uuid.uuid4().hex[:8]}"
    package = {
        "id": pkg_id,
        "item_id": item_id,
        "name": item["name"],
        "stage": item["stage"],
        "artifacts": [a["id"] for a in item["artifacts"]],
        "validations": [v["id"] for v in item["validations"]],
        "blockers": [b["id"] for b in item["blockers"] if not b["resolved"]],
        "created_at": _now(),
    }
    item["delivery_package"] = package
    item["updated_at"] = _now()
    _save_state(state)
    return {"ok": True, "package_id": pkg_id, "item_id": item_id, "stage": item["stage"]}


def status(item_id: str | None = None) -> dict:
    state = _load_state()
    if item_id:
        if item_id not in state["items"]:
            return {"ok": False, "error": f"Item not found: {item_id}"}
        return {"ok": True, "item": state["items"][item_id]}
    return {"ok": True, "items": list(state["items"].values()), "total": len(state["items"])}


# ─── CLI entry point ─────────────────────────────────────────────────────────


COMMANDS = {
    "create-work-item": (create_work_item, "<name>"),
    "submit-artifact": (submit_artifact, "<item_id> <path>"),
    "request-transition": (request_transition, "<item_id> <stage>"),
    "record-validation": (record_validation, "<item_id> <result>"),
    "signal-blocker": (signal_blocker, "<item_id> <description>"),
    "package-delivery": (package_delivery, "<item_id>"),
    "status": (status, "[item_id]"),
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] == "--help" or sys.argv[1] == "-h":
        print("PMO CLI — V1.8 Delivery Management")
        print()
        for cmd, (_, usage) in COMMANDS.items():
            print(f"  pmo {cmd} {usage}")
        print()
        print("  pmo --help   Show this message")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        print(f"ERROR: Unknown command '{cmd}'")
        print(f"Valid: {', '.join(COMMANDS)}")
        sys.exit(1)

    fn, usage = COMMANDS[cmd]
    args = sys.argv[2:]

    if cmd == "create-work-item":
        if len(args) < 1:
            print(f"EXPECTED: {usage}")
            sys.exit(1)
        result = fn(args[0])
    elif cmd == "submit-artifact":
        if len(args) < 2:
            print(f"EXPECTED: {usage}")
            sys.exit(1)
        result = fn(args[0], args[1])
    elif cmd == "request-transition":
        if len(args) < 2:
            print(f"EXPECTED: {usage}")
            sys.exit(1)
        result = fn(args[0], args[1])
    elif cmd == "record-validation":
        if len(args) < 2:
            print(f"EXPECTED: {usage}")
            sys.exit(1)
        result = fn(args[0], args[1])
    elif cmd == "signal-blocker":
        if len(args) < 2:
            print(f"EXPECTED: {usage}")
            sys.exit(1)
        result = fn(args[0], " ".join(args[1:]))
    elif cmd == "package-delivery":
        if len(args) < 1:
            print(f"EXPECTED: {usage}")
            sys.exit(1)
        result = fn(args[0])
    elif cmd == "status":
        result = fn(args[0] if args else None)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
