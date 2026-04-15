"""
tests/test_collaborators.py
V1.9 Sprint 1, Tasks T4.1-T4.4
Unit + integration tests for initial proof-case collaborators.

T4.1: planner module (governance/collaborators/planner.py)
T4.2: tdd module (governance/collaborators/tdd.py)
T4.3: registry (governance/collaborators/registry.py)
T4.4: Operational trace: Planner -> queue -> TDD -> governed return

Architecture reference: Arch Doc §19 — bounded persistent collaborator capability
"""

import pytest

import governance.collaborators.registry as registry_module
import governance.queue.store as queue_store_module


class TestPlannerCollaborator:
    """T4.1: Tests for governance.collaborators.planner.PlannerCollaborator"""

    @pytest.fixture(autouse=True)
    def fresh_planner(self, tmp_path):
        """Fresh planner with temp queue store."""
        queue_store_module.DATA_DIR = tmp_path / "queue_data"
        queue_store_module.MESSAGES_FILE = queue_store_module.DATA_DIR / "messages.json"
        queue_store_module._default_store = None
        yield
        queue_store_module._default_store = None

    def test_planner_creation(self):
        """T4.1: Planner has stable named identity."""
        from governance.collaborators.planner import PlannerCollaborator
        planner = PlannerCollaborator()
        assert planner.role_name == "planner"
        assert planner.collaborator_id == "collaborator:planner"
        assert planner.interaction_count == 0

    def test_planner_process_valid_request(self):
        """T4.1: Planner processes valid planning request and enqueues output."""
        from governance.collaborators.planner import get_planner
        from governance.queue.models import Message, MessageType

        planner = get_planner()

        # Create input message (from governance/another agent)
        input_msg = Message(
            sender="governance",
            receiver="planner",
            type=MessageType.REQUEST,
            payload={
                "task_description": "Implement user authentication module",
                "priority": "high",
            },
        )
        queue_store_module.get_store().add(input_msg)

        result = planner.process(input_msg)

        assert result.success is True
        assert "plan_id" in result.payload
        assert len(result.payload["steps"]) == 3
        assert result.output_message_id is not None
        assert planner.interaction_count == 1

    def test_planner_process_invalid_request(self):
        """T4.1: Planner returns failure for missing task_description."""
        from governance.collaborators.planner import get_planner
        from governance.queue.models import Message, MessageType

        planner = get_planner()
        input_msg = Message(
            sender="gov",
            receiver="planner",
            type=MessageType.REQUEST,
            payload={"priority": "high"},  # missing task_description
        )
        result = planner.process(input_msg)
        assert result.success is False
        assert "task_description" in result.error

    def test_planner_emit_preview(self):
        """T4.1: Planner can emit plan preview without queue round-trip."""
        from governance.collaborators.planner import get_planner

        planner = get_planner()
        result = planner.emit_plan_preview("Test task description")
        assert result.success is True
        assert "plan_id" in result.payload
        assert result.payload["type"] == "preview"

    def test_planner_get_status(self):
        """T4.1: Planner status shows identity, role, interaction count, inbox."""
        from governance.collaborators.planner import get_planner

        planner = get_planner()
        status = planner.get_status()
        assert status["role_name"] == "planner"
        assert status["collaborator_id"] == "collaborator:planner"
        assert "interaction_count" in status
        assert "inbox_size" in status


class TestTDDCollaborator:
    """T4.2: Tests for governance.collaborators.tdd.TDDCollaborator"""

    @pytest.fixture(autouse=True)
    def fresh_tdd(self, tmp_path):
        queue_store_module.DATA_DIR = tmp_path / "queue_data"
        queue_store_module.MESSAGES_FILE = queue_store_module.DATA_DIR / "messages.json"
        queue_store_module._default_store = None
        yield
        queue_store_module._default_store = None

    def test_tdd_creation(self):
        """T4.2: TDD has stable named identity."""
        from governance.collaborators.tdd import TDDCollaborator
        tdd = TDDCollaborator()
        assert tdd.role_name == "tdd"
        assert tdd.collaborator_id == "collaborator:tdd"

    def test_tdd_process_valid_plan(self):
        """T4.2: TDD processes valid plan output and returns validation."""
        from governance.collaborators.tdd import get_tdd
        from governance.queue.models import Message, MessageType

        tdd = get_tdd()
        input_msg = Message(
            sender="planner",
            receiver="tdd",
            type=MessageType.REQUEST,
            payload={
                "_plan_output": {
                    "plan_id": "plan-abc123",
                    "task_description": "Implement auth module",
                    "steps": [
                        {"step_id": "1", "action": "analyze", "description": "Analyze", "depends_on": []},
                        {"step_id": "2", "action": "design", "description": "Design", "depends_on": ["1"]},
                    ],
                }
            },
        )
        queue_store_module.get_store().add(input_msg)

        result = tdd.process(input_msg)

        assert result.success is True
        assert result.payload["validation_passed"] is True
        assert len(result.payload["test_results"]) == 2

    def test_tdd_validate_plan_direct(self):
        """T4.2: TDD can validate a plan directly without queue processing."""
        from governance.collaborators.tdd import get_tdd

        tdd = get_tdd()
        result = tdd.validate_plan({
            "plan_id": "test-plan-1",
            "task_description": "Test task",
            "steps": [{"step_id": "1", "action": "analyze", "description": "A", "depends_on": []}],
        })
        assert result.success is True
        assert result.payload["validation_passed"] is True

    def test_tdd_get_status(self):
        """T4.2: TDD status shows identity and inbox state."""
        from governance.collaborators.tdd import get_tdd

        tdd = get_tdd()
        status = tdd.get_status()
        assert status["role_name"] == "tdd"
        assert "inbox_size" in status


