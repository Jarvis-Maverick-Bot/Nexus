"""
governance/queue/store.py
V1.9 Sprint 1, Task T1.2
JSON-backed persistent queue store.

Implements governance/queue/data/messages.json as the persistent store.
Survives CLI restart. Async write semantics.
"""

import json
import os
import threading
from pathlib import Path
from typing import List, Optional

from .models import Message


DATA_DIR = Path(__file__).parent / "data"
MESSAGES_FILE = DATA_DIR / "messages.json"

_lock = threading.RLock()


def _ensure_data_dir() -> None:
    """Ensure the data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read_raw() -> List[dict]:
    """Read raw JSON list from messages.json. Returns [] if file missing."""
    _ensure_data_dir()
    if not MESSAGES_FILE.exists():
        return []
    with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_raw(data: List[dict]) -> None:
    """Write raw JSON list to messages.json atomically."""
    _ensure_data_dir()
    # Write to temp file then rename for atomicity
    tmp = MESSAGES_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(MESSAGES_FILE)


class QueueStore:
    """
    Thread-safe JSON-backed message queue store.

    Messages are stored as a JSON list in messages.json.
    The store provides add, get, update, list, and filter operations.
    """

    def __init__(self) -> None:
        _ensure_data_dir()

    def add(self, message: Message) -> None:
        """Add a message to the store."""
        with _lock:
            data = _read_raw()
            data.append(message.to_dict())
            _write_raw(data)

    def get(self, message_id: str) -> Optional[Message]:
        """Retrieve a message by message_id. Returns None if not found."""
        with _lock:
            data = _read_raw()
            for item in data:
                if item["message_id"] == message_id:
                    return Message.from_dict(item)
            return None

    def update(self, message: Message) -> None:
        """Update an existing message in the store."""
        with _lock:
            data = _read_raw()
            for i, item in enumerate(data):
                if item["message_id"] == message.message_id:
                    data[i] = message.to_dict()
                    _write_raw(data)
                    return
            raise KeyError(f"Message {message.message_id} not found in store")

    def delete(self, message_id: str) -> bool:
        """Delete a message by message_id. Returns True if deleted, False if not found."""
        with _lock:
            data = _read_raw()
            before = len(data)
            data = [item for item in data if item["message_id"] != message_id]
            if len(data) == before:
                return False
            _write_raw(data)
            return True

    def list_all(self) -> List[Message]:
        """List all messages in the store."""
        with _lock:
            data = _read_raw()
            return [Message.from_dict(item) for item in data]

    def list_by_state(self, state: str) -> List[Message]:
        """List all messages in a specific state."""
        with _lock:
            data = _read_raw()
            return [Message.from_dict(item) for item in data if item["state"] == state]

    def list_by_receiver(self, receiver: str) -> List[Message]:
        """List all messages for a specific receiver."""
        with _lock:
            data = _read_raw()
            return [Message.from_dict(item) for item in data if item["receiver"] == receiver]

    def count(self) -> int:
        """Return total message count."""
        with _lock:
            return len(_read_raw())

    def clear(self) -> None:
        """Clear all messages. Use with caution."""
        with _lock:
            _write_raw([])


# Default store instance
_default_store: Optional[QueueStore] = None


def get_store() -> QueueStore:
    """Get the default store instance (singleton)."""
    global _default_store
    if _default_store is None:
        _default_store = QueueStore()
    return _default_store