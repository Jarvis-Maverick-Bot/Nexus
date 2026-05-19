from nexus.mq.agent_registry_service import AgentRegistryService
from nexus.mq.agent_registry_store import (
    FakeAgentRegistryStore,
    REGISTRY_RECORD_SCHEMA_VERSION,
    record_to_normalized_row,
)
from nexus.mq.tests.test_agent_registry_persistence import NOW, _record


def test_malformed_individual_row_is_rejected_for_that_agent_only():
    store = FakeAgentRegistryStore()
    good = _record(agent_id="ready", runtime_instance_id="ready-runtime")
    bad_row = {
        "schema_version": REGISTRY_RECORD_SCHEMA_VERSION,
        "store_revision": 1,
        "agent_id": "bad",
        "runtime_instance_id": "bad-runtime",
        "registry_status": "active",
        "initialization_status": "ready",
        "startup_packet_expires_at": "2026-05-19T01:00:00+00:00",
        "revision": 1,
        "payload_schema_version": REGISTRY_RECORD_SCHEMA_VERSION,
        "payload": {"schema_version": REGISTRY_RECORD_SCHEMA_VERSION},
    }
    store.seed_raw_row(record_to_normalized_row(good, revision=1))
    store.seed_raw_row(bad_row)
    service = AgentRegistryService(store)

    loaded = service.load_registry_records(now_at=NOW)

    assert loaded.store_fail_closed is False
    assert [item.record.agent_id for item in loaded.records] == ["ready"]
    assert "bad" in loaded.rejected_agents
    assert any(error.startswith("MALFORMED_REGISTRY_ROW") for error in loaded.rejected_agents["bad"])


def test_corrupted_store_schema_rejects_whole_registry_load():
    store = FakeAgentRegistryStore()
    store.seed_raw_row(record_to_normalized_row(_record(), revision=1))
    store.corrupt_store_for_test()
    service = AgentRegistryService(store)

    loaded = service.load_registry_records(now_at=NOW)
    read = service.read_registry_record("jarvis", now_at=NOW)

    assert loaded.store_fail_closed is True
    assert loaded.records == []
    assert "REGISTRY_STORE_CORRUPTED" in loaded.store_errors
    assert read.accepted is False
    assert "REGISTRY_STORE_CORRUPTED" in read.errors


def test_expired_startup_packet_fails_closed_on_write_and_read():
    expired = _record(startup_packet_expires_at="2026-05-18T23:59:00+00:00")
    store = FakeAgentRegistryStore()
    service = AgentRegistryService(store)

    write = service.register_or_refresh(expired, now_at=NOW)
    store.seed_raw_row(record_to_normalized_row(expired, revision=1))
    loaded = service.load_registry_records(now_at=NOW)

    assert write.accepted is False
    assert "STARTUP_PACKET_EXPIRED" in write.errors
    assert loaded.records == []
    assert "STARTUP_PACKET_EXPIRED" in loaded.rejected_agents["jarvis"]
