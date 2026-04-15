"""
governance/task/state.py
V1.9 Sprint 1, Task T2.3
Task lifecycle state machine.

States: CREATED -> QUEUED -> PROMOTED -> IN_PROGRESS -> WAITING -> COMPLETED -> FAILED -> CANCELLED
Explicit transition rules and trigger documentation.
"""

from typing import Dict, List, Tuple

from .models import Task, TaskLifecycleState
from .store import get_task_store


_TRANSITIONS: Dict[TaskLifecycleState, Tuple[List[TaskLifecycleState], str]] = {
    TaskLifecycleState.CREATED: (
        [TaskLifecycleState.QUEUED, TaskLifecycleState.CANCELLED],
        "CREATED: task initialized. Queue it for execution (QUEUED) or cancel before queuing (CANCELLED)."
    ),
    TaskLifecycleState.QUEUED: (
        [TaskLifecycleState.PROMOTED, TaskLifecycleState.CANCELLED],
        "QUEUED: task is queued and waiting to be picked up. Promote when executor picks it up (PROMOTED) or cancel (CANCELLED)."
    ),
    TaskLifecycleState.PROMOTED: (
        [TaskLifecycleState.IN_PROGRESS, TaskLifecycleState.CANCELLED],
        "PROMOTED: source message consumed, task is in executor's queue. Start work (IN_PROGRESS) or cancel (CANCELLED)."
    ),
    TaskLifecycleState.IN_PROGRESS: (
        [TaskLifecycleState.WAITING, TaskLifecycleState.COMPLETED, TaskLifecycleState.FAILED, TaskLifecycleState.CANCELLED],
        "IN_PROGRESS: work is underway. Wait on dependency (WAITING), complete successfully (COMPLETED), fail with error (FAILED), or cancel (CANCELLED)."
    ),
    TaskLifecycleState.WAITING: (
        [TaskLifecycleState.IN_PROGRESS, TaskLifecycleState.COMPLETED, TaskLifecycleState.FAILED, TaskLifecycleState.CANCELLED],
        "WAITING: blocked on external dependency. Resume work (IN_PROGRESS), complete (COMPLETED), fail (FAILED), or cancel (CANCELLED)."
    ),
    TaskLifecycleState.COMPLETED: (
        [],
        "COMPLETED: task finished successfully. Terminal state."
    ),
    TaskLifecycleState.FAILED: (
        [],
        "FAILED: task encountered an error. Terminal state."
    ),
    TaskLifecycleState.CANCELLED: (
        [],
        "CANCELLED: task was cancelled. Terminal state."
    ),
}


def valid_next_states(from_state: TaskLifecycleState) -> List[TaskLifecycleState]:
    if from_state in _TRANSITIONS:
        return _TRANSITIONS[from_state][0]
    return []


def trigger_description(from_state: TaskLifecycleState) -> str:
    if from_state in _TRANSITIONS:
        return _TRANSITIONS[from_state][1]
    return f"{from_state.value}: no transition rules defined."


def can_transition(from_state: TaskLifecycleState, to_state: TaskLifecycleState) -> bool:
    return to_state in valid_next_states(from_state)


def transition(task_id: str, to_state: TaskLifecycleState) -> Task:
    """
    Transition a task to a new state.

    Args:
        task_id: the task to transition
        to_state: the target state

    Returns:
        The updated Task

    Raises:
        KeyError: task not found
        ValueError: illegal transition
    """
    store = get_task_store()
    task = store.get(task_id)
    if task is None:
        raise KeyError(f"Task {task_id} not found")
    if not can_transition(task.lifecycle_state, to_state):
        raise ValueError(
            f"Illegal transition: {task.lifecycle_state.value} -> {to_state.value}. "
            f"Valid from {task.lifecycle_state.value}: {[s.value for s in valid_next_states(task.lifecycle_state)]}"
        )
    task.transition_to(to_state)
    store.update(task)
    return task


def get_state_info(state: TaskLifecycleState) -> dict:
    return {
        "state": state.value,
        "valid_transitions": [s.value for s in valid_next_states(state)],
        "description": trigger_description(state),
        "is_terminal": state in (
            TaskLifecycleState.COMPLETED,
            TaskLifecycleState.FAILED,
            TaskLifecycleState.CANCELLED,
        ),
    }


def all_states() -> List[TaskLifecycleState]:
    return [
        TaskLifecycleState.CREATED,
        TaskLifecycleState.QUEUED,
        TaskLifecycleState.PROMOTED,
        TaskLifecycleState.IN_PROGRESS,
        TaskLifecycleState.WAITING,
        TaskLifecycleState.COMPLETED,
        TaskLifecycleState.FAILED,
        TaskLifecycleState.CANCELLED,
    ]