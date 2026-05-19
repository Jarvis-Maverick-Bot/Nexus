import pytest

from nexus.mq.agent_access_read_model import build_agent_access_read_model
from nexus.mq.agent_registry_service import AgentRegistryService
from nexus.mq.agent_registry_store import FakeAgentRegistryStore
from nexus.mq.dispatch_eligibility import DispatchPolicy, evaluate_dispatch_from_registry_service
from nexus.mq.dispatch_projection import build_dispatch_projection
from nexus.mq.dispatch_request import DispatchRequest
from nexus.mq.tests.test_agent_registry_persistence import NOW, _record


EVAL_NOW = "2026-05-19T00:00:30+00:00"


def _request(**overrides):
    data = {
        "request_id": "dispatch-req-access",
        "correlation_id": "corr-dispatch-access",
        "work_ref": "work://implementation/access",
        "required_capability": "implementation",
        "required_authority_scope": "workflow.command",
        "required_privacy_scope": "project",
        "allowed_task_boundary": "implementation",
        "no_go_scope": ["no business execution", "no operational dispatch"],
        "evidence_refs": ["evidence://dispatch/request"],
    }
    data.update(overrides)
    return DispatchRequest(**data)


def _decision():
    store = FakeAgentRegistryStore()
    service = AgentRegistryService(store)
    assert service.register_or_refresh(_record(), now_at=NOW).accepted is True
    return evaluate_dispatch_from_registry_service(
        _request(),
        service,
        policy=DispatchPolicy(dispatch_enabled=True),
        now_at=EVAL_NOW,
    )


def test_dispatch_projection_is_read_only_and_redacted():
    projection = build_dispatch_projection(_decision())
    rendered = str(projection).lower()

    assert projection["projection_type"] == "dispatch_assignment_candidate"
    assert projection["decision_status"] == "candidate"
    assert projection["read_only"] is True
    assert projection["not_business_completion"] is True
    assert projection["business_execution_allowed"] is False
    assert projection["evidence_refs"] == ["evidence://dispatch/request"]
    assert "token=abc" not in rendered


def test_agent_access_read_model_includes_dispatch_projection_without_mutation_actions():
    projection = build_dispatch_projection(_decision())
    model = build_agent_access_read_model(
        agents=[_record()],
        assignments=[],
        outbox_items=[],
        adapter_health=[],
        exceptions=[],
        evidence=[],
        dispatch_projection=[projection],
    )
    payload = model.to_dict()

    assert payload["dispatch"][0]["projection_type"] == "dispatch_assignment_candidate"
    assert payload["dispatch"][0]["read_only"] is True
    assert payload["dispatch"][0]["not_business_completion"] is True
    with pytest.raises(PermissionError):
        model.apply_operator_action("dispatch")


def test_agent_access_dispatch_projection_redacts_secret_like_fields():
    model = build_agent_access_read_model(
        agents=[],
        assignments=[],
        outbox_items=[],
        adapter_health=[],
        exceptions=[],
        evidence=[],
        dispatch_projection=[
            {
                "projection_type": "dispatch_eligibility",
                "decision_status": "rejected",
                "evidence_refs": ["evidence://dispatch/token=abc"],
                "raw_private_payload": {"password": "abc"},
                "not_business_completion": True,
                "read_only": True,
            }
        ],
    )
    payload = model.to_dict()
    rendered = str(payload).lower()

    assert payload["dispatch"][0]["evidence_refs"] == ["[REDACTED]"]
    assert "token=abc" not in rendered
    assert "raw_private_payload" not in rendered
    assert "password" not in rendered
