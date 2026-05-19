from nexus.mq.agent_registry_service import AgentRegistryService
from nexus.mq.agent_registry_store import FakeAgentRegistryStore
from nexus.mq.tests.test_agent_registry_persistence import NOW, _record


def test_revision_compare_and_set_rejects_stale_write():
    store = FakeAgentRegistryStore()
    service = AgentRegistryService(store)
    created = service.register_or_refresh(_record(), now_at=NOW)

    stale = service.register_or_refresh(
        _record(load_score=0.4),
        expected_revision=created.revision - 1,
        now_at=NOW,
    )
    current = service.read_registry_record("jarvis", now_at=NOW)

    assert stale.accepted is False
    assert "STALE_REVISION" in stale.errors
    assert current.revision == 1
    assert current.record.load_score == 0.0


def test_same_runtime_refresh_is_idempotent_for_unchanged_record():
    store = FakeAgentRegistryStore()
    service = AgentRegistryService(store)
    record = _record()
    created = service.register_or_refresh(record, now_at=NOW)

    refreshed = service.register_or_refresh(record, expected_revision=created.revision, now_at=NOW)

    assert refreshed.accepted is True
    assert refreshed.revision == created.revision
    assert store.list_events()[-1].event_type == "registry_record_unchanged"


def test_runtime_instance_conflict_is_rejected_and_existing_record_can_be_quarantined():
    store = FakeAgentRegistryStore()
    service = AgentRegistryService(store)
    created = service.register_or_refresh(_record(), now_at=NOW)

    conflict = service.register_or_refresh(
        _record(runtime_instance_id="jarvis-runtime-other"),
        expected_revision=created.revision,
        now_at=NOW,
    )
    quarantined = service.quarantine_agent(
        "jarvis",
        reason="runtime_instance_conflict",
        expected_revision=created.revision,
        now_at="2026-05-19T00:01:00+00:00",
    )

    assert conflict.accepted is False
    assert "RUNTIME_INSTANCE_CONFLICT" in conflict.errors
    assert quarantined.accepted is True
    assert quarantined.revision == created.revision + 1
    assert quarantined.record.initialization_status == "quarantined"
    assert quarantined.record.presence_state == "offline"
    assert quarantined.record.accepting_new_work is False
    assert quarantined.record.readiness_blocker == "runtime_instance_conflict"
    assert store.list_events()[-1].event_type == "registry_record_quarantined"
