# governance/control/task_store.py
# Task execution state — separate from work-item governance state

import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

DATA_DIR = Path(__file__).parent.parent / "data"
TASK_STORE_FILE = DATA_DIR / "pmo_task_store.json"
TASK_LOG_FILE = DATA_DIR / "pmo_task_log.json"

# Task lifecycle states (R3 requirement)
LIFECYCLE_STATES = {
    "QUEUED", "DISPATCHED", "RUNNING", "WAITING",
    "SUCCEEDED", "FAILED", "CANCELED", "TIMED_OUT"
}


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_task_store():
    _ensure_data_dir()
    if TASK_STORE_FILE.exists():
        return json.loads(TASK_STORE_FILE.read_text())
    return {}


def _save_task_store(store):
    _ensure_data_dir()
    TASK_STORE_FILE.write_text(json.dumps(store, indent=2))


def _load_task_log():
    _ensure_data_dir()
    if TASK_LOG_FILE.exists():
        return json.loads(TASK_LOG_FILE.read_text())
    return []


def _save_task_log(log):
    _ensure_data_dir()
    TASK_LOG_FILE.write_text(json.dumps(log, indent=2))


def _log_action(task_id: str, action: str, actor: str, result: dict):
    log = _load_task_log()
    log.append({
        "task_id": task_id,
        "action": action,
        "actor": actor,
        "result": result,
        "at": _now(),
    })
    _save_task_log(log)
