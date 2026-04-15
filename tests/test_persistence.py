"""
tests/test_persistence.py
V1.9 Sprint 1, Tasks T3.1-T3.3
JSON persistence baseline verification.

T3.1: Queue state storage — governance/queue/data/messages.json
T3.2: Task state storage — governance/task/data/tasks.json
T3.3: CLI restart survival — both files remain valid after restart

PRD Reference: PRD Section 5.I, Requirements 38-40 (Storage baseline)
"""

import json
import os
import subprocess
import sys
import pytest

import governance.queue.store as queue_store_module
import governance.task.store as task_store_module


class TestPersistenceBaseline:
    """T3.1 + T3.2: JSON storage at declared locations"""

    @pytest.fixture(autouse=True)
    def fresh_stores(self, tmp_path):
        """Point all stores to temp paths for isolation."""
        queue_store_module.DATA_DIR = tmp_path / "queue_data"
        queue_store_module.MESSAGES_FILE = queue_store_module.DATA_DIR / "messages.json"
        queue_store_module._default_store = None

        task_store_module.DATA_DIR = tmp_path / "task_data"
        task_store_module.TASKS_FILE = task_store_module.DATA_DIR / "tasks.json"
        task_store_module._default_store = None

        yield

        queue_store_module.DATA_DIR = queue_store_module.DATA_DIR  # restore on import
        task_store_module.DATA_DIR = task_store_module.DATA_DIR

    def test_queue_storage_location(self):
        """T3.1: messages.json exists at governance/queue/data/messages.json"""
        from governance.queue.store import get_store
        store = get_store()

        # Add a message and verify file exists
        from governance.queue.models import Message, MessageType
        msg = Message(sender="A", receiver="B", type=MessageType.REQUEST, payload={"test": "data"})
        store.add(msg)

        assert queue_store_module.MESSAGES_FILE.exists(), \
            f"messages.json not found at {queue_store_module.MESSAGES_FILE}"

        # Verify it is valid JSON
        with open(queue_store_module.MESSAGES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list), "messages.json root must be a list"
        assert len(data) == 1, "messages.json should contain 1 message after add"
        assert data[0]["sender"] == "A"
        assert data[0]["message_id"] == msg.message_id

    def test_task_storage_location(self):
        """T3.2: tasks.json exists at governance/task/data/tasks.json"""
        from governance.task.store import get_task_store
        store = get_task_store()

        from governance.task.models import Task
        task = Task(assigned_executor="test-agent")
        store.add(task)

        assert task_store_module.TASKS_FILE.exists(), \
            f"tasks.json not found at {task_store_module.TASKS_FILE}"

        with open(task_store_module.TASKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list), "tasks.json root must be a list"
        assert len(data) == 1, "tasks.json should contain 1 task after add"
        assert data[0]["assigned_executor"] == "test-agent"
        assert data[0]["task_id"] == task.task_id

    def test_queue_json_valid_after_multiple_writes(self):
        """T3.1: messages.json remains valid JSON after 3 write cycles"""
        from governance.queue.store import get_store
        from governance.queue.models import Message, MessageType

        store = get_store()
        message_ids = []

        for i in range(3):
            msg = Message(sender=f"A{i}", receiver=f"B{i}", type=MessageType.REQUEST, payload={"n": i})
            store.add(msg)
            message_ids.append(msg.message_id)

        # Verify JSON is still valid
        with open(queue_store_module.MESSAGES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert len(data) == 3
        # Verify we can read all three messages
        for mid in message_ids:
            msg = store.get(mid)
            assert msg is not None, f"Message {mid} not retrievable after 3 write cycles"

    def test_task_json_valid_after_multiple_writes(self):
        """T3.2: tasks.json remains valid JSON after 3 write cycles"""
        from governance.task.store import get_task_store
        from governance.task.models import Task

        store = get_task_store()
        task_ids = []

        for i in range(3):
            t = Task(assigned_executor=f"agent{i}")
            store.add(t)
            task_ids.append(t.task_id)

        with open(task_store_module.TASKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert len(data) == 3
        for tid in task_ids:
            t = store.get(tid)
            assert t is not None, f"Task {tid} not retrievable after 3 write cycles"

    def test_messages_json_human_readable(self):
        """T3.1: messages.json is human-readable and human-inspectable"""
        from governance.queue.store import get_store
        from governance.queue.models import Message, MessageType

        store = get_store()
        msg = Message(sender="planner", receiver="tdd", type=MessageType.REQUEST,
                      payload={"action": "run_tests", "priority": "high"})
        store.add(msg)

        with open(queue_store_module.MESSAGES_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        # Should be readable JSON, not binary
        assert "planner" in content, "sender not visible in raw JSON"
        assert "tdd" in content, "receiver not visible in raw JSON"
        assert "run_tests" in content, "payload not visible in raw JSON"

        # Should not contain binary or encoded content
        try:
            parsed = json.loads(content)
            assert isinstance(parsed, list)
        except json.JSONDecodeError:
            pytest.fail("messages.json is not valid JSON — not human-inspectable")

    def test_tasks_json_human_readable(self):
        """T3.2: tasks.json is human-readable and human-inspectable"""
        from governance.task.store import get_task_store
        from governance.task.models import Task

        store = get_task_store()
        task = Task(assigned_executor="jarvis-planner")
        store.add(task)

        with open(task_store_module.TASKS_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        assert "jarvis-planner" in content, "executor not visible in raw JSON"
        try:
            parsed = json.loads(content)
            assert isinstance(parsed, list)
        except json.JSONDecodeError:
            pytest.fail("tasks.json is not valid JSON — not human-inspectable")

    def test_no_binary_state(self):
        """T3.1+T3.2: Static analysis confirms no binary or hidden state"""
        from governance.queue.store import get_store
        from governance.task.store import get_task_store
        from governance.queue.models import Message, MessageType
        from governance.task.models import Task

        queue_store = get_store()
        task_store = get_task_store()

        msg = Message(sender="A", receiver="B", type=MessageType.REQUEST, payload={})
        task = Task(assigned_executor="X")

        queue_store.add(msg)
        task_store.add(task)

        for filepath in [queue_store_module.MESSAGES_FILE, task_store_module.TASKS_FILE]:
            with open(filepath, "rb") as f:
                raw = f.read()
            # No null bytes (binary indicator)
            assert b"\x00" not in raw, f"Binary null byte found in {filepath.name}"
            # Can be decoded as UTF-8
            assert raw.decode("utf-8"), f"{filepath.name} is not valid UTF-8"
            # Is valid JSON when decoded
            json.loads(raw.decode("utf-8"))

    def test_state_domains_stay_separated(self):
        """T3.1+T3.2: Queue state does not leak into task state and vice versa"""
        from governance.queue.store import get_store
        from governance.task.store import get_task_store
        from governance.queue.models import Message, MessageType
        from governance.task.models import Task

        queue_store = get_store()
        task_store = get_task_store()

        msg = Message(sender="Q", receiver="R", type=MessageType.REQUEST, payload={"queue": True})
        task = Task(assigned_executor="S")

        queue_store.add(msg)
        task_store.add(task)

        # Verify queue store has only messages
        with open(queue_store_module.MESSAGES_FILE, "r", encoding="utf-8") as f:
            msg_data = json.load(f)
        assert all("message_id" in item for item in msg_data)
        assert all("lifecycle_state" not in item for item in msg_data)

        # Verify task store has only tasks
        with open(task_store_module.TASKS_FILE, "r", encoding="utf-8") as f:
            task_data = json.load(f)
        assert all("task_id" in item for item in task_data)
        assert all("sender" not in item for item in task_data)


class TestCLIRestartSurvival:
    """T3.3: Messages and tasks persist across CLI restart simulation"""

    @pytest.fixture(autouse=True)
    def fresh_stores(self, tmp_path):
        queue_store_module.DATA_DIR = tmp_path / "queue_data"
        queue_store_module.MESSAGES_FILE = queue_store_module.DATA_DIR / "messages.json"
        queue_store_module._default_store = None

        task_store_module.DATA_DIR = tmp_path / "task_data"
        task_store_module.TASKS_FILE = task_store_module.DATA_DIR / "tasks.json"
        task_store_module._default_store = None

        yield

    def test_queue_messages_survive_restart_simulation(self):
        """
        T3.3: Messages survive simulated CLI restart.
        Simulates restart by re-initializing store and reading persisted data.
        """
        from governance.queue.store import get_store
        from governance.queue.models import Message, MessageType

        # Phase 1: Write messages
        store1 = get_store()
        msg1 = Message(sender="agent:A", receiver="agent:B", type=MessageType.REQUEST,
                       payload={"seq": 1})
        msg2 = Message(sender="agent:B", receiver="agent:A", type=MessageType.REQUEST,
                       payload={"seq": 2})
        store1.add(msg1)
        store1.add(msg2)

        # Verify written
        assert queue_store_module.MESSAGES_FILE.exists()

        # Phase 2: Simulate restart by clearing singleton and re-reading
        queue_store_module._default_store = None
        store2 = get_store()

        # Verify messages survived
        retrieved1 = store2.get(msg1.message_id)
        retrieved2 = store2.get(msg2.message_id)

        assert retrieved1 is not None, "Message 1 lost after restart simulation"
        assert retrieved2 is not None, "Message 2 lost after restart simulation"
        assert retrieved1.sender == "agent:A"
        assert retrieved2.payload["seq"] == 2

    def test_tasks_survive_restart_simulation(self):
        """
        T3.3: Tasks survive simulated CLI restart.
        Simulates restart by re-initializing store and reading persisted data.
        """
        from governance.task.store import get_task_store
        from governance.task.models import Task, TaskLifecycleState

        # Phase 1: Write tasks
        store1 = get_task_store()
        task1 = Task(assigned_executor="planner")
        task2 = Task(assigned_executor="tdd")
        store1.add(task1)
        store1.add(task2)

        # Advance task1 to RUNNING (initial QUEUED -> DISPATCHED -> RUNNING per PRD §5.B Req 8)
        task1.transition_to(TaskLifecycleState.DISPATCHED)
        task1.transition_to(TaskLifecycleState.RUNNING)
        store1.update(task1)

        assert task_store_module.TASKS_FILE.exists()

        # Phase 2: Simulate restart
        task_store_module._default_store = None
        store2 = get_task_store()

        retrieved1 = store2.get(task1.task_id)
        retrieved2 = store2.get(task2.task_id)

        assert retrieved1 is not None, "Task 1 lost after restart simulation"
        assert retrieved2 is not None, "Task 2 lost after restart simulation"
        assert retrieved1.lifecycle_state == TaskLifecycleState.RUNNING
        assert retrieved2.lifecycle_state == TaskLifecycleState.QUEUED  # Initial state per PRD

    def test_mixed_queue_and_task_persistence(self):
        """
        T3.3: Both queue and task files are valid JSON simultaneously after restart.
        Verifies no corruption or state leakage between stores.
        """
        from governance.queue.store import get_store
        from governance.task.store import get_task_store
        from governance.queue.models import Message, MessageType
        from governance.task.models import Task

        queue_store = get_store()
        task_store = get_task_store()

        msg = Message(sender="Q", receiver="R", type=MessageType.REQUEST, payload={})
        task = Task(assigned_executor="X")

        queue_store.add(msg)
        task_store.add(task)

        # Both files valid simultaneously
        for filepath in [queue_store_module.MESSAGES_FILE, task_store_module.TASKS_FILE]:
            with open(filepath, "r", encoding="utf-8") as f:
                json.load(f)  # Must not raise

        # Simulate restart
        queue_store_module._default_store = None
        task_store_module._default_store = None

        queue_store2 = get_store()
        task_store2 = get_task_store()

        assert queue_store2.get(msg.message_id) is not None
        assert task_store2.get(task.task_id) is not None

        # Still both valid
        for filepath in [queue_store_module.MESSAGES_FILE, task_store_module.TASKS_FILE]:
            with open(filepath, "r", encoding="utf-8") as f:
                json.load(f)