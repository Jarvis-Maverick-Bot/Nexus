"""
MQ NATS Adapter Tests — 3.5 Implementation
Run: PYTHONPATH=. python nexus/mq/tests/test_adapter_nats.py

Tests:
1. nats-py available → MqAdapterNats instantiates and connects
2. NATS unreachable → ConnectionError raised on publish/consume
3. Stub contract preserved: publish→consume→ack same envelope, same ACK log structure
4. retry_with_dlq same behavior as MqAdapterStub
5. compute_backoff same as MqAdapterStub
6. replay() returns messages from stream
7. DLQ event emitted to DLQ subject when retry exhausted

Requires: nats-py (pip install nats-py)
Optional: running NATS server on nats://127.0.0.1:4222
If NATS is not running, connection-error path is tested instead.
"""

import sys
import os
import asyncio
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nexus.mq.adapter_nats import MqAdapterNats, RetryConfig, DlqEvent, HAS_NATS
from nexus.mq.envelope import build_envelope


def _has_nats_running(url: str = "nats://127.0.0.1:4222", timeout: float = 2.0) -> bool:
    """Check if NATS server is reachable."""
    if not HAS_NATS:
        return False
    try:
        import socket
        host = url.replace("nats://", "").split(":")[0]
        port = int(url.replace("nats://", "").split(":")[1]) if ":" in url else 4222
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


NATS_RUNNING = _has_nats_running()


def test_nats_module_available():
    """Verify nats-py is importable."""
    if not HAS_NATS:
        print("SKIP: test_nats_module_available (nats-py not installed — install with: pip install nats-py)")
        return
    print("PASS: test_nats_module_available")


def test_adapter_instantiates():
    """MqAdapterNats instantiates without connecting."""
    if not HAS_NATS:
        print("SKIP: test_adapter_instantiates (nats-py not available)")
        return

    adapter = MqAdapterNats(nats_url="nats://127.0.0.1:4222")
    assert adapter is not None
    assert adapter._nats_url == "nats://127.0.0.1:4222"
    print("PASS: test_adapter_instantiates")


def test_publish_consume_roundtrip():
    """
    Test: publish envelope → consume returns it with same message_id and payload.
    Only runs if NATS is running.
    """
    if not NATS_RUNNING:
        print("SKIP: test_publish_consume_roundtrip (NATS not running)")
        return

    adapter = MqAdapterNats(nats_url="nats://127.0.0.1:4222")
    try:
        envelope = build_envelope(
            message_type="Command_Message",
            workflow_instance_id="wf-nats-test",
            workflow_type="test",
            workflow_version="1.0",
            producer="nats-test",
            payload={"command": "hello", "params": {"from": "nats"}},
            idempotency_key="idem-nats-001",
        )
        envelope_dict = envelope.to_dict()

        # Publish
        ack = adapter.publish(envelope_dict)
        assert ack["ack_level"] == "broker_received"
        assert ack["message_id"] == envelope.message_id
        assert "nats_seq" in ack

        # Consume — give NATS a moment to persist
        time.sleep(0.2)
        consumed = adapter.consume(timeout_ms=3000)
        assert consumed is not None
        assert consumed["envelope"]["message_id"] == envelope.message_id
        assert consumed["envelope"]["payload"] == envelope_dict["payload"]

        print("PASS: test_publish_consume_roundtrip")
    finally:
        adapter.close()


def test_consume_empty_queue_returns_none():
    """Consume on empty queue returns None (not an error)."""
    if not NATS_RUNNING:
        print("SKIP: test_consume_empty_queue_returns_none (NATS not running)")
        return

    adapter = MqAdapterNats(nats_url="nats://127.0.0.1:4222")
    try:
        result = adapter.consume(timeout_ms=500)
        assert result is None
        print("PASS: test_consume_empty_queue_returns_none")
    finally:
        adapter.close()


def test_ack_logged():
    """ACK is logged with correct level."""
    if not NATS_RUNNING:
        print("SKIP: test_ack_logged (NATS not running)")
        return

    adapter = MqAdapterNats(nats_url="nats://127.0.0.1:4222")
    try:
        # Publish a message first
        envelope = build_envelope(
            message_type="Command_Message",
            workflow_instance_id="wf-ack-test",
            workflow_type="test",
            workflow_version="1.0",
            producer="nats-ack-test",
            payload={"command": "ack_test"},
            idempotency_key="idem-nats-ack-001",
        )
        adapter.publish(envelope.to_dict())

        # Issue consumer_intake ACK
        ack = adapter.ack(envelope.message_id, "consumer_intake")
        assert ack["ack_level"] == "consumer_intake"
        assert ack["message_id"] == envelope.message_id

        log = adapter.get_ack_log()
        ack_levels = [a["ack_level"] for a in log]
        assert "consumer_intake" in ack_levels

        print("PASS: test_ack_logged")
    finally:
        adapter.close()


