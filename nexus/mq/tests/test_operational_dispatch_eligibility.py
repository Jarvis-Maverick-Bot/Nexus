from copy import deepcopy

from nexus.mq.agent_registry_service import AgentRegistryService
from nexus.mq.agent_registry_store import FakeAgentRegistryStore
from nexus.mq.dispatch_eligibility import (
    DispatchPolicy,
    DispatchRejectionCode,
    evaluate_dispatch_from_registry_service,
)
from nexus.mq.dispatch_request import DispatchRequest
from nexus.mq.tests.test_agent_registry_persistence import NOW, _record


EVAL_NOW = "2026-05-19T00:00:30+00:00"


def _request(**overrides):
    data = {
        "request_id": "dispatch-req-001",
        "correlation_id": "corr-dispatch-001",
        "work_ref": "work://implementation/001",
        "required_capability": "implementation",
        "required_authority_scope": "workflow.command",
        "required_privacy_scope": "project",
        "allowed_task_boundary": "implementation",
        "no_go_scope": ["no business execution", "no operational dispatch"],
    }
    data.update(overrides)
    return DispatchRequest(**data)


def _enabled_policy(**overrides):
    data = {"dispatch_enabled": True}
    data.update(overrides)
    return DispatchPolicy(**data)


def _service_with_records(*records, authoritative=True):
    store = FakeAgentRegistryStore(authoritative=authoritative)
    service = AgentRegistryService(store)
    for record in records:
        result = service.register_or_refresh(record, now_at=NOW)
        assert result.accepted is True
    return service, store


def test_ready_fresh_idle_accepting_agent_produces_inert_candidate_without_registry_mutation():
    service, _store = _service_with_records(_record())
    before = service.read_registry_record("jarvis", now_at=EVAL_NOW).record

    decision = evaluate_dispatch_from_registry_service(
        _request(),
        service,
        policy=_enabled_policy(),
        now_at=EVAL_NOW,
    )
    after = service.read_registry_record("jarvis", now_at=EVAL_NOW).record

    assert decision.accepted is True
    assert decision.candidate is not None
    assert decision.candidate.target_agent_id == "jarvis"
    assert decision.candidate.registry_revision_seen == 1
    assert decision.candidate.heartbeat_timestamp_observed == NOW
    assert decision.candidate.assignment_kind == "non_business_probe"
    assert decision.candidate.business_execution_allowed is False
    assert decision.candidate.not_business_completion is True
    assert before.current_assignment_refs == []
    assert after.current_assignment_refs == []
    assert after.presence_state == "idle"


def test_dispatch_policy_default_fails_closed_before_candidate_creation():
    service, _store = _service_with_records(_record())

    decision = evaluate_dispatch_from_registry_service(
        _request(),
        service,
        policy=DispatchPolicy(),
        now_at=EVAL_NOW,
    )

    assert decision.accepted is False
    assert DispatchRejectionCode.DISPATCH_DISABLED in decision.errors
    assert decision.candidate is None


def test_cache_only_registry_truth_fails_closed():
    authoritative = FakeAgentRegistryStore()
    authoritative.upsert_record(_record(), now_at=NOW)
    cache_only = FakeAgentRegistryStore(authoritative=False)
    cache_only.seed_raw_row(authoritative.normalized_row("jarvis"))
    service = AgentRegistryService(cache_only)

    decision = evaluate_dispatch_from_registry_service(
        _request(),
        service,
        policy=_enabled_policy(),
        now_at=EVAL_NOW,
    )

    assert decision.accepted is False
    assert DispatchRejectionCode.REGISTRY_UNVERIFIED in decision.errors


def test_corrupted_registry_store_blocks_whole_dispatch_load():
    service, store = _service_with_records(_record())
    store.corrupt_store_for_test()

    decision = evaluate_dispatch_from_registry_service(
        _request(),
        service,
        policy=_enabled_policy(),
        now_at=EVAL_NOW,
    )

    assert decision.accepted is False
    assert DispatchRejectionCode.REGISTRY_MALFORMED in decision.errors
    assert decision.rejected == {}


def test_malformed_row_fails_closed_for_that_agent_while_other_agent_can_be_selected():
    service, store = _service_with_records(_record(agent_id="ready", runtime_instance_id="ready-runtime"))
    malformed_row = deepcopy(store.normalized_row("ready"))
    malformed_row["agent_id"] = "malformed"
    malformed_row["payload"]["record"]["agent_id"] = "malformed"
    malformed_row.pop("payload_schema_version")
    store.seed_raw_row(malformed_row)

    decision = evaluate_dispatch_from_registry_service(
        _request(),
        service,
        policy=_enabled_policy(),
        now_at=EVAL_NOW,
    )

    assert decision.accepted is True
    assert decision.candidate.target_agent_id == "ready"
    assert decision.rejected["malformed"] == [DispatchRejectionCode.REGISTRY_MALFORMED]
