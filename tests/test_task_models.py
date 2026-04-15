"""
tests/test_task_models.py
V1.9 Sprint 1, Tasks T2.1-T2.4
Unit tests for task module (models, store, state, promotion)
"""

import pytest

import governance.task.store as task_store_module
import governance.queue.store as queue_store_module


class TestTaskModel:
    """Tests for governance.task.models.Task and TaskLifecycleState"""

    def test_task_creation(self):
        from governance.task.models import Task, TaskLifecycleState
        task = Task(assigned_executor="agent:dev")
        assert task.assigned_executor == "agent:dev"
        assert task.lifecycle_state == TaskLifecycleState.QUEUED  # Initial state per PRD §5.B Req 8
        assert task.task_id is not None
        assert task.source_message_id is None

    def test_task_to_dict_roundtrip(self):
        from governance.task.models import Task
        task = Task(assigned_executor="agent:dev")
        d = task.to_dict()
        restored = Task.from_dict(d)
        assert restored.task_id == task.task_id
        assert restored.assigned_executor == task.assigned_executor

    def test_task_state_transitions_valid(self):
        from governance.task.models import Task, TaskLifecycleState
        task = Task(assigned_executor="agent:dev")
        # Initial: QUEUED -> DISPATCHED -> RUNNING -> SUCCEEDED (per PRD §5.B Req 8)
        task.transition_to(TaskLifecycleState.DISPATCHED)
        assert task.lifecycle_state == TaskLifecycleState.DISPATCHED
        task.transition_to(TaskLifecycleState.RUNNING)
        assert task.lifecycle_state == TaskLifecycleState.RUNNING

    def test_task_state_transition_illegal(self):
        from governance.task.models import Task, TaskLifecycleState
        task = Task(assigned_executor="agent:dev")
        # Cannot go QUEUED -> SUCCEEDED directly (must go through DISPATCHED -> RUNNING first)
        with pytest.raises(ValueError):
            task.transition_to(TaskLifecycleState.SUCCEEDED)

    def test_task_complete(self):
        from governance.task.models import Task, TaskLifecycleState
        task = Task(assigned_executor="agent:dev")
        task.transition_to(TaskLifecycleState.DISPATCHED)
        task.transition_to(TaskLifecycleState.RUNNING)
        task.complete("All done", {"result": 42})
        assert task.lifecycle_state == TaskLifecycleState.SUCCEEDED
        assert task.result_record is not None
        assert task.result_record.status == "success"
        assert task.result_record.output["result"] == 42

    def test_task_fail(self):
        from governance.task.models import Task, TaskLifecycleState
        task = Task(assigned_executor="agent:dev")
        task.transition_to(TaskLifecycleState.DISPATCHED)
        task.transition_to(TaskLifecycleState.RUNNING)
        task.fail("Build error", "SyntaxError: invalid syntax at line 42")
        assert task.lifecycle_state == TaskLifecycleState.FAILED
        assert task.result_record.status == "failure"
        assert task.result_record.error == "SyntaxError: invalid syntax at line 42"

    def test_task_is_terminal(self):
        from governance.task.models import Task, TaskLifecycleState
        task = Task(assigned_executor="agent:dev")
        assert not task.is_terminal()
        task.lifecycle_state = TaskLifecycleState.SUCCEEDED
        assert task.is_terminal()
        task.lifecycle_state = TaskLifecycleState.FAILED
        assert task.is_terminal()
        task.lifecycle_state = TaskLifecycleState.CANCELED
        assert task.is_terminal()
        task.lifecycle_state = TaskLifecycleState.TIMED_OUT
        assert task.is_terminal()


class TestTaskState:
    """Tests for governance.task.state"""

    def test_valid_next_states(self):
        from governance.task.state import valid_next_states
        from governance.task.models import TaskLifecycleState
        # Initial state is QUEUED. Can go to DISPATCHED or CANCELED
        assert TaskLifecycleState.DISPATCHED in valid_next_states(TaskLifecycleState.QUEUED)
        assert TaskLifecycleState.SUCCEEDED not in valid_next_states(TaskLifecycleState.QUEUED)

    def test_can_transition(self):
        from governance.task.state import can_transition
        from governance.task.models import TaskLifecycleState
        assert can_transition(TaskLifecycleState.QUEUED, TaskLifecycleState.DISPATCHED)
        assert not can_transition(TaskLifecycleState.QUEUED, TaskLifecycleState.SUCCEEDED)

    def test_all_states(self):
        from governance.task.state import all_states
        from governance.task.models import TaskLifecycleState
        states = all_states()
        assert len(states) == 8  # QUEUED, DISPATCHED, RUNNING, WAITING, SUCCEEDED, FAILED, CANCELED, TIMED_OUT
        assert TaskLifecycleState.QUEUED in states
        assert TaskLifecycleState.CANCELED in states  # Note: CANCELED (1 L), not CANCELLED

    def test_get_state_info(self):
        from governance.task.state import get_state_info
        from governance.task.models import TaskLifecycleState
        info = get_state_info(TaskLifecycleState.RUNNING)
        assert info["state"] == "RUNNING"
        assert TaskLifecycleState.WAITING.value in info["valid_transitions"]
        assert info["is_terminal"] is False