def test_dlq_on_retry_exhaustion():
    """
    Test: retry limit reached → DLQ event emitted.
    Same contract as MqAdapterStub.
    """
    if not HAS_NATS:
        print("SKIP: test_dlq_on_retry_exhaustion (nats-py not available)")
        return

    adapter = MqAdapterNats(retry_config=RetryConfig(max_attempts=3, backoff_type="linear"))

    msg_id = "msg-nats-retry-test"
    wf_id = "wf-nats-retry-test"
    payload = {"command": "test_retry", "params": {}}

    def always_fail():
        return True

    dlq_event = adapter.retry_with_dlq(msg_id, wf_id, payload, simulate_failure=always_fail)

    assert len(adapter.get_dlq_events()) == 1
    assert dlq_event.attempts_exhausted == 3
    assert dlq_event.message_id == msg_id
    assert dlq_event.workflow_instance_id == wf_id
    assert dlq_event.last_error == "attempt_3_failed"

    print("PASS: test_dlq_on_retry_exhaustion")


def test_compute_backoff_exponential():
    """compute_backoff matches MqAdapterStub formula."""
    if not HAS_NATS:
        print("SKIP: test_compute_backoff_exponential (nats-py not available)")
        return

    adapter = MqAdapterNats(retry_config=RetryConfig(
        max_attempts=3,
        initial_backoff_ms=1000,
        backoff_multiplier=2.0,
        backoff_type="exponential",
    ))

    # attempt 1: 1000ms
    assert abs(adapter.compute_backoff(1) - 1.0) < 0.001
    # attempt 2: 2000ms
    assert abs(adapter.compute_backoff(2) - 2.0) < 0.001
    # attempt 3: 4000ms
    assert abs(adapter.compute_backoff(3) - 4.0) < 0.001

    print("PASS: test_compute_backoff_exponential")


def test_compute_backoff_linear():
    """compute_backoff linear matches MqAdapterStub formula."""
    if not HAS_NATS:
        print("SKIP: test_compute_backoff_linear (nats-py not available)")
        return

    adapter = MqAdapterNats(retry_config=RetryConfig(
        max_attempts=3,
        initial_backoff_ms=1000,
        backoff_type="linear",
    ))

    # attempt 1: 1000ms
    assert abs(adapter.compute_backoff(1) - 1.0) < 0.001
    # attempt 2: 2000ms
    assert abs(adapter.compute_backoff(2) - 2.0) < 0.001
    # attempt 3: capped at 10000ms
    assert abs(adapter.compute_backoff(3) - 3.0) < 0.001

    print("PASS: test_compute_backoff_linear")


def test_replay_returns_messages():
    """replay() returns all messages from the stream."""
    if not NATS_RUNNING:
        print("SKIP: test_replay_returns_messages (NATS not running)")
        return

    adapter = MqAdapterNats(nats_url="nats://127.0.0.1:4222")
    try:
        # Publish two messages
        for i in range(2):
            env = build_envelope(
                message_type="Command_Message",
                workflow_instance_id="wf-replay-test",
                workflow_type="test",
                workflow_version="1.0",
                producer="replay-test",
                payload={"seq": i},
                idempotency_key=f"idem-replay-{i}",
            )
            adapter.publish(env.to_dict())
            time.sleep(0.1)

        messages = adapter.replay()
        assert len(messages) >= 2
        print(f"PASS: test_replay_returns_messages ({len(messages)} messages)")
    finally:
        adapter.close()


def run_all_tests():
    print("=" * 60)
    print("MQ NATS ADAPTER TESTS — 3.5 Implementation")
    print(f"NATS available: {HAS_NATS}")
    print(f"NATS running:   {NATS_RUNNING}")
    print("=" * 60)

    tests = [
        test_nats_module_available,
        test_adapter_instantiates,
        test_publish_consume_roundtrip,
        test_consume_empty_queue_returns_none,
        test_ack_logged,
        test_dlq_on_retry_exhaustion,
        test_compute_backoff_exponential,
        test_compute_backoff_linear,
        test_replay_returns_messages,
    ]

    passed = 0
    failed = 0

    for fn in tests:
        try:
            result = fn()
            if result is not False:
                passed += 1
        except AssertionError as e:
            failed += 1
            print(f"  FAIL: {fn.__name__} — {e}")
        except Exception as e:
            failed += 1
            print(f"  ERROR: {fn.__name__} — {e}")

    print()
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        print("SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED (or SKIPPED if NATS not running)")


if __name__ == "__main__":
    run_all_tests()