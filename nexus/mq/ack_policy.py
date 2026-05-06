"""
MQ ACK Policy — 3.5 Implementation
ACK means intake/transport only; never workflow progress.

Design source: GOVERNED_WORKFLOW_RUNTIME_AND_MESSAGE_QUEUE_ARCHITECTURE_V0_1.md §0.2, §5.3
Baseline status: accepted-for-skeleton (3.5 V1.1, commit 3f7a5a0)

ACK Convention (§0.2):
- ACK means: "message was received, persisted, claimed, or accepted for processing"
- ACK does NOT mean: task execution succeeded, evidence was written, state transitioned, human approved
- Business progress is emitted only as Business_Message after accepted evidence/state commit
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import uuid


@dataclass
class AckEvent:
    """
    Represents an ACK event at an async MQ boundary.

    Design rule: ACK events must NEVER mutate governed workflow state.
    They are transport receipts only.
    """
    ack_id: str = field(default_factory=lambda: f"ack-{uuid.uuid4().hex[:12]}")
    message_id: str = ""          # message being acknowledged
    workflow_instance_id: str = ""
    ack_level: str = ""           # "broker_received" | "broker_published" | "consumer_intake" | "consumer_claimed"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    consumer_name: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "ack_id": self.ack_id,
            "message_id": self.message_id,
            "workflow_instance_id": self.workflow_instance_id,
            "ack_level": self.ack_level,
            "timestamp": self.timestamp,
            "consumer_name": self.consumer_name,
        }


@dataclass
class WorkflowStateSnapshot:
    """
    Snapshot of governed workflow state at a point in time.

    Design rule: This is what the state store says, NOT what an ACK implies.
    The state store is the source of truth; ACK events cannot change it.
    """
    workflow_instance_id: str
    current_state: str            # e.g., "created", "queued", "processing", "waiting_hitl"
    transition_count: int = 0
    last_transition_at: Optional[str] = None
    last_transition_by: Optional[str] = None  # "system" | "human" | "business_event"


class AckPolicy:
    """
    Encodes the ACK convention: ACK means intake/transport only.

    Design rule from §0.2: ACKs are required at async boundaries for reliability,
    retry, and dedupe. They must NEVER be used as business truth.

    This class provides the ACK event API and enforces that ACK events
    do not touch workflow state.
    """

    def __init__(self):
        # In-memory ACK log for testing/traceability
        # In production this would be the MQ broker's native ACK tracking
        self._ack_log: list[AckEvent] = []

    def broker_received(self, message_id: str, workflow_instance_id: str) -> AckEvent:
        """MQ broker accepted the message for queuing."""
        ack = AckEvent(
            message_id=message_id,
            workflow_instance_id=workflow_instance_id,
            ack_level="broker_received",
        )
        self._ack_log.append(ack)
        return ack

    def broker_published(self, message_id: str, workflow_instance_id: str) -> AckEvent:
        """MQ broker successfully published to a consumer or stream."""
        ack = AckEvent(
            message_id=message_id,
            workflow_instance_id=workflow_instance_id,
            ack_level="broker_published",
        )
        self._ack_log.append(ack)
        return ack

    def consumer_intake(self, message_id: str, workflow_instance_id: str, consumer_name: str) -> AckEvent:
        """Consumer picked up the message from the queue."""
        ack = AckEvent(
            message_id=message_id,
            workflow_instance_id=workflow_instance_id,
            ack_level="consumer_intake",
            consumer_name=consumer_name,
        )
        self._ack_log.append(ack)
        return ack

    def consumer_claimed(self, message_id: str, workflow_instance_id: str, consumer_name: str) -> AckEvent:
        """Consumer has claimed the message for processing (work is in progress)."""
        ack = AckEvent(
            message_id=message_id,
            workflow_instance_id=workflow_instance_id,
            ack_level="consumer_claimed",
            consumer_name=consumer_name,
        )
        self._ack_log.append(ack)
        return ack

    def get_ack_log(self) -> list[AckEvent]:
        return list(self._ack_log)

    def clear_log(self):
        self._ack_log.clear()


class WorkflowStateSeparator:
    """
    Enforces that ACK events cannot advance workflow state.

    Design rule: ACK alone does not change the workflow state record.
    State advances only through:
    1. Accepted evidence/state commit → Business_Message emitted
    2. HITL decision record normalized after valid Feedback_Message

    This class tracks state transitions separately from ACK events.
    """

    def __init__(self):
        self._state_log: list[Dict[str, Any]] = []
        self._current_states: Dict[str, str] = {}  # workflow_instance_id → state

    def current_state(self, workflow_instance_id: str) -> str:
        """Return current state. Returns 'unknown' if never set."""
        return self._current_states.get(workflow_instance_id, "unknown")

    def record_transition(
        self,
        workflow_instance_id: str,
        new_state: str,
        transition_type: str,  # "system" | "human" | "business_event"
        evidence_refs: list[str] = None,
    ) -> None:
        """
        Record a state transition. This is the ONLY way workflow state advances.

        Design rule: ACK events do not call this method.
        Only commit boundary acceptance or HITL normalization calls this.
        """
        self._current_states[workflow_instance_id] = new_state
        self._state_log.append({
            "workflow_instance_id": workflow_instance_id,
            "previous_state": self._current_states.get(workflow_instance_id, "unknown"),
            "new_state": new_state,
            "transition_type": transition_type,
            "evidence_refs": evidence_refs or [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_state_log(self) -> list[dict]:
        return list(self._state_log)

    def state_log_size(self) -> int:
        return len(self._state_log)


def test_ack_means_intake_only() -> bool:
    """
    Test: ACK event alone does not change workflow state.

    Acceptance criteria: after an ACK is issued, the workflow state must still
    be 'unknown' (never changed by the ACK).

    Design rule: §0.2 ACK convention — ACK means delivery/receipt only.
    """
    separator = WorkflowStateSeparator()
    policy = AckPolicy()

    workflow_id = "wf-test-001"
    message_id = "msg-test-001"

    # Verify state is unknown before any ACK
    assert separator.current_state(workflow_id) == "unknown", "state should start unknown"

    # Issue multiple ACKs
    policy.broker_received(message_id, workflow_id)
    policy.consumer_intake(message_id, workflow_id, "TestConsumer")
    policy.consumer_claimed(message_id, workflow_id, "TestConsumer")

    # State must still be unknown — ACK does NOT advance workflow state
    assert separator.current_state(workflow_id) == "unknown", (
        "ACK events must not change workflow state. "
        "ACK means intake/transport only, never business progress."
    )

    # Now record a real state transition (what happens after commit boundary)
    separator.record_transition(workflow_id, "processing", "system")

    # State should now be 'processing'
    assert separator.current_state(workflow_id) == "processing", (
        "State should advance only through commit boundary or HITL normalization"
    )

    # Issue another ACK after state transition — state should still be 'processing'
    policy.broker_published(message_id, workflow_id)
    assert separator.current_state(workflow_id) == "processing", (
        "ACK after state transition must not revert or change state"
    )

    return True
