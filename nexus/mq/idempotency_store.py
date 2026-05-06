"""
MQ Idempotency Store — 3.5 Implementation
Deduplication of command/feedback messages by idempotency_key.

Design source: GOVERNED_WORKFLOW_RUNTIME_AND_MESSAGE_QUEUE_ARCHITECTURE_V0_1.md §5.3
Baseline status: accepted-for-skeleton (3.5 V1.1, commit 3f7a5a0)

Design rule: duplicate delivery must not duplicate side effects.
Every command/event/feedback uses idempotency_key; deduplication happens
BEFORE any side effects occur.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Any
import uuid


@dataclass
class IdempotencyRecord:
    """Record of a processed idempotency key."""
    key: str
    message_id: str
    workflow_instance_id: str
    result: str                    # "processed" | "duplicate_rejected"
    processed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    result_detail: Optional[str] = None


class IdempotencyStore:
    """
    Bounded idempotency store for deduplicating MQ messages.

    Design rule: deduplication must happen BEFORE any side effects.
    The idempotency check is the first gate before command handler execution.

    For skeleton: in-memory bounded store with a size limit.
    In production, this would be a durable store (Redis, DB, or NATS KV).
    """

    MAX_STORE_SIZE = 10000  # bounded for skeleton; prevents unbounded memory growth

    def __init__(self):
        self._store: dict[str, IdempotencyRecord] = {}
        self._eviction_order: list[str] = []  # simple LRU eviction order

    def is_duplicate(self, idempotency_key: str, message_id: str, workflow_instance_id: str) -> tuple[bool, Optional[IdempotencyRecord]]:
        """
        Check if an idempotency key has already been processed.

        Returns (is_duplicate, existing_record).
        If is_duplicate=True, the caller must NOT proceed with side effects.
        """
        if idempotency_key in self._store:
            record = self._store[idempotency_key]
            return True, record

        return False, None

    def record_processed(
        self,
        idempotency_key: str,
        message_id: str,
        workflow_instance_id: str,
        result: str = "processed",
        result_detail: Optional[str] = None,
    ) -> IdempotencyRecord:
        """
        Record that an idempotency key has been processed.

        Must be called AFTER successful commit boundary, not before.
        Design rule: record only after side effects are confirmed safe.
        """
        # Evict oldest if at capacity
        if len(self._store) >= self.MAX_STORE_SIZE:
            oldest = self._eviction_order.pop(0)
            del self._store[oldest]

        record = IdempotencyRecord(
            key=idempotency_key,
            message_id=message_id,
            workflow_instance_id=workflow_instance_id,
            result=result,
            result_detail=result_detail,
        )
        self._store[idempotency_key] = record
        self._eviction_order.append(idempotency_key)
        return record

    def get_record(self, idempotency_key: str) -> Optional[IdempotencyRecord]:
        return self._store.get(idempotency_key)

    def clear(self):
        self._store.clear()
        self._eviction_order.clear()

    def size(self) -> int:
        return len(self._store)


def test_command_idempotent_dedupe() -> bool:
    """
    Test: same idempotency_key delivered twice → one side effect only.

    Acceptance criteria: first message is processed, second message
    is detected as duplicate and rejected before any side effect.
    """
    store = IdempotencyStore()

    key = "cmd-wf001-retry-1"
    msg_id_1 = "msg-001"
    msg_id_2 = "msg-002"
    wf_id = "wf-001"

    # First message — not a duplicate
    is_dup, record = store.is_duplicate(key, msg_id_1, wf_id)
    assert is_dup is False, "First delivery must not be marked duplicate"
    assert record is None, "No record should exist yet"

    # Record the first as processed (simulate successful command execution)
    store.record_processed(key, msg_id_1, wf_id, result="processed")

    # Second message with same idempotency_key — must be detected as duplicate
    is_dup, record = store.is_duplicate(key, msg_id_2, wf_id)
    assert is_dup is True, "Second delivery with same idempotency_key must be marked duplicate"
    assert record is not None, "Duplicate record must be returned"
    assert record.result == "processed", "Duplicate record must show original result"
    assert record.message_id == msg_id_1, "Duplicate record must reference original message"

    return True
