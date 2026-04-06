"""
harness.checkpointer — Layer 2 Checkpoint Persistence

Atomic save/load of WorkItem state transitions.
Ensures state is never lost mid-transition.

Lifecycle:
    before_transition: checkpoint current state (savepoint)
    after_transition: checkpoint new state (confirmed)
    restore: reload from last checkpoint

Resumability: if session dies mid-transition, restore from last checkpoint.
"""

from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import HarnessConfig, get_default_config


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CheckpointError(Exception):
    """Raised when a checkpoint operation fails."""
    pass


class CheckpointNotFoundError(CheckpointError):
    """Raised when no checkpoint exists for a given task_id."""
    pass


# ---------------------------------------------------------------------------
# Checkpoint Record
# ---------------------------------------------------------------------------


@dataclass
class CheckpointRecord:
    """Metadata for a single checkpoint."""
    task_id: str
    checkpoint_id: str
    from_stage: str
    to_stage: str
    actor_role: str
    created_at: datetime
    completed: bool
    # File paths
    before_path: str
    after_path: str

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "checkpoint_id": self.checkpoint_id,
            "from_stage": self.from_stage,
            "to_stage": self.to_stage,
            "actor_role": self.actor_role,
            "created_at": self.created_at.isoformat(),
            "completed": self.completed,
            "before_path": self.before_path,
            "after_path": self.after_path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CheckpointRecord:
        return cls(
            task_id=data["task_id"],
            checkpoint_id=data["checkpoint_id"],
            from_stage=data["from_stage"],
            to_stage=data["to_stage"],
            actor_role=data["actor_role"],
            created_at=datetime.fromisoformat(data["created_at"]),
            completed=data["completed"],
            before_path=data["before_path"],
            after_path=data["after_path"],
        )


# ---------------------------------------------------------------------------
# Checkpointer
# ---------------------------------------------------------------------------


