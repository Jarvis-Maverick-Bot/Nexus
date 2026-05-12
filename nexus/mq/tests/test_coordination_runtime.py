"""Coordination runtime tests for durable intake, callback, and timeout behavior."""

from datetime import datetime, timedelta, timezone
import os

from nexus.mq.coordination_runtime import CoordinationRuntime
from nexus.mq.protocol import build_protocol_envelope


def _identity_config_path() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "agents.yaml")
    )


def _future_iso(minutes: int = 5) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def _past_iso(minutes: int = 5) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def test_runtime_startup_sets_active_status(tmp_path):
    runtime = CoordinationRuntime.from_paths(
        runtime_id="maverick-runtime-001",
        agent_id="maverick",
        role="maverick",
        db_path=tmp_path / "runtime.sqlite3",
        identity_yaml_path=_identity_config_path(),
    )

    status = runtime.startup()
    restored = runtime.state_store.get_runtime_status("maverick-runtime-001")
    runtime.close()

    assert status.status == "ACTIVE"
    assert restored is not None
    assert restored.status == "ACTIVE"


def test_runtime_intake_records_pending_task_and_allows_ack(tmp_path):
    runtime = CoordinationRuntime.from_paths(
        runtime_id="viper-runtime-001",
        agent_id="viper",
        role="viper",
        db_path=tmp_path / "runtime.sqlite3",
        identity_yaml_path=_identity_config_path(),
    )
    runtime.startup()
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

    result = runtime.intake_inbound_message("agent.viper.inbox", request.to_dict())
    stored = runtime.state_store.get_pending_task(f"task-{request.message_id}")
    runtime.close()

    assert result.valid is True
    assert result.ack_allowed is True
    assert result.duplicate is False
    assert stored is not None
    assert stored.correlation_id == request.correlation_id
    assert stored.reply_to_subject == "agent.maverick.callbacks"


def test_runtime_callback_wait_matches_valid_reply(tmp_path):
    runtime = CoordinationRuntime.from_paths(
        runtime_id="maverick-runtime-001",
        agent_id="maverick",
        role="maverick",
        db_path=tmp_path / "runtime.sqlite3",
        identity_yaml_path=_identity_config_path(),
    )
    runtime.startup()
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
    wait = runtime.register_callback_wait(request)
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
        idempotency_key="result:viper:test-001",
    )

    result = runtime.receive_callback("agent.maverick.callbacks", reply.to_dict())
    restored_wait = runtime.state_store.get_callback_wait(wait.callback_id)
    runtime.close()

    assert result.valid is True
    assert result.ack_allowed is True
    assert result.matched is True
    assert restored_wait is not None
    assert restored_wait.state == "RECEIVED"
    assert restored_wait.response_payload["message_id"] == reply.message_id


def test_runtime_rejects_orphan_callback(tmp_path):
    runtime = CoordinationRuntime.from_paths(
        runtime_id="maverick-runtime-001",
        agent_id="maverick",
        role="maverick",
        db_path=tmp_path / "runtime.sqlite3",
        identity_yaml_path=_identity_config_path(),
    )
    runtime.startup()
    orphan = build_protocol_envelope(
        message_type="result",
        source_agent_id="viper",
        source_runtime_instance_id="viper-windows-main-20260507",
        source_role="viper",
        authority_scope="workflow.result",
        payload={"status": "ok"},
        target_agent_id="maverick",
        reply_to_subject="agent.maverick.callbacks",
        correlation_id="corr-orphan-001",
        causation_id="missing-request-001",
        idempotency_key="result:viper:orphan-001",
    )

    result = runtime.receive_callback("agent.maverick.callbacks", orphan.to_dict())
    runtime.close()

    assert result.valid is False
    assert result.ack_allowed is False
    assert any("ORPHAN_CALLBACK" in error for error in result.errors)


def test_runtime_timeout_scan_emits_task_and_callback_timeouts(tmp_path):
    runtime = CoordinationRuntime.from_paths(
        runtime_id="maverick-runtime-001",
        agent_id="maverick",
        role="maverick",
        db_path=tmp_path / "runtime.sqlite3",
        identity_yaml_path=_identity_config_path(),
    )
    runtime.startup()
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

    result = runtime.scan_timeouts(now_at=datetime.now(timezone.utc).isoformat())
    runtime.close()

    assert runtime.timeout_subject() == "ops.timeout"
    assert len(result.task_timeout_envelopes) == 1
    assert len(result.callback_timeout_envelopes) == 1
    assert result.task_timeout_envelopes[0].message_type == "timeout"
    assert result.callback_timeout_envelopes[0].payload["record_type"] == "callback_wait"
