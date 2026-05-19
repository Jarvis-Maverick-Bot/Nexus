from dataclasses import replace

from nexus.mq.private_result_candidate import (
    PrivateAgentResultCandidate,
    PrivateResultOutput,
    validate_private_result_candidate,
)
from nexus.mq.private_result_validators import (
    run_evidence_validator,
    run_safety_validator,
    validate_private_result_candidate_chain,
)
from nexus.mq.tests.test_private_agent_contract import NOW, _contract
from nexus.mq.tests.test_private_task_package import _package


def _candidate(**overrides):
    package = _package()
    data = {
        "result_id": "result-private-diagnostic",
        "assignment_id": package.assignment_id,
        "contract_id": package.contract_id,
        "contract_revision": package.contract_revision,
        "task_package_id": package.task_package_id,
        "task_package_hash": package.package_hash,
        "invocation_id": "diagnostic-echo",
        "status_claim": "success",
        "summary": "diagnostic echo complete",
        "outputs": [PrivateResultOutput("artifact://private-agent/echo", "diagnostic_echo", "sha256:output")],
        "evidence_refs": ["evidence://private-agent/diagnostic-log"],
        "self_reported_risks": [],
        "requested_followup_context": [],
        "claims_business_completion": False,
        "produced_at": NOW,
    }
    data.update(overrides)
    return PrivateAgentResultCandidate(**data)


def test_private_result_candidate_rejects_wrong_contract():
    validation = validate_private_result_candidate(
        _candidate(contract_id="contract-other"),
        package=_package(),
        contract=_contract(),
        now_at=NOW,
    )

    assert validation.valid is False
    assert "PRIVATE_RESULT_CONTRACT_MISMATCH" in validation.errors


def test_private_result_candidate_rejects_malformed_output():
    validation = validate_private_result_candidate(
        _candidate(outputs=[PrivateResultOutput("", "unknown", "")]),
        package=_package(),
        now_at=NOW,
    )

    assert validation.valid is False
    assert "PRIVATE_RESULT_OUTPUT_REF_REQUIRED" in validation.errors
    assert "PRIVATE_RESULT_OUTPUT_TYPE_INVALID: unknown" in validation.errors
    assert "PRIVATE_RESULT_OUTPUT_HASH_REQUIRED" in validation.errors


def test_private_agent_extra_context_request_is_quarantined():
    validation = validate_private_result_candidate(
        _candidate(requested_followup_context=["full_repo_checkout"]),
        package=_package(),
        now_at=NOW,
    )

    assert validation.valid is False
    assert validation.quarantine_required is True
    assert "PRIVATE_FOLLOWUP_CONTEXT_REQUESTED" in validation.errors


def test_validator_layers_do_not_collapse_completion():
    package = _package()
    candidate = _candidate()

    evidence = run_evidence_validator(candidate, package)
    safety = run_safety_validator(candidate, package, evidence=evidence)
    decision = validate_private_result_candidate_chain(candidate, package)

    assert evidence.accepted is True
    assert safety.accepted is True
    assert decision.governed.accepted is False
    assert "PRIVATE_BUSINESS_COMMIT_NOT_AUTHORIZED" in decision.governed.errors
    assert "PRIVATE_DIAGNOSTIC_RESULT_NOT_BUSINESS_COMPLETION" in decision.governed.errors
    assert decision.business_state_committed is False
    assert decision.result_state == "result_candidate"


def test_private_external_result_not_business_completion_even_with_authority_flag():
    decision = validate_private_result_candidate_chain(
        _candidate(),
        _package(),
        governed_authority_approved=True,
        business_commit_authorized=True,
    )

    assert decision.evidence.accepted is True
    assert decision.safety.accepted is True
    assert decision.governed.accepted is False
    assert "PRIVATE_DIAGNOSTIC_RESULT_NOT_BUSINESS_COMPLETION" in decision.governed.errors
    assert decision.business_state_committed is False


def test_private_result_candidate_cannot_commit_business_state_claim():
    decision = validate_private_result_candidate_chain(
        replace(_candidate(), claims_business_completion=True),
        _package(),
    )

    assert decision.evidence.accepted is False
    assert decision.safety.accepted is False
    assert decision.governed.accepted is False
    assert decision.business_state_committed is False
