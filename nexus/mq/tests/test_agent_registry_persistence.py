from nexus.mq.agent_registry import AgentRegistryRecord
from nexus.mq.agent_registry_service import AgentRegistryService
from nexus.mq.agent_registry_store import FakeAgentRegistryStore, REGISTRY_RECORD_SCHEMA_VERSION


NOW = "2026-05-19T00:00:00+00:00"


def _record(**overrides):
    data = {
        "agent_id": "jarvis",
        "runtime_instance_id": "jarvis-runtime-001",
        "role": "implementation",
        "owner_principal_id": "principal:jarvis-owner",
        "runtime_type": "local_skeleton",
        "channel_bindings": ["agent.jarvis.inbox"],
        "capabilities": ["implementation"],
        "authority_scopes": ["workflow.command"],
        "allowed_task_boundaries": ["implementation"],
        "initialization_status": "ready",
        "registry_status": "active",
        "presence_state": "idle",
        "heartbeat_ttl_seconds": 60,
        "last_heartbeat_at": "2026-05-19T00:00:00+00:00",
        "current_assignment_refs": [],
        "protocol_versions_supported": ["3.5", "4.19"],
        "trust_material_ref": "local:nats-agent-protocol",
        "startup_packet_ref": "startup-packet://jarvis",
        "readiness_evidence_ref": "evidence://readiness/jarvis",
        "startup_packet_expires_at": "2026-05-19T01:00:00+00:00",
        "created_at": "2026-05-19T00:00:00+00:00",
        "updated_at": "2026-05-19T00:00:00+00:00",
        "privacy_scopes": ["project"],
    }
    data.update(overrides)
    return AgentRegistryRecord(**data)


def test_fake_store_persists_normalized_columns_and_versioned_payload():
    store = FakeAgentRegistryStore()
    service = AgentRegistryService(store)

    result = service.register_or_refresh(_record(), now_at=NOW)
    loaded = service.load_registry_records(now_at=NOW)
    row = store.normalized_row("jarvis")

    assert result.accepted is True
    assert result.revision == 1
    assert loaded.accepted is True
    assert loaded.records[0].record.agent_id == "jarvis"
    assert loaded.records[0].normalized["revision"] == 1
    assert row["agent_id"] == "jarvis"
    assert row["runtime_instance_id"] == "jarvis-runtime-001"
    assert row["registry_status"] == "active"
    assert row["initialization_status"] == "ready"
    assert row["startup_packet_expires_at"] == "2026-05-19T01:00:00+00:00"
    assert row["payload_schema_version"] == REGISTRY_RECORD_SCHEMA_VERSION
    assert row["payload"]["schema_version"] == REGISTRY_RECORD_SCHEMA_VERSION
    assert row["payload"]["record"]["not_business_completion"] is True
    assert store.list_events()[-1].not_business_completion is True


def test_store_rejects_secret_material_in_registry_record():
    store = FakeAgentRegistryStore()
    service = AgentRegistryService(store)

    result = service.register_or_refresh(
        _record(capabilities=["implementation", "token=abc123"]),
        now_at=NOW,
    )

    assert result.accepted is False
    assert any(error.startswith("SECRET_MATERIAL_VALUE") for error in result.errors)
    assert service.read_registry_record("jarvis", now_at=NOW).accepted is False


def test_cache_only_store_does_not_load_authoritative_registry_truth():
    authoritative = FakeAgentRegistryStore()
    authoritative.upsert_record(_record(), now_at=NOW)
    cached_row = authoritative.normalized_row("jarvis")
    cache_only = FakeAgentRegistryStore(authoritative=False)
    cache_only.seed_raw_row(cached_row)
    service = AgentRegistryService(cache_only)

    loaded = service.load_registry_records(now_at=NOW)
    read = service.read_registry_record("jarvis", now_at=NOW)

    assert loaded.store_fail_closed is True
    assert loaded.records == []
    assert "REGISTRY_TRUTH_UNVERIFIED" in loaded.store_errors
    assert read.accepted is False
    assert "REGISTRY_TRUTH_UNVERIFIED" in read.errors
