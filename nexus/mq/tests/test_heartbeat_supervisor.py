from nexus.mq.agent_registry_service import AgentRegistryService
from nexus.mq.agent_registry_store import FakeAgentRegistryStore
from nexus.mq.heartbeat_supervisor import HeartbeatSupervisor
from nexus.mq.tests.test_agent_registry_persistence import NOW, _record


def _supervisor_with_record(record=None):
    store = FakeAgentRegistryStore()
    service = AgentRegistryService(store)
    service.register_or_refresh(record or _record(), now_at=NOW)
    supervisor = HeartbeatSupervisor(
        agent_id="jarvis",
        runtime_instance_id="jarvis-runtime-001",
        registry_service=service,
    )
    return supervisor, service, store


def test_supervisor_does_not_start_without_active_ready_registry():
    supervisor, _service, _store = _supervisor_with_record(
        _record(initialization_status="not_started", startup_packet_ref=None, readiness_evidence_ref=None)
    )

    result = supervisor.startup(now_at=NOW)

    assert result.accepted is False
    assert result.supervisor_state == "stopped"
    assert "INITIALIZATION_NOT_READY: not_started" in result.errors


def test_supervisor_first_manual_cycle_updates_presence():
    supervisor, service, store = _supervisor_with_record()

    startup = supervisor.startup(now_at=NOW)
    cycle = supervisor.run_cycle(now_at=NOW, evidence_refs=["evidence://heartbeat/cycle-1"])
    read = service.read_registry_record("jarvis", now_at=NOW)

    assert startup.accepted is True
    assert cycle.accepted is True
    assert cycle.heartbeat_result.revision == 2
    assert read.record.presence_state == "idle"
    assert store.get_heartbeat_sequence("jarvis") == 1


def test_supervisor_restart_rereads_registry_sequence():
    supervisor, service, store = _supervisor_with_record()
    supervisor.startup(now_at=NOW)
    first = supervisor.run_cycle(now_at=NOW)
    restarted = HeartbeatSupervisor(
        agent_id="jarvis",
        runtime_instance_id="jarvis-runtime-001",
        registry_service=service,
    )

    startup = restarted.startup(now_at="2026-05-19T00:00:10+00:00")
    second = restarted.run_cycle(now_at="2026-05-19T00:00:10+00:00")

    assert first.accepted is True
    assert startup.accepted is True
    assert second.accepted is True
    assert store.get_heartbeat_sequence("jarvis") == 2


def test_supervisor_degraded_cycle_records_degraded_state_without_completion():
    supervisor, _service, _store = _supervisor_with_record()
    supervisor.startup(now_at=NOW)

    cycle = supervisor.run_cycle(
        now_at=NOW,
        health_summary_ref="evidence://heartbeat/health-warning",
    )

    assert cycle.accepted is True
    assert cycle.supervisor_state == "degraded"
    assert cycle.heartbeat_result.record.presence_state == "degraded"
    assert cycle.heartbeat_result.not_business_completion is True
