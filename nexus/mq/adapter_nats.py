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
import asyncio
import json
import time
import threading
import uuid

from nexus.mq.protocol import ProtocolEnvelope
from nexus.mq.protocol_routing import route_execution_envelope_dict, route_protocol_envelope

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
        stream_subjects: Optional[list[str]] = None,
        consumer_name: Optional[str] = None,
        consumer_filter_subject: Optional[str] = None,
        enable_protocol_subjects: bool = False,
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
        self._consumer_filter_subject = consumer_filter_subject
        self._enable_protocol_subjects = enable_protocol_subjects
        if stream_subjects:
            self._stream_subjects = list(stream_subjects)
        else:
            self._stream_subjects = [f"{self._subject_prefix}.>"]
            if self._enable_protocol_subjects:
                self._stream_subjects.extend(
                    [
                        "agent.>",
                        "workflow.>",
                        "review.>",
                        "feedback.>",
                        "ops.>",
                    ]
                )

        self._nc = None        # nats connection
        self._js = None        # JetStream context
        self._dlq_events: list[DlqEvent] = []
        self._ack_log: list[dict] = []
        self._connected = False
        self._pull_sub = None  # shared pull subscription (reused on reconnect)
        self._pending_acks: dict[str, object] = {}
        self._loop = None      # persistent event loop for sync methods
        self._loop_thread = None
        self._loop_ready = None
        self._consumer_name = consumer_name or "nexus-mq-consumer"  # durable consumer name (shared across instances)

    # ── connection ───────────────────────────────────────────────────────────

    async def _ensure_connection(self):
        """Lazily connect + ensure JetStream + ensure streams exist."""
        if self._nc is not None and self._connected:
            return

        try:
            self._nc = await nats.connect(self._nats_url, connect_timeout=5, max_reconnect_attempts=3)
            self._js = self._nc.jetstream()
        except ConnectionFailure as e:
            raise ConnectionError(f"NATS connection failed to {self._nats_url}: {e}")

        self._connected = True

        try:
            await self._js.add_stream(
                name=self._stream_name,
                subjects=self._stream_subjects,
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

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        """Create one dedicated background event loop for all sync operations."""
        if self._loop is not None and not self._loop.is_closed() and self._loop_thread and self._loop_thread.is_alive():
            return self._loop

        self._loop = asyncio.new_event_loop()
        self._loop_ready = threading.Event()

        def _run_loop():
            asyncio.set_event_loop(self._loop)
            self._loop_ready.set()
            self._loop.run_forever()

        self._loop_thread = threading.Thread(
            target=_run_loop,
            name="MqAdapterNatsLoop",
            daemon=True,
        )
        self._loop_thread.start()
        self._loop_ready.wait()
        return self._loop

    def _run_sync(self, coro):
        """Run adapter coroutines on the dedicated background loop from any caller context."""
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()

    def publish(self, envelope: dict) -> dict:
        """Sync wrapper for publish (delegates to async implementation)."""
        return self._run_sync(self._publish_impl(envelope))

    async def _publish_impl(self, envelope: dict) -> dict:
        subject = self._resolve_subject(envelope)
        await self._ensure_connection()

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
            "nats_seq": ack.seq,
            "subject": subject,
            "not_business_completion": True,
        }
        self._ack_log.append(ack_result)
        return ack_result

    def _resolve_subject(self, envelope: dict) -> str:
        if envelope.get("protocol_version"):
            protocol_envelope = ProtocolEnvelope.from_dict(envelope)
            routed = route_protocol_envelope(protocol_envelope)
            if routed.valid and routed.subject:
                return routed.subject
        if envelope.get("message_type"):
            routed = route_execution_envelope_dict(envelope)
            if routed.valid and routed.subject:
                return routed.subject
            if _is_agent_transport_envelope(envelope):
                raise ValueError(f"AGENT_TRANSPORT_ROUTING_INVALID: {routed.errors or []}")
        return f"{self._subject_prefix}.{envelope.get('message_type', 'unknown').lower()}"

    # ── consume ───────────────────────────────────────────────────────────────

    async def _consume_impl(self, timeout_ms: int = 5000) -> Optional[dict]:
        """
        Async consume: pull one message from JetStream using a durable named pull-subscribe.
        The durable consumer persists on the server and survives adapter restarts,
        allowing subsequent adapter instances to resume from where the last left off.
        """
        await self._ensure_connection()

        try:
            # Reuse existing or create new shared pull subscription
            if self._pull_sub is None:
                self._pull_sub = await self._js.pull_subscribe(
                    subject=self._consumer_filter_subject or "",
                    stream=self._stream_name,
                    durable=self._consumer_name,  # durable — survives reconnects
                )

            # Fetch up to 1 message with timeout
            msgs = await self._pull_sub.fetch(batch=1, timeout=timeout_ms / 1000)
            if msgs:
                msg = msgs[0]
                envelope = json.loads(msg.data.decode('utf-8'))
                msg_id = envelope.get("message_id", "")
                if msg_id:
                    self._pending_acks[msg_id] = msg
                return {"envelope": envelope, "subject": msg.subject, "status": "delivered", "broker_ack_pending": bool(msg_id)}
        except Exception:
            pass

        return None

    def consume(self, timeout_ms: int = 5000) -> Optional[dict]:
        """Consume the next available message. Returns None if queue is empty."""
        return self._run_sync(self._consume_impl(timeout_ms))

    def consume_by_id(self, message_id: str) -> Optional[dict]:
        """
        Consume a specific message by message_id using JetStream get_msg by sequence.
        Scans stream from the end (most recent first).
        """
        return self._run_sync(self._consume_by_id_impl(message_id))

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
                    return {"envelope": envelope, "subject": msg.subject, "status": "delivered"}
            except Exception:
                continue

        return None

    # ── ack ─────────────────────────────────────────────────────────────────

    async def _ack_impl(self, message_id: str, level: str = "consumer_intake") -> dict:
        """Async ACK: log the ack event."""
        broker_acknowledged = False
        pending = self._pending_acks.pop(message_id, None)
        if pending is not None:
            await pending.ack()
            broker_acknowledged = True
        ack = {
            "ack_level": level,
            "message_id": message_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "broker_acknowledged": broker_acknowledged,
            "broker_ack_boundary": "after_durable_intake",
            "not_business_completion": True,
        }
        self._ack_log.append(ack)
        return ack

    def ack(self, message_id: str, level: str = "consumer_intake") -> dict:
        """
        Issue an ACK at the specified level.
        Design rule: ACK means intake only — never workflow state change.
        """
        return self._run_sync(self._ack_impl(message_id, level))

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
        self._run_sync(self._emit_dlq_impl(message_id, workflow_instance_id, attempts, last_error, original_payload))

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
                messages.append({"envelope": envelope, "subject": msg.subject, "seq": seq})
            except Exception:
                continue

        return messages

    def replay(self) -> list[dict]:
        """Replay all messages from the stream (for recovery scenarios)."""
        return self._run_sync(self._replay_impl())

    # ── accessors ────────────────────────────────────────────────────────────

    def get_dlq_events(self) -> list[DlqEvent]:
        return list(self._dlq_events)

    def get_ack_log(self) -> list[dict]:
        return list(self._ack_log)

    def broker_policy_evidence(self) -> dict:
        return {
            "adapter": "nats_jetstream",
            "nats_url": self._redacted_nats_url(),
            "stream_name": self._stream_name,
            "stream_subjects": list(self._stream_subjects),
            "dlq_stream_name": self._dlq_stream_name,
            "dlq_subject": self._dlq_subject,
            "consumer_name": self._consumer_name,
            "consumer_filter_subject": self._consumer_filter_subject,
            "consumer_policy": {
                "durable_name": self._consumer_name,
                "ack_policy": "explicit",
                "ack_boundary": "consumer_intake_only",
            },
            "dlq_distinct_from_handler_exhausted": True,
            "live_mutation_required_for_evidence": False,
            "not_business_completion": True,
        }

    def health_probe(self) -> dict:
        return {
            "component": "nats_jetstream",
            "status": "healthy" if self._connected else "degraded",
            "stream_name": self._stream_name,
            "consumer_name": self._consumer_name,
            "connected": self._connected,
            "not_business_completion": True,
        }

    def _redacted_nats_url(self) -> str:
        if "@" not in self._nats_url:
            return self._nats_url
        scheme, rest = self._nats_url.split("://", 1) if "://" in self._nats_url else ("", self._nats_url)
        host = rest.split("@", 1)[1]
        return f"{scheme}://***@{host}" if scheme else f"***@{host}"

    def _resolve_subject(self, envelope: dict) -> str:
        if envelope.get("protocol_version"):
            try:
                protocol_envelope = ProtocolEnvelope.from_dict(envelope)
                routed = route_protocol_envelope(protocol_envelope)
                if routed.valid and routed.subject:
                    return routed.subject
            except Exception:
                pass

        if envelope.get("message_type"):
            try:
                routed = route_execution_envelope_dict(envelope)
                if routed.valid and routed.subject:
                    return routed.subject
                if _is_agent_transport_envelope(envelope):
                    raise ValueError(f"AGENT_TRANSPORT_ROUTING_INVALID: {routed.errors or []}")
            except ValueError:
                raise
            except Exception:
                pass

        return f"{self._subject_prefix}.{envelope.get('message_type', 'unknown').lower()}"

    # ── close ────────────────────────────────────────────────────────────────

    async def _close_impl(self):
        """Release local adapter resources without mutating shared broker state."""
        if self._pull_sub:
            try:
                await self._pull_sub.unsubscribe()
            except Exception:
                pass
            self._pull_sub = None
        self._pending_acks.clear()
        if self._nc:
            await self._nc.close()

    def close(self):
        """Close the adapter connection and local loop resources."""
        try:
            if self._nc is not None:
                self._run_sync(self._close_impl())
        except Exception:
            pass
        finally:
            self._connected = False
            self._nc = None
            self._js = None
            self._pull_sub = None
            if self._loop is not None and not self._loop.is_closed():
                self._loop.call_soon_threadsafe(self._loop.stop)
            if self._loop_thread and self._loop_thread.is_alive():
                self._loop_thread.join(timeout=2)
            if self._loop is not None and not self._loop.is_closed():
                self._loop.close()
            self._loop = None
            self._loop_thread = None
            self._loop_ready = None


def _is_agent_transport_envelope(envelope: dict) -> bool:
    return envelope.get("workflow_type") == "agent_transport"
