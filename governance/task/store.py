"""
governance/task/store.py
V1.9 Sprint 1, Task T2.2
JSON-backed persistent task store.

Location: governance/task/data/tasks.json
Thread-safe, survives CLI restart.
"""

import json
import threading
from pathlib import Path
from typing import List, Optional

from .models import Task, TaskLifecycleState


DATA_DIR = Path(__file__).parent / "data"
TASKS_FILE = DATA_DIR / "tasks.json"

_lock = threading.RLock()


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read_raw() -> List[dict]:
    _ensure_data_dir()
    if not TASKS_FILE.exists():
        return []
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_raw(data: List[dict]) -> None:
    _ensure_data_dir()
    tmp = TASKS_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(TASKS_FILE)


class TaskStore:
    """Thread-safe JSON-backed task store."""

    def __init__(self) -> None:
        _ensure_data_dir()

    def add(self, task: Task) -> None:
        with _lock:
            data = _read_raw()
            data.append(task.to_dict())
            _write_raw(data)

    def get(self, task_id: str) -> Optional[Task]:
        with _lock:
            data = _read_raw()
            for item in data:
                if item["task_id"] == task_id:
                    return Task.from_dict(item)
            return None

    def update(self, task: Task) -> None:
        with _lock:
            data = _read_raw()
            for i, item in enumerate(data):
                if item["task_id"] == task.task_id:
                    data[i] = task.to_dict()
                    _write_raw(data)
                    return
            raise KeyError(f"Task {task.task_id} not found")

    def delete(self, task_id: str) -> bool:
        with _lock:
            data = _read_raw()
            before = len(data)
            data = [item for item in data if item["task_id"] != task_id]
            if len(data) == before:
                return False
            _write_raw(data)
            return True

    def list_all(self) -> List[Task]:
        with _lock:
            data = _read_raw()
            return [Task.from_dict(item) for item in data]

    def list_by_state(self, state: str) -> List[Task]:
        with _lock:
            data = _read_raw()
            return [Task.from_dict(item) for item in data if item["lifecycle_state"] == state]

    def list_by_executor(self, executor: str) -> List[Task]:
        with _lock:
            data = _read_raw()
            return [Task.from_dict(item) for item in data if item["assigned_executor"] == executor]

    def count(self) -> int:
        with _lock:
            return len(_read_raw())

    def clear(self) -> None:
        with _lock:
            _write_raw([])


_default_store: Optional[TaskStore] = None


def get_task_store() -> TaskStore:
    global _default_store
    if _default_store is None:
        _default_store = TaskStore()
    return _default_store