class TestTaskStore:
    """Tests for governance.task.store"""

    @pytest.fixture(autouse=True)
    def temp_store(self, tmp_path):
        original = task_store_module.DATA_DIR
        original_file = task_store_module.TASKS_FILE
        task_store_module.DATA_DIR = tmp_path / "task_data"
        task_store_module.TASKS_FILE = task_store_module.DATA_DIR / "tasks.json"
        task_store_module._default_store = None
        yield
        task_store_module.DATA_DIR = original
        task_store_module.TASKS_FILE = original_file
        task_store_module._default_store = None

    def test_add_and_get(self):
        from governance.task.models import Task
        from governance.task.store import get_task_store
        store = get_task_store()
        task = Task(assigned_executor="agent:dev")
        store.add(task)
        retrieved = store.get(task.task_id)
        assert retrieved is not None
        assert retrieved.assigned_executor == "agent:dev"

    def test_update_task(self):
        from governance.task.models import Task, TaskLifecycleState
        from governance.task.store import get_task_store
        store = get_task_store()
        task = Task(assigned_executor="agent:dev")
        store.add(task)
        task.lifecycle_state = TaskLifecycleState.QUEUED
        store.update(task)
        updated = store.get(task.task_id)
        assert updated.lifecycle_state == TaskLifecycleState.QUEUED

    def test_delete_task(self):
        from governance.task.models import Task
        from governance.task.store import get_task_store
        store = get_task_store()
        task = Task(assigned_executor="agent:dev")
        store.add(task)
        deleted = store.delete(task.task_id)
        assert deleted is True
        assert store.get(task.task_id) is None

    def test_list_by_state(self):
        from governance.task.models import Task, TaskLifecycleState
        from governance.task.store import get_task_store
        store = get_task_store()
        t1 = Task(assigned_executor="dev1")
        t2 = Task(assigned_executor="dev2")
        store.add(t1)
        store.add(t2)
        t1.lifecycle_state = TaskLifecycleState.RUNNING
        store.update(t1)
        running = store.list_by_state(TaskLifecycleState.RUNNING.value)
        assert len(running) == 1


class TestPromotion:
    """Tests for governance.task.promotion"""

    @pytest.fixture(autouse=True)
    def setup_stores(self, tmp_path):
        # Setup task store
        orig_task_dir = task_store_module.DATA_DIR
        orig_task_file = task_store_module.TASKS_FILE
        task_store_module.DATA_DIR = tmp_path / "task_data"
        task_store_module.TASKS_FILE = task_store_module.DATA_DIR / "tasks.json"
        task_store_module._default_store = None

        # Setup queue store
        orig_queue_dir = queue_store_module.DATA_DIR
        orig_queue_file = queue_store_module.MESSAGES_FILE
        queue_store_module.DATA_DIR = tmp_path / "queue_data"
        queue_store_module.MESSAGES_FILE = queue_store_module.DATA_DIR / "messages.json"
        queue_store_module._default_store = None

        yield

        task_store_module.DATA_DIR = orig_task_dir
        task_store_module.TASKS_FILE = orig_task_file
        task_store_module._default_store = None
        queue_store_module.DATA_DIR = orig_queue_dir
        queue_store_module.MESSAGES_FILE = orig_queue_file
        queue_store_module._default_store = None

    def test_promote_message_to_task(self):
        from governance.queue.models import Message, MessageType
        from governance.queue.store import get_store as get_queue
        from governance.task.promotion import promote_message_to_task
        from governance.task.models import TaskLifecycleState

        # Setup: a message in ROUTED state
        queue_store = get_queue()
        msg = Message(sender="planner", receiver="tdd", type=MessageType.REQUEST, payload={"work": "test"})
        queue_store.add(msg)

        # Transition to ROUTED (from NEW)
        from governance.queue.state import transition as route_message
        from governance.queue.models import MessageState
        route_message(msg.message_id, MessageState.ROUTED)

        # Promote: new task starts in QUEUED state (per PRD §5.B Req 8)
        task = promote_message_to_task(msg.message_id, executor="jarvis-tdd")
        assert task is not None
        assert task.assigned_executor == "jarvis-tdd"
        assert task.source_message_id == msg.message_id
        assert task.lifecycle_state == TaskLifecycleState.QUEUED

    def test_promote_invalid_state(self):
        from governance.queue.models import Message, MessageType
        from governance.queue.store import get_store as get_queue
        from governance.task.promotion import promote_message_to_task

        queue_store = get_queue()
        msg = Message(sender="planner", receiver="tdd", type=MessageType.REQUEST, payload={})
        queue_store.add(msg)

        # Message is in NEW state - cannot promote
        with pytest.raises(ValueError, match="Cannot promote"):
            promote_message_to_task(msg.message_id, executor="jarvis-tdd")

    def test_get_task_for_message(self):
        from governance.queue.models import Message, MessageType
        from governance.queue.store import get_store as get_queue
        from governance.queue.state import transition as route_message
        from governance.queue.models import MessageState
        from governance.task.promotion import promote_message_to_task, get_task_for_message

        queue_store = get_queue()
        msg = Message(sender="planner", receiver="tdd", type=MessageType.REQUEST, payload={})
        queue_store.add(msg)
        route_message(msg.message_id, MessageState.ROUTED)

        task = promote_message_to_task(msg.message_id, executor="tdd")
        found = get_task_for_message(msg.message_id)
        assert found is not None
        assert found.task_id == task.task_id

    def test_list_promotion_records(self):
        from governance.queue.models import Message, MessageType
        from governance.queue.store import get_store as get_queue
        from governance.queue.state import transition as route_message
        from governance.queue.models import MessageState
        from governance.task.promotion import promote_message_to_task, list_promotion_records

        queue_store = get_queue()
        msg = Message(sender="planner", receiver="tdd", type=MessageType.REQUEST, payload={})
        queue_store.add(msg)
        route_message(msg.message_id, MessageState.ROUTED)
        promote_message_to_task(msg.message_id, executor="tdd")

        records = list_promotion_records()
        assert len(records) >= 1

        filtered = list_promotion_records(executor="tdd")
        assert all(r["assigned_executor"] == "tdd" for r in filtered)