"""
tests/test_queue_models.py
V1.9 Sprint 1, Tasks T1.1-T1.4
Unit tests for queue module (models, store, state, linkage)
"""

import json
import os
import tempfile
import pytest
from pathlib import Path

# Patch DATA_DIR before importing store
import governance.queue.store as store_module


class TestMessageModel:
    """Tests for governance.queue.models.Message"""

    def test_message_creation(self):
        from governance.queue.models import Message, MessageState, MessageType
        msg = Message(
            sender="agent:A",
            receiver="agent:B",
            type=MessageType.REQUEST,
            payload={"action": "do_work"},
        )
        assert msg.sender == "agent:A"
        assert msg.receiver == "agent:B"
        assert msg.type == MessageType.REQUEST
        assert msg.state == MessageState.NEW
        assert msg.message_id is not None
        assert msg.linked_response_id is None

    def test_message_to_dict_roundtrip(self):
        from governance.queue.models import Message, MessageType
        msg = Message(
            sender="agent:A",
            receiver="agent:B",
            type=MessageType.REQUEST,
            payload={"key": "value"},
        )
        d = msg.to_dict()
        assert d["sender"] == "agent:A"
        assert d["type"] == "REQUEST"
        restored = Message.from_dict(d)
        assert restored.sender == msg.sender
        assert restored.message_id == msg.message_id

    def test_state_transitions_valid(self):
        from governance.queue.models import Message, MessageState, MessageType
        msg = Message(
            sender="agent:A",
            receiver="agent:B",
            type=MessageType.REQUEST,
            payload={},
        )
        msg.transition_to(MessageState.ROUTED)
        assert msg.state == MessageState.ROUTED
        msg.transition_to(MessageState.CLAIMED)
        assert msg.state == MessageState.CLAIMED

    def test_state_transition_illegal_raises(self):
        from governance.queue.models import Message, MessageState, MessageType
        msg = Message(
            sender="agent:A",
            receiver="agent:B",
            type=MessageType.REQUEST,
            payload={},
        )
        # Cannot go NEW -> ANSWERED directly (not in valid transitions)
        with pytest.raises(ValueError):
            msg.transition_to(MessageState.ANSWERED)

    def test_is_terminal(self):
        from governance.queue.models import Message, MessageState, MessageType
        msg = Message(
            sender="agent:A",
            receiver="agent:B",
            type=MessageType.REQUEST,
            payload={},
        )
        assert not msg.is_terminal()
        msg.state = MessageState.ANSWERED
        assert msg.is_terminal()
        msg.state = MessageState.CLOSED
        assert msg.is_terminal()
        msg.state = MessageState.CANCELED
        assert msg.is_terminal()
        msg.state = MessageState.EXPIRED
        assert msg.is_terminal()

    def test_link_response(self):
        from governance.queue.models import Message, MessageType
        msg = Message(
            sender="agent:A",
            receiver="agent:B",
            type=MessageType.REQUEST,
            payload={},
        )
        msg.link_response("response-123")
        assert msg.linked_response_id == "response-123"


class TestQueueState:
    """Tests for governance.queue.state"""

    def test_valid_next_states(self):
        from governance.queue.state import valid_next_states
        from governance.queue.models import MessageState
        # NEW can go to ROUTED, CANCELED, or EXPIRED (per queue/state.py)
        assert MessageState.ROUTED in valid_next_states(MessageState.NEW)
        assert MessageState.CANCELED in valid_next_states(MessageState.NEW)
        assert MessageState.EXPIRED in valid_next_states(MessageState.NEW)
        assert MessageState.ANSWERED not in valid_next_states(MessageState.NEW)

    def test_can_transition(self):
        from governance.queue.state import can_transition
        from governance.queue.models import MessageState
        assert can_transition(MessageState.NEW, MessageState.ROUTED)
        assert can_transition(MessageState.NEW, MessageState.CANCELED)
        assert not can_transition(MessageState.NEW, MessageState.ANSWERED)

    def test_all_states(self):
        from governance.queue.state import all_states
        from governance.queue.models import MessageState
        states = all_states()
        # MessageState now has 8 states: NEW, ROUTED, CLAIMED, WAITING, ANSWERED, CLOSED, CANCELED, EXPIRED
        assert len(states) == 8
        assert MessageState.CANCELED in states
        assert MessageState.EXPIRED in states
        assert states == [
            MessageState.NEW, MessageState.ROUTED, MessageState.CLAIMED,
            MessageState.WAITING, MessageState.ANSWERED, MessageState.CLOSED,
            MessageState.CANCELED, MessageState.EXPIRED,
        ]


