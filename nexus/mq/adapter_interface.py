"""
MQ Adapter Interface — 3.5 Implementation
Abstract vendor-neutral interface between runtime coordinator and MQ transport.

Design source: GOVERNED_WORKFLOW_RUNTIME_AND_MESSAGE_QUEUE_ARCHITECTURE_V0_1.md §5.3, §5.6, §7.7
Baseline status: accepted-for-skeleton (3.5 V1.1, commit 3f7a5a0)

Interface contract — all adapters must implement:
- publish(envelope) -> ack
- consume() -> Optional[msg]
- consume_by_id(message_id) -> Optional[msg]
- ack(message_id, level) -> ack
- retry_with_dlq(...) -> DlqEvent
- emit_dlq(...) -> DlqEvent
- compute_backoff(attempt) -> seconds
- get_dlq_events() -> list[DlqEvent]
- get_ack_log() -> list[dict]
- replay() -> list[dict]
- close()

Two implementations shipped:
- MqAdapterStub  (in-memory, no broker required)
- MqAdapterNats  (NATS JetStream, production)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Callable


class AckLevel:
    """ACK level constants — mirrored from adapter stub for API compatibility."""
    BROKER_RECEIVED = "broker_received"
    BROKER_PUBLISHED = "broker_published"
    CONSUMER_INTAKE = "consumer_intake"
    CONSUMER_CLAIMED = "consumer_claimed"


@dataclass
class RetryConfig:
    """Configuration for bounded retry behavior."""
    max_attempts: int = 3
    initial_backoff_ms: int = 1000
    max_backoff_ms: int = 10000
    backoff_multiplier: float = 2.0
    backoff_type: str = "exponential"  # "exponential" | "linear"


@dataclass
class DlqEvent:
    """Dead Letter Queue event — emitted when retry limit is exhausted."""
    event_id: str = field(default_factory=lambda: f"dlq-{uuid_module.uuid4().hex[:12]}")
    message_id: str = ""
    workflow_instance_id: str = ""
    original_payload: dict = field(default_factory=dict)
    attempts_exhausted: int = 0
    last_error: str = ""
    dlq_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


import uuid as uuid_module


class MqAdapter(ABC):
    """
    Abstract MQ adapter interface.

    Design rule: the application logic above this interface never changes
    when switching from stub to real broker. Only the adapter implementation changes.
    """

    @abstractmethod
    def publish(self, envelope: dict) -> dict:
        """Publish a message. Returns ACK at broker_received level."""

    @abstractmethod
    def consume(self) -> Optional[dict]:
        """Consume the next available message. Returns None if queue is empty."""

    @abstractmethod
    def consume_by_id(self, message_id: str) -> Optional[dict]:
        """Consume a specific message by message_id."""

    @abstractmethod
    def ack(self, message_id: str, level: str = "consumer_intake") -> dict:
        """Issue an ACK at the specified level."""

    @abstractmethod
    def retry_with_dlq(
        self,
        message_id: str,
        workflow_instance_id: str,
        payload: dict,
        simulate_failure: Callable[[], bool],
        on_retry: Optional[Callable[[int], None]] = None,
    ) -> DlqEvent:
        """Attempt message processing with bounded retry and DLQ on exhaustion."""

    @abstractmethod
    def emit_dlq(
        self,
        message_id: str,
        workflow_instance_id: str,
        attempts: int,
        last_error: str,
        original_payload: dict,
    ) -> DlqEvent:
        """Emit a Dead Letter Queue event when retry limit is exhausted."""

    @abstractmethod
    def compute_backoff(self, attempt: int) -> float:
        """Compute backoff delay in seconds for a given attempt number."""

    @abstractmethod
    def get_dlq_events(self) -> list[DlqEvent]:
        """Return all DLQ events emitted so far."""

    @abstractmethod
    def get_ack_log(self) -> list[dict]:
        """Return all ACKs logged so far."""

    @abstractmethod
    def replay(self) -> list[dict]:
        """Replay all messages from the beginning (for recovery scenarios)."""

    @abstractmethod
    def close(self):
        """Close the adapter and release resources."""