class TestCollaboratorRegistry:
    """T4.3: Tests for governance.collaborators.registry"""

    def test_registry_creation(self):
        """T4.3: Registry starts empty and auto-registers initial proof-case collaborators."""
        # Reset registry
        registry_module._default_registry = None
        reg = registry_module.get_registry()
        assert reg.is_registered("planner")
        assert reg.is_registered("tdd")

    def test_get_registered_collaborator(self):
        """T4.3: Registry returns registered collaborator by role name."""
        from governance.collaborators.planner import get_planner
        from governance.collaborators.tdd import get_tdd

        reg = registry_module.get_registry()
        planner = reg.get("planner")
        assert planner is not None
        assert planner.role_name == "planner"

        tdd = reg.get("tdd")
        assert tdd is not None
        assert tdd.role_name == "tdd"

    def test_list_roles(self):
        """T4.3: Registry lists all registered roles."""
        reg = registry_module.get_registry()
        roles = reg.list_roles()
        assert "planner" in roles
        assert "tdd" in roles

    def test_registry_get_status(self):
        """T4.3: Registry returns all collaborator statuses."""
        reg = registry_module.get_registry()
        statuses = reg.all_status()
        role_names = [s["role_name"] for s in statuses]
        assert "planner" in role_names
        assert "tdd" in role_names

    def test_registry_unregister(self):
        """T4.3: Registry can unregister a collaborator."""
        from governance.collaborators.base import CollaboratorBase

        reg = registry_module.get_registry()
        assert reg.is_registered("planner")
        removed = reg.unregister("planner")
        assert removed is True
        assert not reg.is_registered("planner")

        # Re-register via class (planner re-added via get_planner)
        from governance.collaborators.planner import get_planner
        reg.register("planner", get_planner())


class TestCollaboratorBase:
    """Tests for the CollaboratorBase class."""

    @pytest.fixture(autouse=True)
    def fresh_base(self, tmp_path):
        queue_store_module.DATA_DIR = tmp_path / "queue_data"
        queue_store_module.MESSAGES_FILE = queue_store_module.DATA_DIR / "messages.json"
        queue_store_module._default_store = None
        yield
        queue_store_module._default_store = None

    def test_can_claim_valid_message(self):
        """T4.1/T4.2: Collaborator can claim message addressed to its role in valid state."""
        from governance.collaborators.planner import get_planner
        from governance.queue.models import Message, MessageType, MessageState

        planner = get_planner()

        msg_new = Message(
            sender="gov", receiver="planner",
            type=MessageType.REQUEST, payload={}
        )
        assert planner.can_claim(msg_new) is True

        msg_routed = Message(
            sender="gov", receiver="planner",
            type=MessageType.REQUEST, payload={}
        )
        msg_routed.state = MessageState.ROUTED
        assert planner.can_claim(msg_routed) is True

    def test_cannot_claim_wrong_receiver(self):
        """T4.1/T4.2: Collaborator cannot claim message addressed to different role."""
        from governance.collaborators.planner import get_planner
        from governance.queue.models import Message, MessageType

        planner = get_planner()
        msg = Message(
            sender="gov", receiver="tdd",  # addressed to tdd, not planner
            type=MessageType.REQUEST, payload={}
        )
        assert planner.can_claim(msg) is False

    def test_claim_transitions_to_claimed(self):
        """T4.1/T4.2: Claim transitions message to CLAIMED state."""
        from governance.collaborators.planner import get_planner
        from governance.queue.models import Message, MessageType, MessageState

        planner = get_planner()
        queue_store = queue_store_module.get_store()
        msg = Message(
            sender="gov", receiver="planner",
            type=MessageType.REQUEST, payload={}
        )
        queue_store_module.get_store().add(msg)

        planner.claim(msg)

        updated = queue_store_module.get_store().get(msg.message_id)
        assert updated.state == MessageState.CLAIMED

    def test_enqueue_output(self):
        """T4.1/T4.2: Collaborator can enqueue output to another role."""
        from governance.collaborators.planner import get_planner

        planner = get_planner()
        output_msg = planner.enqueue_output(
            receiver="tdd",
            payload={"result": "test output"},
            original_message_id="orig-123",
        )

        assert output_msg.sender == "planner"
        assert output_msg.receiver == "tdd"
        assert output_msg.payload["_source_collaborator"] == "collaborator:planner"
        assert output_msg.payload["_source_message_id"] == "orig-123"
        assert output_msg.payload["result"] == "test output"

    def test_receive_from_queue(self):
        """T4.1/T4.2: Collaborator can read messages from its inbox."""
        from governance.collaborators.tdd import get_tdd
        from governance.queue.models import Message, MessageType

        tdd = get_tdd()
        queue_store = queue_store_module.get_store()

        # Add messages to tdd's inbox
        msg1 = Message(sender="planner", receiver="tdd", type=MessageType.REQUEST, payload={"n": 1})
        msg2 = Message(sender="planner", receiver="tdd", type=MessageType.REQUEST, payload={"n": 2})
        queue_store.add(msg1)
        queue_store.add(msg2)

        inbox = tdd.receive_from_queue(limit=10)
        assert len(inbox) == 2


