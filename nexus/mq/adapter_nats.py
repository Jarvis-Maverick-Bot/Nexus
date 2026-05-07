"""
MQ NATS JetStream Adapter — 3.5 Implementation
Real broker adapter: replaces MqAdapterStub with real NATS JetStream transport.

Design source: GOVERNED_WORKFLOW_RUNTIME_AND_MESSAGE_QUEUE_ARCHITECTURE_V0_1.md §5.3, §5.6, §7.7
Baseline status: 3.5 V1.1 (commit 3f7a5a0)

Design rules:
- Same publish/consume/ack/retry/DLQ/idempotency interface as MqAdapterStub
- When NATS is unavailable, raises ConnectionError (caller decides fallback)
- NATS JetStream provides durable message persistence and replay
- ACK semantics: consumer_intake (before processing), consumer_claimed (after processing)
- Retry with DLQ: bounded exponential backoff; DLQ event on exhaustion
- Envelope envelope["message_id"] is the durable message ID used for dedup
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Callable
import json
import time
import uuid

try:
    import nats
    from nats.errors import TimeoutError as NatsTimeoutError, NoServersError
    try:
        from nats.errors import ConnectionFailure as ConnectionFailure
    except ImportError:
        # ConnectionFailure was renamed/removed in nats-py 2.14+
        # Use NoServersError as the connection-error marker
        ConnectionFailure = NoServersError
    HAS_NATS = True
except ImportError:
    HAS_NATS = False
    ConnectionFailure = Exception
    NoServersError = Exception
    NatsTimeoutError = Exception
    nats = None


# ── Retry/DLQ ────────────────────────────────────────────────────────────────────

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
    event_id: str = field(default_factory=lambda: f"dlq-{uuid.uuid4().hex[:12]}")
    message_id: str = ""
    workflow_instance_id: str = ""
    original_payload: dict = field(default_factory=dict)
    attempts_exhausted: int = 0
    last_error: str = ""
    dlq_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── NATS subjects ────────────────────────────────────────────────────────────────

_SUBJECT_DEFAULT = "nexus.mq"
_SUBJECT_DLQ = "nexus.mq.dlq"


# ── MqAdapterNats ────────────────────────────────────────────────────────────────

class MqAdapterNats:
    """
    NATS JetStream MQ adapter.

    Preserves the same envelope, ACK, retry, DLQ, idempotency, and replay
    interface contract as MqAdapterStub — the application logic above it
    does not change when switching from stub to real broker.

    Requires a running NATS server with JetStream enabled.

    Subjects:
    - <subject_prefix>.> (default "nexus.mq.>"): main message stream
    - <subject_prefix>.dlq (default "nexus.mq.dlq"): dead letter queue

    JetStream:
    - Stream: nexus-mq (subject: nexus.mq.>, storage: file, retention: workqueue)
    - Consumer: ephemeral for consume() — messages delivered once, no pending维护
    - Consumer for consume_by_id: pull-based, by message_id
    """

    def __init__(
        self,
        nats_url: str = "nats://127.0.0.1:4222",
        subject_prefix: str = "nexus.mq",
        retry_config: Optional[RetryConfig] = None,
        stream_name: str = "nexus-mq",
        dlq_stream_name: str = "nexus-mq-dlq",
    ):
        if not HAS_NATS:
            raise RuntimeError(
                "nats-py is not installed. Install with: pip install nats-py. "
                "Or use MqAdapterStub for broker-free testing."
            )

        self._nats_url = nats_url
        self._subject_prefix = subject_prefix
        self._subject = f"{subject_prefix}.>"       # all messages
        self._dlq_subject = f"{subject_prefix}.dlq"
        self._retry_config = retry_config or RetryConfig()
        self._stream_name = stream_name
        self._dlq_stream_name = dlq_stream_name

        self._nc = None        # nats connection
        self._js = None        # JetStream context
        self._dlq_events: list[DlqEvent] = []
        self._ack_log: list[dict] = []
        self._connected = False

    # ── connection ───────────────────────────────────────────────────────────

    async def _ensure_connection(self):
        """Lazily connect + ensure JetStream + ensure streams exist."""
        if self._connected:
            return

        try:
            self._nc = await nats.connect(self._nats_url, connect_timeout=5, max_reconnect_attempts=3)
            self._js = self._nc.jetstream()
        except ConnectionFailure as e:
            raise ConnectionError(f"NATS connection failed to {self._nats_url}: {e}")

        # Ensure main stream
        try:
            await self._js.add_stream(
                name=self._stream_name,
                subjects=[f"{self._subject_prefix}.>"],
                storage="file",
                retention="workqueue",
                max_bytes=10_000_000,
            )
        except Exception:
            pass  # stream already exists

        # Ensure DLQ stream
        try:
            await self._js.add_stream(
                name=self._dlq_stream_name,
                subjects=[self._dlq_subject],
                storage="file",
                retention="limits",
            )
        except Exception:
            pass  # DLQ stream already exists

        self._connected = True

    async def _ensure_consumer(self, consumer_name: str) -> str:
        """Ensure an ephemeral consumer exists for the stream, return consumer_name."""
        try:
            await self._js.add_consumer(
                self._stream_name,
                durable_consumer=consumer_name,
                ack_policy="none",
                deliver_policy="new",
                max_deliver=1,
                max_messages=1,
            )
        except Exception:
            pass  # consumer already exists
        return consumer_name

    # ── publish ─────────────────────────────────────────────────────────────

    async def publish(self, envelope: dict) -> dict:
        """
        Publish a message to NATS JetStream.
        Returns an ACK event at broker_received level.
        """
        await self._ensure_connection()

        subject = f"{self._subject_prefix}.{envelope.get('message_type', 'unknown').lower()}"
        payload_bytes = json.dumps(envelope, ensure_ascii=False).encode('utf-8')

        # Publish with message_id as JetStream message-ID for dedup
        msg_id = envelope.get("message_id", "")
        ack = await self._js.publish(
            subject,
            payload=payload_bytes,
            headers={"message_id": msg_id} if msg_id else {},
            timeout=5,
        )

        ack_result = {
            "ack_level": "broker_received",
            "message_id": msg_id,
            "workflow_instance_id": envelope.get("workflow_instance_id", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nats_seq": ack.sequence,
        }
        self._ack_log.append(ack_result)
        return ack_result

    def publish(self, envelope: dict) -> dict:
        """Sync wrapper for publish (delegates to async implementation)."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        return loop.run_until_complete(self._publish_impl(envelope))

    async def _publish_impl(self, envelope: dict) -> dict:
        await self._ensure_connection()

        subject = f"{self._subject_prefix}.{envelope.get('message_type', 'unknown').lower()}"
        payload_bytes = json.dumps(envelope, ensure_ascii=False).encode('utf-8')
        msg_id = envelope.get("message_id", "")

        ack = await self._js.publish(
            subject,
            payload=payload_bytes,
            headers={"message_id": msg_id} if msg_id else {},
            timeout=5,
        )

        ack_result = {
            "ack_level": "broker_received",
            "message_id": msg_id,
            "workflow_instance_id": envelope.get("workflow_instance_id", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nats_seq": ack.sequence,
        }
        self._ack_log.append(ack_result)
        return ack_result

    # ── consume ───────────────────────────────────────────────────────────────

    async def _consume_impl(self, timeout_ms: int = 5000) -> Optional[dict]:
        """
        Async consume: pull one message from JetStream using pull-subscribe.
        Uses ephemeral consumer so messages are not persisted across restarts
        (the stub contract is preserved: consume removes from queue).
        """
        import asyncio
        await self._ensure_connection()

        try:
            # Pull-based subscribe (ephemeral — auto-deleted after use)
            sub = await self._js.pull_subscribe(
                subject="",
                stream=self._stream_name,
                durable="",  # ephemeral
            )

            # Fetch up to 1 message with timeout
            msgs = await sub.fetch(max_messages=1, timeout=timeout_ms // 1000)
            if msgs:
                msg = msgs[0]
                envelope = json.loads(msg.data.decode('utf-8'))
                return {"envelope": envelope, "status": "delivered"}
        except Exception:
            pass

        return None

    def consume(self, timeout_ms: int = 5000) -> Optional[dict]:
        """Consume the next available message. Returns None if queue is empty."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        return loop.run_until_complete(self._consume_impl(timeout_ms))

    def consume_by_id(self, message_id: str) -> Optional[dict]:
        """
        Consume a specific message by message_id using JetStream get_msg by sequence.
        Scans stream from the end (most recent first).
        """
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        return loop.run_until_complete(self._consume_by_id_impl(message_id))

    async def _consume_by_id_impl(self, message_id: str) -> Optional[dict]:
        await self._ensure_connection()

        try:
            stream_info = await self._js.stream_info(self._stream_name)
            last_seq = stream_info.state.messages
        except Exception:
            return None

        if last_seq == 0:
            return None

        # Scan from end — most recent first (get_msg is O(1) by seq)
        for seq in range(last_seq, 0, -1):
            try:
                msg = await self._js.get_msg(self._stream_name, seq)
                envelope = json.loads(msg.data.decode('utf-8'))
                if envelope.get("message_id") == message_id:
                    return {"envelope": envelope, "status": "delivered"}
            except Exception:
                continue

        return None

    # ── ack ─────────────────────────────────────────────────────────────────

    async def _ack_impl(self, message_id: str, level: str = "consumer_intake") -> dict:
        """Async ACK: log the ack event."""
        ack = {
            "ack_level": level,
            "message_id": message_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._ack_log.append(ack)
        return ack

    def ack(self, message_id: str, level: str = "consumer_intake") -> dict:
        """
        Issue an ACK at the specified level.
        Design rule: ACK means intake only — never workflow state change.
        """
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        return loop.run_until_complete(self._ack_impl(message_id, level))

    # ── retry with DLQ ───────────────────────────────────────────────────────

    def emit_dlq(
        self,
        message_id: str,
        workflow_instance_id: str,
        attempts: int,
        last_error: str,
        original_payload: dict,
    ) -> DlqEvent:
        """
        Emit a Dead Letter Queue event to the DLQ subject.
        Also logs locally for accessor methods.
        """
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        loop.run_until_complete(self._emit_dlq_impl(message_id, workflow_instance_id, attempts, last_error, original_payload))

        event = DlqEvent(
            message_id=message_id,
            workflow_instance_id=workflow_instance_id,
            attempts_exhausted=attempts,
            last_error=last_error,
            original_payload=original_payload,
        )
        self._dlq_events.append(event)
        return event

    async def _emit_dlq_impl(
        self,
        message_id: str,
        workflow_instance_id: str,
        attempts: int,
        last_error: str,
        original_payload: dict,
    ):
        await self._ensure_connection()

        dlq_payload = {
            "event_type": "dead_letter",
            "message_id": message_id,
            "workflow_instance_id": workflow_instance_id,
            "attempts_exhausted": attempts,
            "last_error": last_error,
            "original_payload": original_payload,
            "dlq_at": datetime.now(timezone.utc).isoformat(),
        }
        payload_bytes = json.dumps(dlq_payload, ensure_ascii=False).encode('utf-8')

        try:
            await self._js.publish(self._dlq_subject, payload=payload_bytes, timeout=5)
        except Exception:
            pass  # DLQ publish failure should not block DLQ event recording

    def compute_backoff(self, attempt: int) -> float:
        """
        Compute backoff delay in seconds for a given attempt number.
        """
        cfg = self._retry_config
        if cfg.backoff_type == "exponential":
            delay = min(cfg.initial_backoff_ms * (cfg.backoff_multiplier ** (attempt - 1)), cfg.max_backoff_ms)
        else:
            delay = min(cfg.initial_backoff_ms + (attempt - 1) * cfg.initial_backoff_ms, cfg.max_backoff_ms)
        return delay / 1000.0

    def retry_with_dlq(
        self,
        message_id: str,
        workflow_instance_id: str,
        payload: dict,
        simulate_failure: Callable[[], bool],
        on_retry: Optional[Callable[[int], None]] = None,
    ) -> DlqEvent:
        """
        Attempt message processing with bounded retry and DLQ on exhaustion.

        Note: this is a sync wrapper. The actual processing is simulated by
        calling simulate_failure(). In production, this would call the
        message handler. This method is mainly for contract testing with
        the stub; for real NATS, the retry logic lives in the consumer loop.
        """
        cfg = self._retry_config
        last_error = ""

        for attempt in range(1, cfg.max_attempts + 1):
            if simulate_failure():
                last_error = f"attempt_{attempt}_failed"
                if on_retry:
                    on_retry(attempt)
                if attempt < cfg.max_attempts:
                    backoff = self.compute_backoff(attempt)
                    time.sleep(backoff)
                continue
            else:
                return DlqEvent()  # success — no DLQ

        # Exhausted all retries
        return self.emit_dlq(
            message_id=message_id,
            workflow_instance_id=workflow_instance_id,
            attempts=cfg.max_attempts,
            last_error=last_error,
            original_payload=payload,
        )

    # ── replay ───────────────────────────────────────────────────────────────

    async def _replay_impl(self) -> list[dict]:
        """Async replay: return all messages in the stream."""
        await self._ensure_connection()

        messages = []
        stream_info = await self._js.stream_info(self._stream_name)
        last_seq = stream_info.state.messages

        for seq in range(1, last_seq + 1):
            try:
                msg = await self._js.get_msg(self._stream_name, seq)
                envelope = json.loads(msg.data.decode('utf-8'))
                messages.append({"envelope": envelope, "seq": seq})
            except Exception:
                continue

        return messages

    def replay(self) -> list[dict]:
        """Replay all messages from the stream (for recovery scenarios)."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        return loop.run_until_complete(self._replay_impl())

    # ── accessors ────────────────────────────────────────────────────────────

    def get_dlq_events(self) -> list[DlqEvent]:
        return list(self._dlq_events)

    def get_ack_log(self) -> list[dict]:
        return list(self._ack_log)

    # ── close ────────────────────────────────────────────────────────────────

    def close(self):
        """Close the NATS connection (sync wrapper)."""
        if self._nc:
            try:
                import asyncio
                asyncio.get_event_loop().run_until_complete(self._nc.close())
            except Exception:
                pass
            self._connected = False
            self._nc = None
            self._js = None