from nexus.mq.agent_registry_service import AgentRegistryService
from nexus.mq.agent_registry_store import FakeAgentRegistryStore
from nexus.mq.candidate_runtime_registry import CandidateRuntimeMigrationRequest, CandidateRuntimeRegistry
from nexus.mq.tests.test_candidate_runtime_identity import NOW, _identity, _profile


def _registry():
    store = FakeAgentRegistryStore()
    return CandidateRuntimeRegistry(AgentRegistryService(store)), store


def test_candidate_runtime_registration_readback_and_idempotent_refresh():
    registry, store = _registry()

    first = registry.register_or_refresh_candidate_runtime(profile=_profile(), identity=_identity(), now_at=NOW)
    second = registry.register_or_refresh_candidate_runtime(profile=_profile(), identity=_identity(), now_at=NOW)
    row = store.normalized_row("jarvis")

    assert first.accepted is True
    assert first.revision == 1
    assert second.accepted is True
    assert second.duplicate_suppressed is True
    assert second.revision == 1
    assert row["candidate_profile_ref"] == "candidate-profile://implementation"
    assert row["runtime_provider"] == "openclaw"


def test_candidate_runtime_identity_collision_quarantines_existing_record():
    registry, store = _registry()
    registry.register_or_refresh_candidate_runtime(profile=_profile(), identity=_identity(), now_at=NOW)

    conflict = registry.register_or_refresh_candidate_runtime(
        profile=_profile(),
        identity=_identity(runtime_instance_id="jarvis-runtime-002"),
        now_at=NOW,
    )
    read = AgentRegistryService(store).read_registry_record("jarvis", now_at=NOW)

    assert conflict.accepted is False
    assert "DUPLICATE_ACTIVE_CANDIDATE_RUNTIME" in conflict.errors
    assert conflict.quarantined_existing is True
    assert read.record.initialization_status == "quarantined"
    assert read.record.accepting_new_work is False


def test_candidate_runtime_registry_unavailable_fails_closed():
    store = FakeAgentRegistryStore(authoritative=False)
    registry = CandidateRuntimeRegistry(AgentRegistryService(store))

    result = registry.register_or_refresh_candidate_runtime(profile=_profile(), identity=_identity(), now_at=NOW)

    assert result.accepted is False
    assert "REGISTRY_TRUTH_UNVERIFIED" in result.errors


def test_candidate_runtime_migration_is_adapter_boundary_only_and_validated():
    registry, _store = _registry()

    decision = registry.evaluate_runtime_migration(
        CandidateRuntimeMigrationRequest(
            agent_id="jarvis",
            candidate_profile_ref="candidate-profile://implementation",
            source_runtime_instance_id="legacy-runtime",
            target_runtime_instance_id="jarvis-runtime-001",
            owner_principal_id="principal:jarvis-owner",
            runtime_provider="openclaw",
            migration_id="migration-001",
            evidence_ref="evidence://migration/jarvis",
        )
    )

    assert decision.accepted is True
    assert decision.not_business_completion is True
