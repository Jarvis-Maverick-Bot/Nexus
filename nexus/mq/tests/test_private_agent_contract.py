from dataclasses import replace

from nexus.mq.private_agent_contract import (
    AllowedPrivateInvocation,
    PrivateAgentContract,
    validate_private_agent_contract,
)


NOW = "2026-05-19T00:00:30+00:00"


def _invocation(**overrides):
    data = {
        "invocation_id": "diagnostic-echo",
        "invocation_type": "cli",
        "command_or_endpoint_ref": "cmdref://private-agent/diagnostic-echo",
        "allowed_args_schema_ref": "schema://private-agent/diagnostic-echo-args",
        "timeout_policy_ref": "timeout://private-agent/diagnostic",
        "retry_policy_ref": "retry://private-agent/none",
        "allowed_args": {"mode": ["diagnostic"], "format": ["json"]},
        "allowed_env_refs": ["envref://private-agent/diagnostic-only"],
        "forbidden_env_keys": ["token", "password", "secret"],
    }
    data.update(overrides)
    return AllowedPrivateInvocation(**data)


def _contract(**overrides):
    data = {
        "contract_id": "contract-private-diagnostic",
        "contract_revision": 1,
        "agent_display_name": "Private Diagnostic Agent",
        "owner": "principal:nova",
        "trust_class": "private_local",
        "adapter_host_ref": "adapter-host://local/mock",
        "adapter_agent_id": "private-adapter",
        "adapter_runtime_instance_id": "private-adapter-runtime",
        "contract_status": "active",
        "allowed_invocations": [_invocation()],
        "capability_claims": ["diagnostic.echo"],
        "authority_scope": ["diagnostic.contract"],
        "privacy_scope": ["project"],
        "forbidden_context": [
            "live_credentials",
            "long_term_memory",
            "full_repo_checkout",
            "unrelated_shared_docs",
            "private_chat_history",
            "operator_private_files",
            "business_authority_state",
            "raw_evidence_bodies",
            "external_network_credentials",
            "cross_project_context",
        ],
        "input_schema_ref": "schema://private-agent/input",
        "output_schema_ref": "schema://private-agent/output",
        "evidence_requirements": ["evidence://private-agent/diagnostic-log"],
        "validation_policy_ref": "validation://private-agent/layered",
        "max_task_package_classification": "diagnostic",
        "business_completion_authority": False,
        "diagnostic_only_until": "2026-05-20T00:00:00+00:00",
        "accepted_by": "alex",
        "accepted_at": "2026-05-19T00:00:00+00:00",
        "expires_at": "2026-05-20T00:00:00+00:00",
        "last_review_evidence_ref": "evidence://nova/private-contract-review",
    }
    data.update(overrides)
    return PrivateAgentContract(**data)


def test_private_contract_active_requires_acceptance_and_expiry():
    result = validate_private_agent_contract(
        _contract(accepted_by="", accepted_at="", expires_at="2026-05-18T00:00:00+00:00"),
        now_at=NOW,
    )

    assert result.valid is False
    assert "PRIVATE_CONTRACT_ACTIVE_REQUIRES_ACCEPTED_BY" in result.errors
    assert "PRIVATE_CONTRACT_ACTIVE_REQUIRES_ACCEPTED_AT" in result.errors
    assert "PRIVATE_CONTRACT_EXPIRED" in result.errors


def test_private_contract_business_completion_authority_must_be_false():
    result = validate_private_agent_contract(
        _contract(business_completion_authority=True),
        now_at=NOW,
    )

    assert result.valid is False
    assert "PRIVATE_CONTRACT_CANNOT_GRANT_BUSINESS_COMPLETION_AUTHORITY" in result.errors


def test_private_contract_requires_allowlist_scope_and_evidence():
    result = validate_private_agent_contract(
        _contract(allowed_invocations=[], capability_claims=[], authority_scope=[], evidence_requirements=[]),
        now_at=NOW,
    )

    assert result.valid is False
    assert "PRIVATE_CONTRACT_INVOCATION_ALLOWLIST_REQUIRED" in result.errors
    assert "PRIVATE_CONTRACT_CAPABILITY_CLAIMS_REQUIRED" in result.errors
    assert "PRIVATE_CONTRACT_AUTHORITY_SCOPE_REQUIRED" in result.errors
    assert "PRIVATE_CONTRACT_EVIDENCE_REQUIREMENTS_REQUIRED" in result.errors


def test_private_contract_rejects_secret_material():
    result = validate_private_agent_contract(
        _contract(agent_display_name="token=abc123"),
        now_at=NOW,
    )

    assert result.valid is False
    assert any(error.startswith("SECRET_MATERIAL_VALUE") for error in result.errors)


def test_private_contract_not_business_completion_marker_required():
    result = validate_private_agent_contract(
        replace(_contract(), not_business_completion=False),
        now_at=NOW,
    )

    assert result.valid is False
    assert "PRIVATE_CONTRACT_CANNOT_BE_BUSINESS_COMPLETION" in result.errors
