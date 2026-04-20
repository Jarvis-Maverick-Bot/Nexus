"""
NATS Collaboration Mechanism - Durable State Store
Stores collaboration state as JSON, append-only message log as JSONL
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict


# ── Configurable data directory via environment variable ───────────────
# If COLLAB_DATA_DIR is set, use it. Otherwise compute from file location.
# This file is at: .../collab_module/state_store.py
# Repo root is: .../collab_module/../  (3 levels up from collab_module/)
_COLLAB_DATA_DIR = os.environ.get(
    "COLLAB_DATA_DIR",
    None  # default to computed relative path
)

if _COLLAB_DATA_DIR:
    _DATA_DIR = _COLLAB_DATA_DIR
else:
    # Compute relative to this file: collab_module/state_store.py -> repo root
    _REPO_ROOT = Path(__file__).parent.parent
    _DATA_DIR = str(_REPO_ROOT / "governance" / "data")

STATE_FILE = os.path.join(_DATA_DIR, "collab_state.json")
MESSAGE_LOG_FILE = os.path.join(_DATA_DIR, "collab_messages.jsonl")


@dataclass
class CollabState:
    """Single collaboration session state."""
    collab_id: str
    status: str = "open"  # open | in_progress | completed | exited | blocked
    artifact_type: Optional[str] = None
    artifact_path: Optional[str] = None
    opened_by: str = ""
    current_owner: str = ""
    last_message_id: str = ""
    last_acknowledged_message_id: str = ""
    last_event: str = ""
    pending_action: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'CollabState':
        return cls(**d)


class CollabStateStore:
    """Durable collaboration state store with file locking."""

    def __init__(self, state_file: str = STATE_FILE, log_file: str = MESSAGE_LOG_FILE):
        self.state_file = Path(state_file)
        self.log_file = Path(log_file)
        self._ensure_data_dir()

    def _ensure_data_dir(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.state_file.exists():
            self._write_state({})

    def _read_state(self) -> Dict[str, Any]:
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _write_state(self, data: Dict[str, Any]):
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _append_log(self, entry: dict):
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    # ── Collaboration CRUD ──────────────────────────────────────────

    def get_collab(self, collab_id: str) -> Optional[CollabState]:
        """Get a collaboration by ID."""
        data = self._read_state()
        if collab_id in data:
            return CollabState.from_dict(data[collab_id])
        return None

    def open_collab(self, collab_id: str, opened_by: str,
                    artifact_type: Optional[str] = None,
                    artifact_path: Optional[str] = None) -> CollabState:
        """Open a new collaboration."""
        data = self._read_state()
        now = datetime.now(timezone.utc).isoformat()
        state = CollabState(
            collab_id=collab_id,
            status='open',
            artifact_type=artifact_type,
            artifact_path=artifact_path,
            opened_by=opened_by,
            current_owner=opened_by,
            created_at=now,
            updated_at=now
        )
        data[collab_id] = state.to_dict()
        self._write_state(data)
        self._append_log({
            "event": "collab_opened",
            "collab_id": collab_id,
            "opened_by": opened_by,
            "timestamp": now
        })
        return state

    def update_collab(self, collab_id: str, **kwargs) -> Optional[CollabState]:
        """Update collaboration fields."""
        data = self._read_state()
        if collab_id not in data:
            return None
        state = CollabState.from_dict(data[collab_id])
        for key, value in kwargs.items():
            if hasattr(state, key):
                setattr(state, key, value)
        state.updated_at = datetime.now(timezone.utc).isoformat()
        data[collab_id] = state.to_dict()
        self._write_state(data)
        return state

    def close_collab(self, collab_id: str) -> Optional[CollabState]:
        """Close a collaboration."""
        return self.update_collab(collab_id, status='completed')

    def list_collabs(self, status: Optional[str] = None) -> List[CollabState]:
        """List all collaborations, optionally filtered by status."""
        data = self._read_state()
        collabs = [CollabState.from_dict(d) for d in data.values()]
        if status:
            collabs = [c for c in collabs if c.status == status]
        return collabs

    # ── Message Logging ─────────────────────────────────────────────

    def log_message(self, envelope: dict, direction: str):
        """Append a message to the durable log."""
        self._append_log({
            "direction": direction,
            "collab_id": envelope.get('collab_id'),
            "message_id": envelope.get('message_id'),
            "message_type": envelope.get('message_type'),
            "from": envelope.get('from'),
            "to": envelope.get('to'),
            "summary": envelope.get('summary', ''),
            "timestamp": envelope.get('timestamp'),
            "full_envelope": envelope
        })

    def get_messages(self, collab_id: str, direction: Optional[str] = None) -> List[dict]:
        """Get all logged messages for a collab."""
        messages = []
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    entry = json.loads(line.strip())
                    if entry.get('collab_id') == collab_id:
                        if direction is None or entry.get('direction') == direction:
                            messages.append(entry)
        except FileNotFoundError:
            pass
        return messages

    # ── Convenience ────────────────────────────────────────────────

    def get_or_create_collab(self, collab_id: str, opened_by: str,
                             artifact_type: Optional[str] = None,
                             artifact_path: Optional[str] = None) -> CollabState:
        existing = self.get_collab(collab_id)
        if existing:
            return existing
        return self.open_collab(collab_id, opened_by, artifact_type, artifact_path)

    def emit_event(self, collab_id: str, event: str, **extra):
        """Log a workflow event."""
        data = self._read_state()
        if collab_id in data:
            data[collab_id]['last_event'] = event
            data[collab_id]['updated_at'] = datetime.now(timezone.utc).isoformat()
            self._write_state(data)
        self._append_log({
            "event": event,
            "collab_id": collab_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **extra
        })