class TestQueueStore:
    """Tests for governance.queue.store"""

    @pytest.fixture(autouse=True)
    def temp_store(self, tmp_path):
        """Use temp directory for all store tests."""
        original_data_dir = store_module.DATA_DIR
        original_messages = store_module.MESSAGES_FILE
        store_module.DATA_DIR = tmp_path / "queue_data"
        store_module.MESSAGES_FILE = store_module.DATA_DIR / "messages.json"
        store_module._default_store = None
        yield
        store_module.DATA_DIR = original_data_dir
        store_module.MESSAGES_FILE = original_messages
        store_module._default_store = None

    def test_add_and_get(self):
        from governance.queue.models import Message, MessageType
        from governance.queue.store import get_store
        store = get_store()
        msg = Message(
            sender="A", receiver="B",
            type=MessageType.REQUEST, payload={"n": 1},
        )
        store.add(msg)
        retrieved = store.get(msg.message_id)
        assert retrieved is not None
        assert retrieved.sender == "A"

    def test_update_message(self):
        from governance.queue.models import Message, MessageType, MessageState
        from governance.queue.store import get_store
        store = get_store()
        msg = Message(
            sender="A", receiver="B",
            type=MessageType.REQUEST, payload={},
        )
        store.add(msg)
        msg.state = MessageState.ROUTED
        store.update(msg)
        updated = store.get(msg.message_id)
        assert updated.state == MessageState.ROUTED

    def test_delete_message(self):
        from governance.queue.models import Message, MessageType
        from governance.queue.store import get_store
        store = get_store()
        msg = Message(sender="A", receiver="B", type=MessageType.REQUEST, payload={})
        store.add(msg)
        deleted = store.delete(msg.message_id)
        assert deleted is True
        assert store.get(msg.message_id) is None

    def test_list_all(self):
        from governance.queue.models import Message, MessageType
        from governance.queue.store import get_store
        store = get_store()
        msg1 = Message(sender="A", receiver="B", type=MessageType.REQUEST, payload={})
        msg2 = Message(sender="B", receiver="A", type=MessageType.REQUEST, payload={})
        store.add(msg1)
        store.add(msg2)
        all_msgs = store.list_all()
        assert len(all_msgs) == 2

    def test_list_by_state(self):
        from governance.queue.models import Message, MessageType, MessageState
        from governance.queue.state import transition
        from governance.queue.store import get_store
        store = get_store()
        msg = Message(sender="A", receiver="B", type=MessageType.REQUEST, payload={})
        store.add(msg)
        transition(msg.message_id, MessageState.ROUTED)
        routed = store.list_by_state(MessageState.ROUTED.value)
        assert len(routed) == 1
        assert routed[0].message_id == msg.message_id

    def test_count(self):
        from governance.queue.models import Message, MessageType
        from governance.queue.store import get_store
        store = get_store()
        assert store.count() == 0
        store.add(Message(sender="A", receiver="B", type=MessageType.REQUEST, payload={}))
        assert store.count() == 1


class TestMessageLinkage:
    """Tests for governance.queue.linkage"""

    @pytest.fixture(autouse=True)
    def temp_store(self, tmp_path):
        original_data_dir = store_module.DATA_DIR
        original_messages = store_module.MESSAGES_FILE
        store_module.DATA_DIR = tmp_path / "queue_data"
        store_module.MESSAGES_FILE = store_module.DATA_DIR / "messages.json"
        store_module._default_store = None
        yield
        store_module.DATA_DIR = original_data_dir
        store_module.MESSAGES_FILE = original_messages
        store_module._default_store = None

    def test_link_request_to_response(self):
        from governance.queue.models import Message, MessageType
        from governance.queue.store import get_store
        from governance.queue.linkage import link_request_to_response
        store = get_store()
        request = Message(sender="A", receiver="B", type=MessageType.REQUEST, payload={})
        response = Message(sender="B", receiver="A", type=MessageType.RESPONSE, payload={})
        store.add(request)
        store.add(response)
        link_request_to_response(request.message_id, response.message_id)
        updated = store.get(request.message_id)
        assert updated.linked_response_id == response.message_id

    def test_get_response_for_request(self):
        from governance.queue.models import Message, MessageType
        from governance.queue.store import get_store
        from governance.queue.linkage import link_request_to_response, get_response_for_request
        store = get_store()
        request = Message(sender="A", receiver="B", type=MessageType.REQUEST, payload={})
        response = Message(sender="B", receiver="A", type=MessageType.RESPONSE, payload={})
        store.add(request)
        store.add(response)
        link_request_to_response(request.message_id, response.message_id)
        found = get_response_for_request(request.message_id)
        assert found is not None
        assert found.message_id == response.message_id

    def test_return_chain(self):
        from governance.queue.models import Message, MessageType
        from governance.queue.store import get_store
        from governance.queue.linkage import link_request_to_response, get_return_chain
        store = get_store()
        req = Message(sender="A", receiver="B", type=MessageType.REQUEST, payload={})
        res = Message(sender="B", receiver="A", type=MessageType.RESPONSE, payload={})
        store.add(req)
        store.add(res)
        link_request_to_response(req.message_id, res.message_id)
        chain = get_return_chain(req.message_id)
        assert len(chain) == 2
        assert chain[0]["is_origin"] is True
        assert chain[1]["is_origin"] is False