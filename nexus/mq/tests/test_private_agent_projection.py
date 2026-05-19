import pytest

from nexus.mq.agent_access_read_model import build_agent_access_read_model
from nexus.mq.private_agent_eligibility import PrivateAgentEligibilityDecision
from nexus.mq.private_agent_projection import build_private_agent_projection
from nexus.mq.private_result_validators import validate_private_result_candidate_chain
from nexus.mq.tests.test_private_agent_contract import _contract
from nexus.mq.tests.test_private_diagnostic_runner import _invocation, _prepared_result
from nexus.mq.tests.test_private_task_package import _package
from nexus.mq.private_invocation_runner import run_private_diagnostic_invocation


def test_private_projection_is_redacted_and_read_only():
    package = _package()
    diagnostic_run = run_private_diagnostic_invocation(
        _contract(last_review_evidence_ref="evidence://review/token=abc"),
        package,
        _invocation(task_package_hash=package.package_hash),
        _prepared_result(),
        now_at="2026-05-19T00:00:30+00:00",
    )
    validation = validate_private_result_candidate_chain(diagnostic_run.result_candidate, package)

    projection = build_private_agent_projection(
        contract=_contract(last_review_evidence_ref="evidence://review/token=abc"),
        eligibility=PrivateAgentEligibilityDecision(accepted=True, contract_id="contract-private-diagnostic"),
        diagnostic_run=diagnostic_run,
        validation=validation,
    )

    rendered = str(projection).lower()
    assert projection["read_only"] is True
    assert projection["not_business_completion"] is True
    assert projection["diagnostic_only"] is True
    assert projection["business_state_committed"] is False
    assert projection["evidence_refs"][0] == "[REDACTED]"
    assert "token=abc" not in rendered
    assert "raw" not in rendered


def test_agent_access_read_model_accepts_private_projection_as_explicit_read_only_surface():
    projection = build_private_agent_projection(contract=_contract())
    model = build_agent_access_read_model(
        agents=[],
        assignments=[],
        outbox_items=[],
        adapter_health=[],
        exceptions=[],
        evidence=[],
        private_agent_projection=[
            {
                **projection,
                "raw_private_payload": {"password": "abc"},
                "secret": "abc",
                "action": "invoke",
            }
        ],
    )

    payload = model.to_dict()
    rendered = str(payload).lower()

    assert payload["private_agents"][0]["contract_id"] == "contract-private-diagnostic"
    assert payload["private_agents"][0]["read_only"] is True
    assert payload["private_agents"][0]["not_business_completion"] is True
    assert "raw_private_payload" not in rendered
    assert "password" not in rendered
    assert "secret" not in rendered
    assert "action" not in rendered
    with pytest.raises(PermissionError):
        model.apply_operator_action("invoke_private_agent")
