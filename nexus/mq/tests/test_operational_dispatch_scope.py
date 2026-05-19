import pytest

from nexus.mq.agent_registry_service import AgentRegistryService
from nexus.mq.agent_registry_store import FakeAgentRegistryStore
from nexus.mq.dispatch_eligibility import DispatchPolicy, DispatchRejectionCode, evaluate_dispatch_from_registry_service
from nexus.mq.dispatch_request import DispatchRequest
from nexus.mq.tests.test_agent_registry_persistence import NOW, _record


EVAL_NOW = "2026-05-19T00:00:30+00:00"


def _request(**overrides):
    data = {
        "request_id": "dispatch-req-scope",
        "correlation_id": "corr-dispatch-scope",
        "work_ref": "work://implementation/scope",
        "required_capability": "implementation",
        "required_authority_scope": "workflow.command",
        "required_privacy_scope": "project",
        "allowed_task_boundary": "implementation",
        "no_go_scope": ["no business execution", "no operational dispatch"],
    }
    data.update(overrides)
    return DispatchRequest(**data)


def _decision_for_record(record, request=None, now_at=EVAL_NOW):
    store = FakeAgentRegistryStore()
    service = AgentRegistryService(store)
    result = service.register_or_refresh(record, now_at=NOW)
    assert result.accepted is True
    return evaluate_dispatch_from_registry_service(
        request or _request(),
        service,
        policy=DispatchPolicy(dispatch_enabled=True),
        now_at=now_at,
    )


def test_missing_readiness_evidence_fails_closed_from_registry_row_rejection():
    store = FakeAgentRegistryStore()
    service = AgentRegistryService(store)
    assert service.register_or_refresh(_record(), now_at=NOW).accepted is True
    row = store.normalized_row("jarvis")
    row["readiness_evidence_ref"] = None
    row["payload"]["record"]["readiness_evidence_ref"] = None
    store.seed_raw_row(row)

    decision = evaluate_dispatch_from_registry_service(
        _request(),
        service,
        policy=DispatchPolicy(dispatch_enabled=True),
        now_at=EVAL_NOW,
    )

    assert decision.accepted is False
    assert DispatchRejectionCode.READINESS_EVIDENCE_MISSING in decision.rejected["jarvis"]


def test_expired_startup_packet_fails_closed_from_registry_freshness():
    decision = _decision_for_record(
        _record(startup_packet_expires_at="2026-05-19T00:00:20+00:00"),
        now_at=EVAL_NOW,
    )

    assert decision.accepted is False
    assert DispatchRejectionCode.STARTUP_PACKET_EXPIRED in decision.rejected["jarvis"]


def test_stale_heartbeat_fails_closed_even_when_presence_still_idle():
    decision = _decision_for_record(
        _record(heartbeat_ttl_seconds=10, last_heartbeat_at=NOW, presence_state="idle"),
        now_at="2026-05-19T00:00:15+00:00",
    )

    assert decision.accepted is False
    assert DispatchRejectionCode.HEARTBEAT_STALE in decision.rejected["jarvis"]


@pytest.mark.parametrize(
    ("presence_state", "expected_code"),
    [
        ("online", DispatchRejectionCode.PRESENCE_ONLINE_ONLY),
        ("busy", DispatchRejectionCode.PRESENCE_BUSY),
        ("degraded", DispatchRejectionCode.PRESENCE_DEGRADED),
        ("draining", DispatchRejectionCode.PRESENCE_DRAINING),
        ("offline", DispatchRejectionCode.PRESENCE_OFFLINE),
        ("stale", DispatchRejectionCode.PRESENCE_STALE),
    ],
)
def test_non_idle_presence_states_fail_normal_dispatch(presence_state, expected_code):
    decision = _decision_for_record(_record(presence_state=presence_state))

    assert decision.accepted is False
    assert expected_code in decision.rejected["jarvis"]


def test_accepting_new_work_false_fails_dispatch():
    decision = _decision_for_record(_record(accepting_new_work=False))

    assert decision.accepted is False
    assert DispatchRejectionCode.NOT_ACCEPTING_NEW_WORK in decision.rejected["jarvis"]


@pytest.mark.parametrize(
    ("request_override", "expected_code"),
    [
        ({"required_capability": "review"}, DispatchRejectionCode.CAPABILITY_MISMATCH),
        ({"required_authority_scope": "workflow.admin"}, DispatchRejectionCode.AUTHORITY_SCOPE_MISMATCH),
        ({"required_privacy_scope": "private"}, DispatchRejectionCode.PRIVACY_SCOPE_MISMATCH),
        ({"allowed_task_boundary": "deployment"}, DispatchRejectionCode.TASK_BOUNDARY_MISMATCH),
    ],
)
def test_capability_authority_privacy_and_task_boundary_mismatches_fail_closed(request_override, expected_code):
    decision = _decision_for_record(_record(), request=_request(**request_override))

    assert decision.accepted is False
    assert expected_code in decision.rejected["jarvis"]


def test_business_dispatch_without_separate_authorization_uses_canonical_rejection_code():
    decision = _decision_for_record(_record(), request=_request(assignment_kind="business_task"))

    assert decision.accepted is False
    assert DispatchRejectionCode.BUSINESS_DISPATCH_NOT_AUTHORIZED in decision.errors
