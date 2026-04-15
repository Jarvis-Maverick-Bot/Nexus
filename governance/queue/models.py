"""
governance/queue/models.py
V1.9 Sprint 1, Task T1.1
Message object model for governed queue.

PRD Reference: PRD Section 5.A, Requirements 1-5 (Queue and message coordination)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import uuid


class MessageState(str, Enum):
    """Message lifecycle states. States: NEW -> ROUTED -> CLAIMED -> WAITING -> ANSWERED -> CLOSED"""
    NEW = "NEW"
    ROUTED = "ROUTED"
    CLAIMED = "CLAIMED"
    WAITING = "WAITING"
    ANSWERED = "ANSWERED"
    CLOSED = "CLOSED"


class MessageType(str, Enum):
    """Message type classification."""
    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    SIGNAL = "SIGNAL"
    ESCALATION = "ESCALATION"


@dataclass
class Message:
    """
    Governed message object.

    Fields:
        message_id: Unique identifier (UUID)
        sender: Name of sending participant
        receiver: Name of receiving participant
        type: MessageType enum value
        payload: Arbitrary payload dict (serializable)
        state: Current MessageState
        created_at: ISO timestamp of creation
        updated_at: ISO timestamp of last update
        linked_response_id: message_id of the linked response, if any
    """
    sender: str
    receiver: str
    type: MessageType
    payload: dict
    state: MessageState = MessageState.NEW
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    linked_response_id: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize message to dict for JSON storage."""
        return {
            "message_id": self.message_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "type": self.type.value,
            "payload": self.payload,
            "state": self.state.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "linked_response_id": self.linked_response_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        """Deserialize message from dict."""
        msg = cls(
            sender=data["sender"],
            receiver=data["receiver"],
            type=MessageType(data["type"]),
            payload=data["payload"],
            state=MessageState(data["state"]),
            message_id=data["message_id"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            linked_response_id=data.get("linked_response_id"),
        )
        return msg

    def link_response(self, response_id: str) -> None:
        """Link this message to a response message_id."""
        self.linked_response_id = response_id
        self.touch()

    def transition_to(self, new_state: MessageState) -> None:
        """Transition message to new state. Validates transition is legal."""
        valid_transitions = {
            MessageState.NEW: [MessageState.ROUTED, MessageState.CLOSED],
            MessageState.ROUTED: [MessageState.CLAIMED, MessageState.CLOSED],
            MessageState.CLAIMED: [MessageState.WAITING, MessageState.ANSWERED, MessageState.CLOSED],
            MessageState.WAITING: [MessageState.ANSWERED, MessageState.CLOSED],
            MessageState.ANSWERED: [MessageState.CLOSED],
            MessageState.CLOSED: [],
        }
        if new_state in valid_transitions.get(self.state, []):
            self.state = new_state
            self.touch()
        else:
            raise ValueError(
                f"Illegal transition: {self.state.value} -> {new_state.value}. "
                f"Valid transitions from {self.state.value}: {[s.value for s in valid_transitions[self.state]]}"
            )

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def is_terminal(self) -> bool:
        """Returns True if message is in a terminal state."""
        return self.state in (MessageState.ANSWERED, MessageState.CLOSED)