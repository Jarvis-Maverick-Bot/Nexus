from dataclasses import replace

from nexus.mq.agent_registry_service import AgentRegistryService
from nexus.mq.agent_registry_store import FakeAgentRegistryStore
from nexus.mq.private_agent_eligibility import (
    PrivateAgentEligibilityRequest,
    PrivateAgentRejectionCode,
    evaluate_private_agent_eligibility,
    evaluate_private_agent_from_registry_service,
)
from nexus.mq.private_contract_registry import FakePrivateContractRegistryStore
from nexus.mq.tests.test_agent_registry_persistence import _record
from nexus.mq.tests.test_private_agent_contract import NOW, _contract


EVAL_NOW = "2026-05-19T00:00:30+00:00"


def _request(**overrides):
    data = {
        "request_id": "private-eligibility-001",
        "correlation_id": "corr-private-eligibility",
        "contract_id": "contract-private-diagnostic",
        "invocation_id": "diagnostic-echo",
        "required_capability": "diagnostic.echo",
        "required_authority_scope": "diagnostic.contract",
        "required_privacy_scope": "project",
        "task_kind": "diagnostic",
    }
    data.update(overrides)
    return PrivateAgentEligibilityRequest(**data)


def _adapter_record(**overrides):
    data = {
        "agent_id": "private-adapter",
        "runtime_instance_id": "private-adapter-runtime",
        "role": "private_contract_adapter",
        "runtime_type": "local_mock_adapter",
        "capabilities": ["private.contract.diagnostic"],
        "authority_scopes": ["diagnostic.contract"],
        "allowed_task_boundaries": ["diagnostic"],
        "startup_packet_ref": "startup-packet://private-adapter",
        "readiness_evidence_ref": "evidence://readiness/private-adapter",
        "trust_material_ref": "local:private-contract-adapter",
    }
    data.update(overrides)
    return _record(**data)


def test_active_contract_and_fresh_adapter_are_eligible_through_registry_boundary():
    contract_store = FakePrivateContractRegistryStore()
    runtime_store = FakeAgentRegistryStore()
    runtime_service = AgentRegistryService(runtime_store)
    assert contract_store.upsert_contract(_contract(), now_at=NOW).accepted is True
    assert runtime_service.register_or_refresh(_adapter_record(), now_at=NOW).accepted is True

    decision = evaluate_private_agent_from_registry_service(
        _request(),
        contract_store,
        runtime_service,
        now_at=EVAL_NOW,
    )

    assert decision.accepted is True
    assert decision.contract_id == "contract-private-diagnostic"
    assert decision.adapter_agent_id == "private-adapter"
    assert decision.registry_revision_seen == 1
    assert decision.heartbeat_timestamp_observed == "2026-05-19T00:00:00+00:00"


def test_adapter_presence_does_not_imply_private_trust():
    contract = replace(_contract(), contract_status="suspended")

    decision = evaluate_private_agent_eligibility(
        _request(),
        contract,
        _adapter_record(),
        registry_revision_seen=1,
        now_at=EVAL_NOW,
    )

    assert decision.accepted is False
    assert PrivateAgentRejectionCode.PRIVATE_CONTRACT_NOT_ACTIVE in decision.errors


def test_active_contract_without_fresh_adapter_fails_closed():
    decision = evaluate_private_agent_eligibility(
        _request(),
        _contract(),
        _adapter_record(last_heartbeat_at="2026-05-18T23:58:00+00:00"),
        registry_revision_seen=1,
        now_at=EVAL_NOW,
    )

    assert decision.accepted is False
    assert PrivateAgentRejectionCode.PRIVATE_ADAPTER_STALE in decision.errors


def test_private_agent_wrong_scope_fails_closed_without_private_details():
    decision = evaluate_private_agent_eligibility(
        _request(required_authority_scope="business.commit", required_privacy_scope="full_repo"),
        _contract(),
        _adapter_record(),
        registry_revision_seen=1,
        now_at=EVAL_NOW,
    )

    assert decision.accepted is False
    assert PrivateAgentRejectionCode.PRIVATE_AUTHORITY_SCOPE_MISMATCH in decision.errors
    assert PrivateAgentRejectionCode.PRIVATE_PRIVACY_SCOPE_MISMATCH in decision.errors
    assert "full_repo" not in decision.errors


def test_private_agent_non_diagnostic_task_is_blocked():
    decision = evaluate_private_agent_eligibility(
        _request(task_kind="non_business_probe"),
        _contract(max_task_package_classification="non_business_probe"),
        _adapter_record(),
        registry_revision_seen=1,
        now_at=EVAL_NOW,
    )

    assert decision.accepted is False
    assert PrivateAgentRejectionCode.PRIVATE_DIAGNOSTIC_ONLY in decision.errors


def test_missing_contract_fails_closed_before_adapter_trust():
    contract_store = FakePrivateContractRegistryStore()
    runtime_store = FakeAgentRegistryStore()
    runtime_service = AgentRegistryService(runtime_store)
    assert runtime_service.register_or_refresh(_adapter_record(), now_at=NOW).accepted is True

    decision = evaluate_private_agent_from_registry_service(
        _request(),
        contract_store,
        runtime_service,
        now_at=EVAL_NOW,
    )

    assert decision.accepted is False
    assert decision.errors == [PrivateAgentRejectionCode.PRIVATE_CONTRACT_MISSING]
