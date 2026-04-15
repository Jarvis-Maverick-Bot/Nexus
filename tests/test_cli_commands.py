"""
tests/test_cli_commands.py
V1.9 Sprint 1, Tasks T5.2, T5.3
Unit and integration tests for governance queue-list and task-list commands.

T5.2: governance queue-list command (governance/cli/commands/queue_cmd.py)
T5.3: governance task-list command (governance/cli/commands/task_cmd.py)
T5.4: State domain separation verified (queue != task != work-item)
"""

import pytest
import json
import tempfile
from pathlib import Path

import governance.queue.store as queue_store_module
import governance.task.store as task_store_module


class TestQueueListCommand:
    """T5.2: Tests for `governance queue-list` command."""

    @pytest.fixture(autouse=True)
    def fresh_queue_store(self, tmp_path):
        """Fresh queue store with temp directory."""
        queue_store_module.DATA_DIR = tmp_path / "queue_data"
        queue_store_module.MESSAGES_FILE = queue_store_module.DATA_DIR / "messages.json"
        queue_store_module._default_store = None
        yield
        queue_store_module._default_store = None

    def test_queue_list_empty(self):
        """T5.2: queue-list returns empty when no messages."""
        from governance.cli.commands.queue_cmd import queue_list, format_queue_list
        msgs = queue_list()
        assert msgs == []
        output = format_queue_list(msgs)
        assert "no messages" in output

    def test_queue_list_with_messages(self):
        """T5.2: queue-list returns all messages with correct fields."""
        from governance.cli.commands.queue_cmd import queue_list
        from governance.queue.models import Message, MessageType, MessageState

        store = queue_store_module.get_store()
        msg1 = Message(sender="gov", receiver="planner", type=MessageType.REQUEST, payload={"n": 1})
        msg2 = Message(sender="planner", receiver="tdd", type=MessageType.RESPONSE, payload={})
        store.add(msg1)
        store.add(msg2)

        msgs = queue_list()
        assert len(msgs) == 2
        # Verify fields present
        for m in msgs:
            assert "message_id" in m
            assert "sender" in m
            assert "receiver" in m
            assert "type" in m
            assert "state" in m
            assert "created_at" in m

    def test_queue_list_shows_state(self):
        """T5.2: queue-list shows correct state per message."""
        from governance.cli.commands.queue_cmd import queue_list
        from governance.queue.models import Message, MessageType, MessageState

        store = queue_store_module.get_store()
        msg = Message(sender="gov", receiver="planner", type=MessageType.REQUEST, payload={})
        store.add(msg)

        msgs = queue_list()
        assert len(msgs) == 1
        assert msgs[0]["state"] == MessageState.NEW.value
        assert msgs[0]["sender"] == "gov"
        assert msgs[0]["receiver"] == "planner"


class TestTaskListCommand:
    """T5.3: Tests for `governance task-list` command."""

    @pytest.fixture(autouse=True)
    def fresh_task_store(self, tmp_path):
        """Fresh task store with temp directory."""
        task_store_module.DATA_DIR = tmp_path / "task_data"
        task_store_module.TASKS_FILE = task_store_module.DATA_DIR / "tasks.json"
        task_store_module._default_store = None
        yield
        task_store_module._default_store = None

    def test_task_list_empty(self):
        """T5.3: task-list returns empty when no tasks."""
        from governance.cli.commands.task_cmd import task_list, format_task_list
        tasks = task_list()
        assert tasks == []
        output = format_task_list(tasks)
        assert "no tasks" in output

    def test_task_list_with_tasks(self):
        """T5.3: task-list returns all tasks with correct fields."""
        from governance.cli.commands.task_cmd import task_list
        from governance.task.models import Task, TaskLifecycleState
        from governance.task.store import get_task_store as get_task_store

        store = get_task_store()
        task1 = Task(source_message_id="msg-001", assigned_executor="planner")
        task2 = Task(source_message_id="msg-002", assigned_executor="tdd")
        store.add(task1)
        store.add(task2)

        tasks = task_list()
        assert len(tasks) == 2
        for t in tasks:
            assert "task_id" in t
            assert "lifecycle_state" in t
            assert "source_message_id" in t
            assert "assigned_executor" in t
            assert "created_at" in t

    def test_task_list_shows_state(self):
        """T5.3: task-list shows correct lifecycle state."""
        from governance.cli.commands.task_cmd import task_list
        from governance.task.models import Task, TaskLifecycleState
        from governance.task.store import get_task_store as get_task_store

        store = get_task_store()
        task = Task(source_message_id="msg-001", assigned_executor="planner")
        store.add(task)

        tasks = task_list()
        assert len(tasks) == 1
        assert tasks[0]["lifecycle_state"] == TaskLifecycleState.QUEUED.value  # Initial state per PRD §5.B Req 8


