"""
governance/task/promotion.py
V1.9 Sprint 1, Task T2.4
Queue-to-task promotion logic.

Converts a queued Message into an executable Task.
Source message is transitioned to CLAIMED state; new Task is created in PROMOTED state.

The message-to-task boundary is explicit and inspectable:
- Message carries the task_id once promoted
- Task carries the source_message_id
- CLI can trace message -> task via 'governance inspect-message <id>'
"""

from typing import Optional

from governance.queue.models import Message, MessageState, MessageType
from governance.queue.store import get_store as get_queue_store
from governance.queue.state import transition as transition_message

from .models import Task, TaskLifecycleState
from .store import get_task_store


def promote_message_to_task(
    message_id: str,
    executor: str,
    claim: bool = True,
) -> Task:
    """
    Promote a queue message to a task.

    Steps:
    1. Retrieve and validate the message (must be in ROUTED or CLAIMED state)
    2. Transition message to CLAIMED (if not already) or close it as consumed
    3. Create Task in PROMOTED state, linked to source message
    4. Store task

    Args:
        message_id: the message to promote
        executor: the executor being assigned this task
        claim: if True, transition message to CLAIMED (still actionable)
               if False, leave message in current state (consumed silently)

    Returns:
        The newly created Task

    Raises:
        KeyError: message not found
        ValueError: message not in promotable state
    """
    queue_store = get_queue_store()
    task_store = get_task_store()

    message = queue_store.get(message_id)
    if message is None:
        raise KeyError(f"Message {message_id} not found")

    # Only ROUTED or CLAIMED messages can be promoted
    if message.state not in (MessageState.ROUTED, MessageState.CLAIMED):
        raise ValueError(
            f"Message {message_id} is in state {message.state.value}. "
            f"Cannot promote. Must be ROUTED or CLAIMED."
        )

    # Consume the message (transition to CLAIMED if not already)
    if claim and message.state == MessageState.ROUTED:
        transition_message(message_id, MessageState.CLAIMED)

    # Create the task, linked to the source message
    task = Task(
        assigned_executor=executor,
        source_message_id=message_id,
        lifecycle_state=TaskLifecycleState.PROMOTED,
    )

    # Link the message -> task relationship in payload
    message.payload["_promoted_task_id"] = task.task_id
    queue_store.update(message)

    task_store.add(task)
    return task


def get_task_for_message(message_id: str) -> Optional[Task]:
    """Find a task that was promoted from a given message."""
    queue_store = get_queue_store()
    message = queue_store.get(message_id)
    if message is None:
        return None
    task_id = message.payload.get("_promoted_task_id")
    if task_id is None:
        return None
    task_store = get_task_store()
    return task_store.get(task_id)


def get_source_message(task_id: str) -> Optional[Message]:
    """Find the source message for a task."""
    task_store = get_task_store()
    task = task_store.get(task_id)
    if task is None:
        return None
    if task.source_message_id is None:
        return None
    queue_store = get_queue_store()
    return queue_store.get(task.source_message_id)


def list_promotion_records(executor: Optional[str] = None) -> list:
    """
    List all tasks with their source message info.

    Args:
        executor: if provided, filter to only tasks assigned to this executor

    Returns:
        List of dicts: {task_id, source_message_id, executor, state}
    """
    task_store = get_task_store()
    if executor:
        tasks = task_store.list_by_executor(executor)
    else:
        tasks = task_store.list_all()

    return [
        {
            "task_id": t.task_id,
            "source_message_id": t.source_message_id,
            "assigned_executor": t.assigned_executor,
            "lifecycle_state": t.lifecycle_state.value,
            "created_at": t.created_at,
        }
        for t in tasks
    ]