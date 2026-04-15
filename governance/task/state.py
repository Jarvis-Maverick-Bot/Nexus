"""
governance/task/state.py
V1.9 Sprint 1, Task T2.3 (revised to match PRD V0_1 §5.B Req 8)
Task lifecycle state machine.

States: QUEUED -> DISPATCHED -> RUNNING -> WAITING -> SUCCEEDED | FAILED | CANCELED | TIMED_OUT
Explicit transition rules and trigger documentation.
"""

from typing import Dict, List, Tuple

from .models import Task, TaskLifecycleState
from .store import get_task_store


_TRANSITIONS: Dict[TaskLifecycleState, Tuple[List[TaskLifecycleState], str]] = {
    TaskLifecycleState.QUEUED: (
        [TaskLifecycleState.DISPATCHED, TaskLifecycleState.CANCELED],
        "QUEUED: task is waiting to be dispatched. Dispatch to executor (DISPATCHED) or cancel (CANCELED)."
    ),
    TaskLifecycleState.DISPATCHED: (
        [TaskLifecycleState.RUNNING, TaskLifecycleState.CANCELED],
        "DISPATCHED: executor has been assigned. Start work (RUNNING) or cancel (CANCELED)."
    ),
    TaskLifecycleState.RUNNING: (
        [TaskLifecycleState.WAITING, TaskLifecycleState.SUCCEEDED, TaskLifecycleState.FAILED, TaskLifecycleState.CANCELED, TaskLifecycleState.TIMED_OUT],
        "RUNNING: executor is actively working. Wait on dependency (WAITING), succeed (SUCCEEDED), fail (FAILED), cancel (CANCELED), or timeout (TIMED_OUT)."
    ),
    TaskLifecycleState.WAITING: (
        [TaskLifecycleState.RUNNING, TaskLifecycleState.SUCCEEDED, TaskLifecycleState.FAILED, TaskLifecycleState.CANCELED, TaskLifecycleState.TIMED_OUT],
        "WAITING: blocked on external dependency. Resume work (RUNNING), succeed (SUCCEEDED), fail (FAILED), cancel (CANCELED), or timeout (TIMED_OUT)."
    ),
    TaskLifecycleState.SUCCEEDED: (
        [],
        "SUCCEEDED: task completed successfully. Terminal state."
    ),
    TaskLifecycleState.FAILED: (
        [],
        "FAILED: task encountered an error. Terminal state."
    ),
    TaskLifecycleState.CANCELED: (
        [],
        "CANCELED: task was cancelled by authorized action. Terminal state."
    ),
    TaskLifecycleState.TIMED_OUT: (
        [],
        "TIMED_OUT: task exceeded allowed execution window. Terminal state."
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
            TaskLifecycleState.SUCCEEDED,
            TaskLifecycleState.FAILED,
            TaskLifecycleState.CANCELED,
            TaskLifecycleState.TIMED_OUT,
        ),
    }


def all_states() -> List[TaskLifecycleState]:
    return [
        TaskLifecycleState.QUEUED,
        TaskLifecycleState.DISPATCHED,
        TaskLifecycleState.RUNNING,
        TaskLifecycleState.WAITING,
        TaskLifecycleState.SUCCEEDED,
        TaskLifecycleState.FAILED,
        TaskLifecycleState.CANCELED,
        TaskLifecycleState.TIMED_OUT,
    ]