class Checkpointer:
    """
    Manages atomic checkpoint/restore for WorkItem state transitions.

    Checkpoint lifecycle:
        1. checkpoint_before(task_id, from_stage, to_stage, actor_role)
           → saves current workitem state as "before" snapshot
        2. [application: advance the stage]
        3. checkpoint_after(task_id, from_stage, to_stage, actor_role)
           → saves new workitem state as "after" snapshot, marks complete
        4. On session restart: restore_from_checkpoint(task_id)
           → reloads last completed state

    For resumability: if session dies mid-transition, recover from last
    completed checkpoint.
    """

    def __init__(self, config: HarnessConfig | None = None):
        self.config = config or get_default_config()
        self.checkpoint_dir = self.config.checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.checkpoint_dir / "checkpoint_index.json"

    # --- Path helpers ---

    def _checkpoint_path(self, task_id: str, checkpoint_id: str, phase: str) -> Path:
        return self.checkpoint_dir / f"ckpt_{task_id}_{checkpoint_id}_{phase}.json"

    def _index(self) -> dict[str, dict]:
        if self._index_path.exists():
            return json.loads(self._index_path.read_text(encoding="utf-8"))
        return {}

    def _save_index(self, index: dict[str, dict]) -> None:
        self._index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    # --- Checkpoint operations ---

    def checkpoint_before(
        self,
        task_id: str,
        from_stage: str,
        to_stage: str,
        actor_role: str,
        workitem_state: dict,
    ) -> CheckpointRecord:
        """
        Save state before attempting a transition.

        This is the "savepoint" — if the transition fails or session dies,
        we can recover to this state.
        """
        checkpoint_id = str(uuid.uuid4())[:8]
        before_path = self._checkpoint_path(task_id, checkpoint_id, "before")

        # Write before state
        before_path.write_text(json.dumps(workitem_state, indent=2), encoding="utf-8")

        record = CheckpointRecord(
            task_id=task_id,
            checkpoint_id=checkpoint_id,
            from_stage=from_stage,
            to_stage=to_stage,
            actor_role=actor_role,
            created_at=datetime.utcnow(),
            completed=False,
            before_path=str(before_path),
            after_path="",
        )

        # Update index
        index = self._index()
        if task_id not in index:
            index[task_id] = {}
        index[task_id][checkpoint_id] = record.to_dict()
        self._save_index(index)

        return record

    def checkpoint_after(
        self,
        record: CheckpointRecord,
        workitem_state: dict,
    ) -> CheckpointRecord:
        """
        Save state after successful transition.

        Marks the checkpoint as completed — this is the recovery point.
        """
        after_path = self._checkpoint_path(record.task_id, record.checkpoint_id, "after")
        after_path.write_text(json.dumps(workitem_state, indent=2), encoding="utf-8")

        completed_record = CheckpointRecord(
            task_id=record.task_id,
            checkpoint_id=record.checkpoint_id,
            from_stage=record.from_stage,
            to_stage=record.to_stage,
            actor_role=record.actor_role,
            created_at=record.created_at,
            completed=True,
            before_path=record.before_path,
            after_path=str(after_path),
        )

        # Update index
        index = self._index()
        if record.task_id in index and record.checkpoint_id in index[record.task_id]:
            index[record.task_id][record.checkpoint_id] = completed_record.to_dict()
            self._save_index(index)

        return completed_record

    def get_latest_completed_checkpoint(self, task_id: str) -> CheckpointRecord | None:
        """Get the most recent completed checkpoint for a task_id."""
        index = self._index()
        if task_id not in index:
            return None

        checkpoints = [
            CheckpointRecord.from_dict(c)
            for c in index[task_id].values()
            if c.get("completed", False)
        ]

        if not checkpoints:
            return None

        # Return most recent completed
        checkpoints.sort(key=lambda c: c.created_at, reverse=True)
        return checkpoints[0]

    def get_latest_checkpoint(self, task_id: str) -> CheckpointRecord | None:
        """Get the most recent checkpoint for a task_id (completed or not)."""
        index = self._index()
        if task_id not in index:
            return None

        checkpoints = [
            CheckpointRecord.from_dict(c)
            for c in index[task_id].values()
        ]

        if not checkpoints:
            return None

        checkpoints.sort(key=lambda c: c.created_at, reverse=True)
        return checkpoints[0]

    def load_checkpoint_state(self, checkpoint: CheckpointRecord) -> dict:
        """
        Load state from a checkpoint.

        For completed checkpoints: load from "after" state (the confirmed state)
        For incomplete checkpoints: load from "before" state (the savepoint)
        """
        path = Path(checkpoint.after_path if checkpoint.completed else checkpoint.before_path)
        if not path.exists():
            raise CheckpointError(f"Checkpoint file not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def restore_from_latest(self, task_id: str) -> dict:
        """
        Restore the latest completed state for a task_id.

        Raises CheckpointNotFoundError if no completed checkpoint exists.
        """
        checkpoint = self.get_latest_completed_checkpoint(task_id)
        if checkpoint is None:
            raise CheckpointNotFoundError(f"No completed checkpoint found for task '{task_id}'")
        return self.load_checkpoint_state(checkpoint)

    def restore_from_latest_any(self, task_id: str) -> tuple[dict, CheckpointRecord]:
        """
        Restore from latest checkpoint (completed or not).

        Returns the state dict and the checkpoint record.
        """
        checkpoint = self.get_latest_checkpoint(task_id)
        if checkpoint is None:
            raise CheckpointNotFoundError(f"No checkpoint found for task '{task_id}'")
        return self.load_checkpoint_state(checkpoint), checkpoint

    def list_checkpoints(self, task_id: str) -> list[CheckpointRecord]:
        """List all checkpoints for a task_id."""
        index = self._index()
        if task_id not in index:
            return []
        return sorted(
            [CheckpointRecord.from_dict(c) for c in index[task_id].values()],
            key=lambda c: c.created_at,
            reverse=True,
        )

    def cleanup_completed(self, task_id: str, keep_latest: int = 3) -> int:
        """
        Remove completed checkpoints for a task, keeping the N most recent.

        Returns number of checkpoints removed.
        """
        checkpoints = self.list_checkpoints(task_id)
        completed = [c for c in checkpoints if c.completed]
        to_remove = completed[keep_latest:]

        index = self._index()
        removed = 0
        for ckpt in to_remove:
            # Remove files
            for path_str in [ckpt.before_path, ckpt.after_path]:
                if path_str:
                    p = Path(path_str)
                    if p.exists():
                        p.unlink()
            # Remove from index
            if task_id in index and ckpt.checkpoint_id in index[task_id]:
                del index[task_id][ckpt.checkpoint_id]
                removed += 1

        if removed > 0:
            self._save_index(index)

        return removed
