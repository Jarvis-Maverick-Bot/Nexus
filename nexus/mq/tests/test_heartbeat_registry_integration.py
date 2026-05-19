from nexus.mq.agent_registry_service import AgentRegistryService
from nexus.mq.agent_registry_store import FakeAgentRegistryStore
from nexus.mq.heartbeat_policy import HeartbeatPolicy
from nexus.mq.heartbeat_presence_writer import HeartbeatPresenceWriter, HeartbeatTtlEvaluator
from nexus.mq.tests.test_agent_registry_persistence import NOW, _record
from nexus.mq.tests.test_heartbeat_runtime import _packet


def _service_with_record(record=None):
    store = FakeAgentRegistryStore()
    service = AgentRegistryService(store)
    service.register_or_refresh(record or _record(), now_at=NOW)
    return service, store


def test_heartbeat_presence_writer_updates_only_presence_fields_through_registry_store():
    service, store = _service_with_record()
    writer = HeartbeatPresenceWriter(service, HeartbeatPolicy())

    result = writer.apply_heartbeat(_packet(load_score=0.25), now_at=NOW)
    read = service.read_registry_record("jarvis", now_at=NOW)

    assert result.accepted is True
    assert result.revision == 2
    assert read.record.presence_state == "idle"
    assert read.record.last_heartbeat_at == NOW
    assert read.record.load_score == 0.25
    assert read.record.capabilities == ["implementation"]
    assert read.record.authority_scopes == ["workflow.command"]
    assert store.get_heartbeat_sequence("jarvis") == 1
    assert result.event.event_type == "heartbeat_accepted"
    assert result.event.not_business_completion is True


def test_registry_unavailable_fails_closed_for_heartbeat_write():
    authoritative = FakeAgentRegistryStore()
    authoritative.upsert_record(_record(), now_at=NOW)
    cache_only = FakeAgentRegistryStore(authoritative=False)
    cache_only.seed_raw_row(authoritative.normalized_row("jarvis"))
    service = AgentRegistryService(cache_only)
    writer = HeartbeatPresenceWriter(service, HeartbeatPolicy())

    result = writer.apply_heartbeat(_packet(), now_at=NOW)

    assert result.accepted is False
    assert "REGISTRY_TRUTH_UNVERIFIED" in result.errors


def test_runtime_mismatch_rejects_presence_update():
    service, _store = _service_with_record()
    writer = HeartbeatPresenceWriter(service, HeartbeatPolicy())

    result = writer.apply_heartbeat(_packet(runtime_instance_id="other-runtime"), now_at=NOW)

    assert result.accepted is False
    assert "RUNTIME_INSTANCE_MISMATCH" in result.errors


def test_ttl_expiry_marks_stale_then_offline_and_blocks_new_work():
    original_heartbeat_at = "2026-05-19T00:00:00+00:00"
    service, store = _service_with_record(
        _record(last_heartbeat_at=original_heartbeat_at, heartbeat_ttl_seconds=10)
    )
    writer = HeartbeatPresenceWriter(service, HeartbeatPolicy())
    evaluator = HeartbeatTtlEvaluator(service, HeartbeatPolicy(stale_to_offline_grace_seconds=180))

    accepted = writer.apply_heartbeat(_packet(heartbeat_sequence=1), now_at=original_heartbeat_at)
    stale = evaluator.evaluate_agent("jarvis", now_at="2026-05-19T00:00:15+00:00")
    after_stale = service.read_registry_record("jarvis", now_at="2026-05-19T00:00:15+00:00")
    offline = evaluator.evaluate_agent("jarvis", now_at="2026-05-19T00:03:12+00:00")

    assert accepted.accepted is True
    assert store.get_heartbeat_sequence("jarvis") == 1
    assert stale.transitioned is True
    assert stale.record.presence_state == "stale"
    assert stale.record.accepting_new_work is False
    assert stale.record.last_heartbeat_at == original_heartbeat_at
    assert stale.record.updated_at == "2026-05-19T00:00:15+00:00"
    assert after_stale.record.last_heartbeat_at == original_heartbeat_at
    assert store.get_heartbeat_sequence("jarvis") == 1
    assert offline.transitioned is True
    assert offline.record.presence_state == "offline"
    assert offline.record.accepting_new_work is False
    assert offline.record.last_heartbeat_at == original_heartbeat_at
    assert store.get_heartbeat_sequence("jarvis") == 1


def test_drain_sets_accepting_new_work_false():
    service, _store = _service_with_record()
    writer = HeartbeatPresenceWriter(service, HeartbeatPolicy())

    result = writer.apply_heartbeat(
        _packet(desired_presence_state="draining", accepting_new_work=True),
        now_at=NOW,
    )

    assert result.accepted is True
    assert result.record.presence_state == "draining"
    assert result.record.accepting_new_work is False
