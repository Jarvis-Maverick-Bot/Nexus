"""Supervisor tests for the Phase 3 always-on listener runtime."""

from datetime import datetime, timedelta, timezone
import os

from nexus.mq.adapter import MqAdapterStub
from nexus.mq.listener_runtime import ListenerRuntime, ListenerRuntimeConfig
from nexus.mq.listener_supervisor import ListenerSupervisor, SupervisorConfig
from nexus.mq.protocol import build_protocol_envelope


def _identity_config_path() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "agents.yaml")
    )


def _future_iso(minutes: int = 5) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def _past_iso(minutes: int = 5) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def test_supervisor_runs_poll_timeout_and_reconcile_cycles(tmp_path):
    adapter = MqAdapterStub()
    listener = ListenerRuntime.from_paths(
        adapter=adapter,
        runtime_id="maverick-runtime-001",
        agent_id="maverick",
        role="maverick",
        db_path=tmp_path / "supervisor.sqlite3",
        identity_yaml_path=_identity_config_path(),
        config=ListenerRuntimeConfig(),
    )
    request = build_protocol_envelope(
        message_type="command",
        source_agent_id="maverick",
        source_runtime_instance_id="maverick-windows-main-20260507",
        source_role="maverick",
        authority_scope="workflow.command",
        payload={"command": "dispatch"},
        target_agent_id="maverick",
        reply_to_subject="agent.maverick.callbacks",
        causation_id=None,
        expires_at=_future_iso(),
    )
    adapter.publish(request.to_dict())
    listener.runtime.state_store.create_pending_task(
        task_type="command",
        subject="agent.maverick.inbox",
        correlation_id="corr-timeout-001",
        workflow_id="wf-timeout-001",
        payload={"command": "dispatch"},
        reply_to_subject="agent.viper.callbacks",
        created_by="maverick-runtime-001",
        deadline_at=_past_iso(),
    )
    supervisor = ListenerSupervisor(
        listener=listener,
        config=SupervisorConfig(timeout_every_cycles=2, reconcile_every_cycles=3),
    )

    summary = supervisor.run_cycles(total_cycles=3, now_at=datetime.now(timezone.utc).isoformat())
    timeout_messages = [msg for msg in adapter.replay() if msg["subject"] == "ops.timeout"]
    supervisor.close()

    assert summary.startup.runtime_status == "ACTIVE"
    assert len(summary.cycles) == 3
    assert summary.cycles[0].poll_status == "message_intake"
    assert summary.cycles[1].timeout_published >= 1
    assert len(timeout_messages) >= 1


def test_supervisor_stops_early_when_runtime_quarantined(tmp_path, monkeypatch):
    adapter = MqAdapterStub()
    listener = ListenerRuntime.from_paths(
        adapter=adapter,
        runtime_id="maverick-runtime-001",
        agent_id="maverick",
        role="maverick",
        db_path=tmp_path / "supervisor.sqlite3",
        identity_yaml_path=_identity_config_path(),
    )
    monkeypatch.setattr(
        listener.runtime.state_store,
        "verify_integrity",
        lambda: (False, ["simulated-integrity-failure"]),
    )
    supervisor = ListenerSupervisor(listener=listener)

    summary = supervisor.run_cycles(total_cycles=2)
    supervisor.close()

    assert summary.stopped_early is True
    assert summary.stop_reason == "runtime_quarantined"
    assert summary.startup.quarantined is True
