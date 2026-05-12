"""Phase 3 listener runtime tests."""

from datetime import datetime, timedelta, timezone
import os

from nexus.mq.adapter import MqAdapterStub
from nexus.mq.coordination_runtime import CoordinationRuntime
from nexus.mq.listener_runtime import ListenerRuntime, ListenerRuntimeConfig
from nexus.mq.protocol import build_protocol_envelope


def _identity_config_path() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "agents.yaml")
    )


def _uat_identity_config_path() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "agents_uat.yaml")
    )


def _future_iso(minutes: int = 5) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def _past_iso(minutes: int = 5) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def _make_runtime(tmp_path, runtime_id: str, agent_id: str, role: str):
    return CoordinationRuntime.from_paths(
        runtime_id=runtime_id,
        agent_id=agent_id,
        role=role,
        db_path=tmp_path / f"{runtime_id}.sqlite3",
        identity_yaml_path=_identity_config_path(),
    )


def test_listener_startup_reconciles_outbox(tmp_path):
    adapter = MqAdapterStub()
    runtime = _make_runtime(tmp_path, "maverick-runtime-001", "maverick", "maverick")
    envelope = build_protocol_envelope(
        message_type="result",
        source_agent_id="maverick",
        source_runtime_instance_id="maverick-windows-main-20260507",
        source_role="maverick",
        authority_scope="workflow.result",
        payload={"status": "ok"},
        target_agent_id="viper",
        reply_to_subject="agent.viper.callbacks",
        correlation_id="corr-outbox-001",
        causation_id="msg-request-001",
        idempotency_key="outbox:maverick:001",
    )
    runtime.record_outbox_publish(envelope)
    listener = ListenerRuntime(adapter, runtime)

    result = listener.startup()
    replayed = adapter.consume()
    listener.close()

    assert result.runtime_status == "ACTIVE"
    assert result.reconciled_outbox_records == 1
    assert replayed is not None
    assert replayed["envelope"]["message_id"] == envelope.message_id


def test_listener_poll_once_intakes_and_acks_message(tmp_path):
    adapter = MqAdapterStub()
    runtime = _make_runtime(tmp_path, "viper-runtime-001", "viper", "viper")
    listener = ListenerRuntime(adapter, runtime)
    listener.startup()
    request = build_protocol_envelope(
        message_type="command",
        source_agent_id="maverick",
        source_runtime_instance_id="maverick-windows-main-20260507",
        source_role="maverick",
        authority_scope="workflow.command",
        payload={"command": "dispatch"},
        target_agent_id="viper",
        reply_to_subject="agent.maverick.callbacks",
        causation_id=None,
        expires_at=_future_iso(),
    )
    adapter.publish(request.to_dict())

    result = listener.poll_once()
    stored = runtime.state_store.get_pending_task(f"task-{request.message_id}")
    listener.close()

    assert result.status == "message_intake"
    assert result.acked is True
    assert stored is not None
    assert stored.correlation_id == request.correlation_id
    assert any(
        ack["ack_level"] == "consumer_intake" and ack["message_id"] == request.message_id
        for ack in adapter.get_ack_log()
    )


def test_listener_poll_once_receives_callback_and_acks(tmp_path):
    adapter = MqAdapterStub()
    runtime = _make_runtime(tmp_path, "maverick-runtime-001", "maverick", "maverick")
    listener = ListenerRuntime(adapter, runtime)
    listener.startup()
    request = build_protocol_envelope(
        message_type="command",
        source_agent_id="maverick",
        source_runtime_instance_id="maverick-windows-main-20260507",
        source_role="maverick",
        authority_scope="workflow.command",
        payload={"command": "dispatch"},
        target_agent_id="viper",
        reply_to_subject="agent.maverick.callbacks",
        causation_id=None,
        expires_at=_future_iso(),
    )
    runtime.register_callback_wait(request)
    reply = build_protocol_envelope(
        message_type="result",
        source_agent_id="viper",
        source_runtime_instance_id="viper-windows-main-20260507",
        source_role="viper",
        authority_scope="workflow.result",
        payload={"status": "ok"},
        target_agent_id="maverick",
        reply_to_subject="agent.maverick.callbacks",
        correlation_id=request.correlation_id,
        causation_id=request.message_id,
        idempotency_key="result:viper:listener-001",
    )
    adapter.publish(reply.to_dict())

    result = listener.poll_once()
    wait = runtime.state_store.get_callback_wait(f"wait-{request.message_id}")
    listener.close()

    assert result.status == "callback_received"
    assert result.acked is True
    assert wait is not None
    assert wait.state == "RECEIVED"


