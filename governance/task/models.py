"""
governance/task/models.py
V1.9 Sprint 1, Task T2.1
Task execution lifecycle model.

Distinct from Message (governance/queue/models.py) and WorkItem (platform_model/objects.py).
Implements the 8-state task lifecycle per PRD Section 5.B, Requirements 6-10.

States: CREATED -> QUEUED -> PROMOTED -> IN_PROGRESS -> WAITING -> COMPLETED -> FAILED -> CANCELLED
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any
import uuid


class TaskLifecycleState(str, Enum):
    """
    8-state task lifecycle.
    States: CREATED -> QUEUED -> PROMOTED -> IN_PROGRESS -> WAITING -> COMPLETED -> FAILED -> CANCELLED
    """
    CREATED = "CREATED"          # Task created, not yet queued
    QUEUED = "QUEUED"            # Queued for execution
    PROMOTED = "PROMOTED"        # Promoted from queue (source message consumed)
    IN_PROGRESS = "IN_PROGRESS"  # Executor has claimed it, work ongoing
    WAITING = "WAITING"          # Waiting on external dependency or input
    COMPLETED = "COMPLETED"      # Work finished successfully
    FAILED = "FAILED"            # Work failed or errored
    CANCELLED = "CANCELLED"      # Task cancelled before completion


class TaskResult:
    """
    Result record for a completed or failed task.
    Stored as embedded field in Task, inspectable via 'governance result <task_id>'.
    """
    def __init__(
        self,
        status: str,  # "success" | "failure" | "cancelled"
        summary: str,
        output: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        completed_at: Optional[str] = None,
    ):
        self.status = status
        self.summary = summary
        self.output = output or {}
        self.error = error
        self.completed_at = completed_at or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "summary": self.summary,
            "output": self.output,
            "error": self.error,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskResult":
        return cls(
            status=data["status"],
            summary=data["summary"],
            output=data.get("output"),
            error=data.get("error"),
            completed_at=data.get("completed_at"),
        )


@dataclass
class Task:
    """
    Governed task object.
    Distinct from Message (queue coordination) and WorkItem (delivery tracking).

    Fields:
        task_id: Unique identifier (UUID)
        source_message_id: message_id this task was promoted from (None if created directly)
        assigned_executor: Name of the assigned executor participant
        lifecycle_state: Current TaskLifecycleState
        created_at: ISO timestamp of creation
        updated_at: ISO timestamp of last update
        result_record: Embedded TaskResult (None until task completes/fails)
    """
    assigned_executor: str
    lifecycle_state: TaskLifecycleState = TaskLifecycleState.CREATED
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_message_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    result_record: Optional[TaskResult] = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "source_message_id": self.source_message_id,
            "assigned_executor": self.assigned_executor,
            "lifecycle_state": self.lifecycle_state.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "result_record": self.result_record.to_dict() if self.result_record else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        result_record = None
        if data.get("result_record"):
            result_record = TaskResult.from_dict(data["result_record"])
        return cls(
            task_id=data["task_id"],
            source_message_id=data.get("source_message_id"),
            assigned_executor=data["assigned_executor"],
            lifecycle_state=TaskLifecycleState(data["lifecycle_state"]),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            result_record=result_record,
        )

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def transition_to(self, new_state: TaskLifecycleState) -> None:
        valid_transitions = {
            TaskLifecycleState.CREATED: [TaskLifecycleState.QUEUED, TaskLifecycleState.CANCELLED],
            TaskLifecycleState.QUEUED: [TaskLifecycleState.PROMOTED, TaskLifecycleState.CANCELLED],
            TaskLifecycleState.PROMOTED: [TaskLifecycleState.IN_PROGRESS, TaskLifecycleState.CANCELLED],
            TaskLifecycleState.IN_PROGRESS: [TaskLifecycleState.WAITING, TaskLifecycleState.COMPLETED, TaskLifecycleState.FAILED, TaskLifecycleState.CANCELLED],
            TaskLifecycleState.WAITING: [TaskLifecycleState.IN_PROGRESS, TaskLifecycleState.COMPLETED, TaskLifecycleState.FAILED, TaskLifecycleState.CANCELLED],
            TaskLifecycleState.COMPLETED: [],
            TaskLifecycleState.FAILED: [],
            TaskLifecycleState.CANCELLED: [],
        }
        if new_state in valid_transitions.get(self.lifecycle_state, []):
            self.lifecycle_state = new_state
            self.touch()
        else:
            raise ValueError(
                f"Illegal transition: {self.lifecycle_state.value} -> {new_state.value}. "
                f"Valid: {[s.value for s in valid_transitions.get(self.lifecycle_state, [])]}"
            )

    def complete(self, summary: str, output: Optional[Dict[str, Any]] = None) -> None:
        self.result_record = TaskResult(status="success", summary=summary, output=output)
        self.transition_to(TaskLifecycleState.COMPLETED)

    def fail(self, summary: str, error: str) -> None:
        self.result_record = TaskResult(status="failure", summary=summary, error=error)
        self.transition_to(TaskLifecycleState.FAILED)

    def is_terminal(self) -> bool:
        return self.lifecycle_state in (
            TaskLifecycleState.COMPLETED,
            TaskLifecycleState.FAILED,
            TaskLifecycleState.CANCELLED,
        )