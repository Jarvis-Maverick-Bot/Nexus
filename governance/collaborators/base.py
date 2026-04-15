"""
governance/collaborators/base.py
V1.9 Sprint 1, Tasks T4.1, T4.2
Base collaborator interface for initial proof-case collaborators.

Defines the minimum contract for a collaborator in the governed loop.
Initial proof-case collaborators: jarvis-planner, jarvis-tdd.

Architecture reference: Arch Doc §19 — bounded persistent collaborator capability
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import uuid

from governance.queue.models import Message, MessageType, MessageState
from governance.queue.store import get_store as get_queue_store
from governance.queue.state import transition as route_message


@dataclass
class CollaboratorOutput:
    """Structured output from a collaborator operation."""
    success: bool
    summary: str
    payload: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    output_message_id: Optional[str] = None
    completed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CollaboratorBase(ABC):
    """
    Base class for initial proof-case collaborators.

    Each collaborator:
    - Has a stable named identity (role string)
    - Owns a queue inbox (receives items routed to its role)
    - Can emit output into the governed queue via enqueue
    - Returns structured evidence via CollaboratorOutput

    This is the initial proof-case: not a general framework,
    but a concrete implementation demonstrating bounded persistent
    collaborator capability.
    """

    def __init__(self, role_name: str):
        """
        Initialize collaborator with stable named identity.

        Args:
            role_name: stable identifier (e.g., "planner", "tdd")
                      Must match the role used in routing rules.
        """
        self.role_name = role_name
        self._collaborator_id = f"collaborator:{role_name}"
        self._interaction_count = 0

    @property
    def collaborator_id(self) -> str:
        """Stable identity visible in governance status."""
        return self._collaborator_id

    @property
    def interaction_count(self) -> int:
        """Number of interactions this collaborator has participated in."""
        return self._interaction_count

    def _record_interaction(self) -> None:
        """Record that this collaborator processed an item."""
        self._interaction_count += 1

    @abstractmethod
    def process(self, input_message: Message) -> CollaboratorOutput:
        """
        Process an incoming message and return structured output.

        Subclasses implement their specific processing logic here.

        Args:
            input_message: the Message this collaborator is handling

        Returns:
            CollaboratorOutput with success/failure, summary, and payload
        """
        ...

    def enqueue_output(
        self,
        receiver: str,
        payload: Dict[str, Any],
        original_message_id: Optional[str] = None,
    ) -> Message:
        """
        Emit output into the governed queue as a new message.

        Args:
            receiver: role or participant to receive this output
            payload: the work output or result data
            original_message_id: optionally link to source message

        Returns:
            The created output Message
        """
        queue_store = get_queue_store()
        out_msg = Message(
            sender=self.role_name,
            receiver=receiver,
            type=MessageType.RESPONSE,
            payload={
                "_source_collaborator": self.collaborator_id,
                "_source_message_id": original_message_id,
                **payload,
            },
            state=MessageState.NEW,
        )
        queue_store.add(out_msg)
        self._record_interaction()
        return out_msg

    def receive_from_queue(self, limit: int = 10) -> List[Message]:
        """
        Retrieve messages in this collaborator's inbox (routed to this role).

        Args:
            limit: maximum number of messages to retrieve

        Returns:
            List of messages addressed to this collaborator
        """
        queue_store = get_queue_store()
        messages = queue_store.list_by_receiver(self.role_name)
        # Return up to limit, excluding CLOSED terminal messages
        active = [m for m in messages if m.state != MessageState.CLOSED]
        return active[:limit]

    def can_claim(self, message: Message) -> bool:
        """
        Determine if this collaborator can claim a given message.

        Base implementation: message must be addressed to this role
        and in a claimable state (NEW or ROUTED).

        Subclasses can override with additional rules.
        """
        return (
            message.receiver == self.role_name
            and message.state in (MessageState.NEW, MessageState.ROUTED)
        )

    def claim(self, message: Message) -> None:
        """
        Claim a message for this collaborator's processing.

        Transitions message to CLAIMED state.

        Args:
            message: the message to claim

        Raises:
            ValueError: if message cannot be claimed by this collaborator
        """
        if not self.can_claim(message):
            raise ValueError(
                f"Collaborator {self.role_name} cannot claim message "
                f"{message.message_id} (state={message.state.value}, receiver={message.receiver})"
            )
        if message.state == MessageState.NEW:
            route_message(message.message_id, MessageState.ROUTED)
        route_message(message.message_id, MessageState.CLAIMED)

    def get_status(self) -> Dict[str, Any]:
        """
        Return collaborator status for governance inspection.

        Returns:
            dict with identity, role, interaction count, inbox size
        """
        inbox = self.receive_from_queue(limit=100)
        return {
            "collaborator_id": self.collaborator_id,
            "role_name": self.role_name,
            "interaction_count": self._interaction_count,
            "inbox_size": len(inbox),
            "inbox_active": sum(1 for m in inbox if m.state not in (MessageState.ANSWERED, MessageState.CLOSED)),
        }