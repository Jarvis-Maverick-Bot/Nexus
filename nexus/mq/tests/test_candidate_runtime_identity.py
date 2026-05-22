import pytest

from nexus.mq.candidate_runtime_identity import (
    CandidateAgentProfile,
    CandidateRuntimeIdentity,
    build_candidate_registry_record,
    validate_candidate_agent_profile,
    validate_candidate_runtime_identity,
)


NOW = "2026-05-22T00:00:00+00:00"


def _profile(**overrides):
    data = {
        "agent_id": "jarvis",
        "candidate_profile_ref": "candidate-profile://implementation",
        "role": "implementation",
        "capabilities": ["implementation"],
        "authority_scopes": ["workflow.command"],
        "privacy_scopes": ["project"],
        "allowed_task_boundaries": ["implementation"],
        "no_go_scope": ["no business execution", "no private-agent invocation"],
    }
    data.update(overrides)
    return CandidateAgentProfile(**data)


def _identity(**overrides):
    data = {
        "agent_id": "jarvis",
        "runtime_instance_id": "jarvis-runtime-001",
        "runtime_type": "local_skeleton",
        "runtime_provider": "openclaw",
        "host_ref": "host://jarvis-linux",
        "owner_principal_id": "principal:jarvis-owner",
        "role": "implementation",
        "candidate_profile_ref": "candidate-profile://implementation",
        "startup_packet_ref": "startup-packet://jarvis",
        "readiness_evidence_ref": "evidence://readiness/jarvis",
        "startup_packet_expires_at": "2026-05-22T01:00:00+00:00",
        "source_repo_refs": ["repo://nexus"],
        "trust_material_ref": "trust-ref://jarvis",
        "credential_ref": "credential-ref://nats/jarvis",
    }
    data.update(overrides)
    return CandidateRuntimeIdentity(**data)


def test_candidate_runtime_identity_is_generic_for_jarvis_and_future_candidate():
    jarvis = validate_candidate_runtime_identity(_identity(), profile=_profile())
    future = validate_candidate_runtime_identity(
        _identity(
            agent_id="future-agent",
            runtime_instance_id="future-runtime-001",
            runtime_provider="codex",
            host_ref="host://future",
            owner_principal_id="principal:future-owner",
            startup_packet_ref="startup-packet://future",
            readiness_evidence_ref="evidence://readiness/future",
            trust_material_ref="trust-ref://future",
            credential_ref="credential-ref://nats/future",
        ),
        profile=_profile(agent_id="future-agent"),
    )

    assert jarvis.valid is True
    assert future.valid is True


def test_candidate_profile_rejects_jarvis_only_and_business_dispatch():
    result = validate_candidate_agent_profile(
        _profile(candidate_profile_ref="candidate-profile://jarvis-only", business_dispatch_allowed=True)
    )

    assert result.valid is False
    assert "CANDIDATE_PROFILE_MUST_BE_GENERIC_NOT_JARVIS_ONLY" in result.errors
    assert "BUSINESS_DISPATCH_NOT_AUTHORIZED" in result.errors


def test_candidate_identity_rejects_secret_material_and_mismatched_profile():
    result = validate_candidate_runtime_identity(
        _identity(credential_ref="token=abc123", candidate_profile_ref="candidate-profile://other"),
        profile=_profile(),
    )

    assert result.valid is False
    assert "CANDIDATE_PROFILE_REF_MISMATCH" in result.errors
    assert any(error.startswith("SECRET_MATERIAL_VALUE") for error in result.errors)


def test_candidate_identity_builds_registry_record_without_business_completion():
    record = build_candidate_registry_record(profile=_profile(), identity=_identity(), now_at=NOW)

    assert record.agent_id == "jarvis"
    assert record.candidate_profile_ref == "candidate-profile://implementation"
    assert record.runtime_provider == "openclaw"
    assert record.host_ref == "host://jarvis-linux"
    assert record.credential_ref == "credential-ref://nats/jarvis"
    assert record.not_business_completion is True


def test_candidate_identity_missing_required_field_fails_before_record_build():
    with pytest.raises(ValueError) as excinfo:
        build_candidate_registry_record(profile=_profile(), identity=_identity(source_repo_refs=[]), now_at=NOW)

    assert "MISSING_CANDIDATE_RUNTIME_IDENTITY_FIELD: source_repo_refs" in str(excinfo.value)