class TestCollaboratorOperationalTrace:
    """T4.4: End-to-end operational trace — Planner -> queue -> TDD -> governed return"""

    @pytest.fixture(autouse=True)
    def fresh_trace(self, tmp_path):
        queue_store_module.DATA_DIR = tmp_path / "queue_data"
        queue_store_module.MESSAGES_FILE = queue_store_module.DATA_DIR / "messages.json"
        queue_store_module._default_store = None
        yield
        queue_store_module._default_store = None

    def test_full_trace_planner_to_tdd(self):
        """
        T4.4: Complete trace — Planner processes request -> enqueues to TDD -> TDD processes -> returns result.

        This is the primary Scenario 1 proof: agent-to-agent queue loop.
        """
        from governance.collaborators.planner import get_planner
        from governance.collaborators.tdd import get_tdd
        from governance.queue.models import Message, MessageType, MessageState

        planner = get_planner()
        tdd = get_tdd()
        queue_store = queue_store_module.get_store()

        # Step 1: Governance sends planning request to planner
        planning_msg = Message(
            sender="governance",
            receiver="planner",
            type=MessageType.REQUEST,
            payload={
                "task_description": "Implement user management feature",
                "priority": "normal",
            },
        )
        queue_store.add(planning_msg)

        # Step 2: Planner processes and enqueues to TDD
        plan_result = planner.process(planning_msg)
        assert plan_result.success is True
        assert plan_result.output_message_id is not None

        # Verify planner output is in queue (to tdd)
        output_msg = queue_store.get(plan_result.output_message_id)
        assert output_msg is not None
        assert output_msg.receiver == "tdd"
        assert "_plan_output" in output_msg.payload

        # Step 3: TDD receives and processes the plan
        tdd_input = output_msg
        tdd_result = tdd.process(tdd_input)
        assert tdd_result.success is True
        assert tdd_result.payload["validation_passed"] is True
        assert tdd_result.payload["test_count"] >= 1

        # Verify TDD returned result to queue (message answered)
        updated_msg = queue_store.get(tdd_input.message_id)
        assert updated_msg.state == MessageState.ANSWERED

    def test_trace_with_interaction_count(self):
        """T4.4: Both collaborators increment interaction count."""
        from governance.collaborators.planner import PlannerCollaborator
        from governance.collaborators.tdd import TDDCollaborator
        from governance.queue.models import Message, MessageType

        # Use fresh instances to avoid singleton carry-over from other tests
        planner = PlannerCollaborator()
        tdd = TDDCollaborator()

        initial_count = planner.interaction_count

        msg = Message(
            sender="gov", receiver="planner",
            type=MessageType.REQUEST,
            payload={"task_description": "Test task"},
        )
        queue_store_module.get_store().add(msg)

        result = planner.process(msg)
        assert result.success is True
        assert planner.interaction_count > initial_count

    def test_both_collaborators_persist_across_restart(self):
        """T4.4: Both collaborators survive simulated CLI restart."""
        from governance.collaborators.planner import get_planner
        from governance.collaborators.planner import PlannerCollaborator
        from governance.collaborators.tdd import get_tdd
        from governance.queue.models import Message, MessageType

        queue_store_module._default_store = None

        # First session: create messages
        planner1 = get_planner()
        tdd1 = get_tdd()
        queue_store1 = queue_store_module.get_store()

        msg = Message(
            sender="gov", receiver="planner",
            type=MessageType.REQUEST,
            payload={"task_description": "Restart test"},
        )
        queue_store1.add(msg)
        planner1.process(msg)

        # Simulate restart: re-init singleton
        queue_store_module._default_store = None

        # Second session: verify state persisted
        planner2 = get_planner()
        tdd2 = get_tdd()

        # Singleton returns existing registered instance
        assert planner2.role_name == "planner"
        assert tdd2.role_name == "tdd"
        assert planner2.interaction_count >= 1