class TestStateDomainSeparation:
    """T5.4: Verify queue state != task state != work-item state."""

    def test_queue_state_enum_distinct_from_task_state_enum(self):
        """T5.4: Queue and Task state enums are distinct enum types (different state machines)."""
        from governance.queue.models import MessageState
        from governance.task.models import TaskLifecycleState

        # Distinct enum types
        assert MessageState is not TaskLifecycleState
        # Queue: 8 states (NEW, ROUTED, CLAIMED, WAITING, ANSWERED, CLOSED, CANCELED, EXPIRED)
        # Task: 8 states (QUEUED, DISPATCHED, RUNNING, WAITING, SUCCEEDED, FAILED, CANCELED, TIMED_OUT)
        assert len(MessageState) == 8
        assert len(TaskLifecycleState) == 8
        # The enums are from different classes (true separation)
        assert isinstance(MessageState.NEW, MessageState)
        assert isinstance(TaskLifecycleState.QUEUED, TaskLifecycleState)  # Initial state
        # Cross-type membership is False (they are different types)
        assert not isinstance(MessageState.NEW, TaskLifecycleState)
        assert not isinstance(TaskLifecycleState.QUEUED, MessageState)

    def test_queue_message_fields_distinct_from_task_fields(self):
        """T5.4: Message fields are distinct from Task fields."""
        from governance.queue.models import Message
        from governance.task.models import Task

        msg_fields = set(Message.__dataclass_fields__.keys())
        task_fields = set(Task.__dataclass_fields__.keys())

        # Key field differences
        assert "message_id" in msg_fields
        assert "task_id" in task_fields
        assert "message_id" not in task_fields
        assert "task_id" not in msg_fields

        # No cross-contamination
        assert msg_fields & task_fields == {"created_at", "updated_at"}  # timestamps only

    def test_queue_store_separate_from_task_store(self):
        """T5.4: Queue and task stores are independent files."""
        import governance.queue.store as qs
        import governance.task.store as ts

        # Different file names
        assert qs.MESSAGES_FILE.name == "messages.json"
        assert ts.TASKS_FILE.name == "tasks.json"
        # Different parent directories
        assert "queue" in str(qs.MESSAGES_FILE)
        assert "task" in str(ts.TASKS_FILE)


class TestCLIHelpIntegration:
    """T5.2/T5.3: Verify queue-list and task-list appear in CLI help."""

    def test_help_shows_queue_list(self):
        """T5.2: --help includes queue-list command."""
        import io, contextlib, sys

        import governance.cli.cli as cli_module
        old_argv = sys.argv
        f = io.StringIO()
        try:
            sys.argv = ["cli.py", "--help"]
            with contextlib.redirect_stdout(f):
                try:
                    cli_module.main()
                except SystemExit:
                    pass
        finally:
            sys.argv = old_argv

        output = f.getvalue()
        assert "queue-list" in output

    def test_help_shows_task_list(self):
        """T5.3: --help includes task-list command."""
        import io, contextlib, sys

        import governance.cli.cli as cli_module
        old_argv = sys.argv
        f = io.StringIO()
        try:
            sys.argv = ["cli.py", "--help"]
            with contextlib.redirect_stdout(f):
                try:
                    cli_module.main()
                except SystemExit:
                    pass
        finally:
            sys.argv = old_argv

        output = f.getvalue()
        assert "task-list" in output