def test_listener_invalid_message_emits_anomaly(tmp_path):
    adapter = MqAdapterStub()
    runtime = _make_runtime(tmp_path, "viper-runtime-001", "viper", "viper")
    listener = ListenerRuntime(adapter, runtime)
    listener.startup()
    invalid = build_protocol_envelope(
        message_type="command",
        source_agent_id="unknown-agent",
        source_runtime_instance_id="ghost-runtime",
        source_role="ghost",
        authority_scope="workflow.command",
        payload={"command": "dispatch"},
        target_agent_id="viper",
        reply_to_subject="agent.ghost.callbacks",
        causation_id=None,
        expires_at=_future_iso(),
    )
    adapter.publish(invalid.to_dict())

    result = listener.poll_once()
    anomaly = adapter.consume()
    listener.close()

    assert result.status == "message_rejected"
    assert result.anomaly_published is True
    assert anomaly is not None
    assert anomaly["subject"] == "ops.anomaly"
    assert anomaly["envelope"]["message_type"] == "anomaly"


def test_listener_backlog_pause_skips_ack_for_new_business_message(tmp_path):
    adapter = MqAdapterStub()
    runtime = _make_runtime(tmp_path, "viper-runtime-001", "viper", "viper")
    runtime.state_store.create_pending_task(
        task_type="command",
        subject="agent.viper.inbox",
        correlation_id="corr-existing-001",
        workflow_id="wf-existing-001",
        payload={"command": "already-busy"},
        reply_to_subject="agent.maverick.callbacks",
        created_by="viper-runtime-001",
        deadline_at=_future_iso(),
    )
    listener = ListenerRuntime(adapter, runtime, ListenerRuntimeConfig(max_pending_tasks=1))
    listener.startup()
    request = build_protocol_envelope(
        message_type="command",
        source_agent_id="maverick",
        source_runtime_instance_id="maverick-windows-main-20260507",
        source_role="maverick",
        authority_scope="workflow.command",
        payload={"command": "dispatch"},
        target_agent_id="viper",
        reply_to_subject="agent.maverick.callbacks",
        causation_id=None,
        expires_at=_future_iso(),
    )
    adapter.publish(request.to_dict())

    result = listener.poll_once()
    listener.close()

    assert result.status == "backlog_paused"
    assert result.acked is False
    assert not any(
        ack["ack_level"] == "consumer_intake" and ack["message_id"] == request.message_id
        for ack in adapter.get_ack_log()
    )


def test_listener_emit_timeouts_publishes_timeout_messages(tmp_path):
    adapter = MqAdapterStub()
    runtime = _make_runtime(tmp_path, "maverick-runtime-001", "maverick", "maverick")
    listener = ListenerRuntime(adapter, runtime)
    listener.startup()
    runtime.state_store.create_pending_task(
        task_type="command",
        subject="agent.maverick.inbox",
        correlation_id="corr-timeout-001",
        workflow_id="wf-timeout-001",
        payload={"command": "dispatch"},
        reply_to_subject="agent.viper.callbacks",
        created_by="maverick-runtime-001",
        deadline_at=_past_iso(),
    )
    runtime.state_store.create_callback_wait(
        correlation_id="corr-timeout-002",
        expected_subject="agent.maverick.callbacks",
        expected_source_agent_id="viper",
        request_message_id="msg-timeout-002",
        task_id="task-timeout-002",
        payload={"command": "wait"},
        deadline_at=_past_iso(),
        created_by="maverick-runtime-001",
    )

    result = listener.emit_timeouts_once()
    first = adapter.consume()
    second = adapter.consume()
    listener.close()

    assert result.published_count == 2
    assert result.task_timeouts == 1
    assert result.callback_timeouts == 1
    assert first is not None and first["subject"] == "ops.timeout"
    assert second is not None and second["subject"] == "ops.timeout"


def test_listener_runtime_from_paths_supports_uat_identity_config(tmp_path):
    adapter = MqAdapterStub()
    listener = ListenerRuntime.from_paths(
        adapter=adapter,
        runtime_id="jarvis-runtime-001",
        agent_id="jarvis",
        role="jarvis",
        db_path=tmp_path / "jarvis-uat.sqlite3",
        identity_yaml_path=_uat_identity_config_path(),
        config=ListenerRuntimeConfig(),
    )
    startup = listener.startup()
    request = build_protocol_envelope(
        message_type="command",
        source_agent_id="nova",
        source_runtime_instance_id="nova-uat-main-20260508",
        source_role="nova",
        authority_scope="workflow.command",
        payload={"command": "formal_smoke_probe"},
        target_agent_id="jarvis",
        reply_to_subject="agent.nova.callbacks",
        causation_id=None,
        expires_at=_future_iso(),
    )
    adapter.publish(request.to_dict())

    result = listener.poll_once()
    stored = listener.runtime.state_store.get_pending_task(f"task-{request.message_id}")
    listener.close()

    assert startup.runtime_status == "ACTIVE"
    assert result.status == "message_intake"
    assert stored is not None
    assert stored.reply_to_subject == "agent.nova.callbacks"
