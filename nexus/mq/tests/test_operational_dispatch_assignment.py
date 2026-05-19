from dataclasses import replace

from nexus.mq.agent_registry_service import AgentRegistryService
from nexus.mq.agent_registry_store import FakeAgentRegistryStore
from nexus.mq.dispatch_assignment import validate_assignment_candidate
from nexus.mq.dispatch_eligibility import DispatchPolicy, evaluate_dispatch_from_registry_service
from nexus.mq.dispatch_request import DispatchRequest
from nexus.mq.tests.test_agent_registry_persistence import NOW, _record


EVAL_NOW = "2026-05-19T00:00:30+00:00"


def _request(**overrides):
    data = {
        "request_id": "dispatch-req-assignment",
        "correlation_id": "corr-dispatch-assignment",
        "work_ref": "work://implementation/assignment",
        "required_capability": "implementation",
        "required_authority_scope": "workflow.command",
        "required_privacy_scope": "project",
        "allowed_task_boundary": "implementation",
        "no_go_scope": ["no business execution", "no operational dispatch"],
        "evidence_refs": ["evidence://dispatch/request"],
    }
    data.update(overrides)
    return DispatchRequest(**data)


def _candidate():
    store = FakeAgentRegistryStore()
    service = AgentRegistryService(store)
    assert service.register_or_refresh(_record(), now_at=NOW).accepted is True
    decision = evaluate_dispatch_from_registry_service(
        _request(),
        service,
        policy=DispatchPolicy(dispatch_enabled=True),
        now_at=EVAL_NOW,
    )
    assert decision.accepted is True
    return decision.candidate


def test_assignment_candidate_contains_required_boundary_fields():
    candidate = _candidate()
    payload = candidate.to_dict()

    assert payload["assignment_id"].startswith("assign-")
    assert payload["idempotency_key"].startswith("dispatch:")
    assert payload["request_id"] == "dispatch-req-assignment"
    assert payload["correlation_id"] == "corr-dispatch-assignment"
    assert payload["target_agent_id"] == "jarvis"
    assert payload["target_runtime_instance_id"] == "jarvis-runtime-001"
    assert payload["registry_revision_seen"] == 1
    assert payload["heartbeat_timestamp_observed"] == NOW
    assert payload["startup_packet_ref"] == "startup-packet://jarvis"
    assert payload["startup_packet_expires_at"] == "2026-05-19T01:00:00+00:00"
    assert payload["readiness_evidence_ref"] == "evidence://readiness/jarvis"
    assert payload["assignment_kind"] == "non_business_probe"
    assert payload["business_execution_allowed"] is False
    assert payload["not_business_completion"] is True


def test_assignment_candidate_cannot_mark_business_completion_or_allow_business_execution():
    candidate = _candidate()

    invalid_completion = validate_assignment_candidate(replace(candidate, not_business_completion=False))
    invalid_business_execution = validate_assignment_candidate(replace(candidate, business_execution_allowed=True))
    invalid_live_state = validate_assignment_candidate(replace(candidate, state="completed"))

    assert "ASSIGNMENT_CANDIDATE_CANNOT_BE_BUSINESS_COMPLETION" in invalid_completion.errors
    assert "ASSIGNMENT_CANDIDATE_CANNOT_ALLOW_BUSINESS_EXECUTION" in invalid_business_execution.errors
    assert "UNSUPPORTED_INERT_ASSIGNMENT_STATE: completed" in invalid_live_state.errors


def test_assignment_candidate_generation_is_deterministic_for_same_registry_snapshot():
    first = _candidate()
    second = _candidate()

    assert first.assignment_id == second.assignment_id
    assert first.idempotency_key == second.idempotency_key
