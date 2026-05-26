import json

from nexus.mq.candidate_adapter_profile_loader import (
    CANDIDATE_ADAPTER_PROFILE_SCHEMA_VERSION,
    CANDIDATE_ADAPTER_PROTOCOL_VERSION,
    load_candidate_adapter_profile,
    profile_digest,
)


def _write_profile(tmp_path, **overrides):
    data = {
        "profile_schema_version": CANDIDATE_ADAPTER_PROFILE_SCHEMA_VERSION,
        "adapter_protocol_version": CANDIDATE_ADAPTER_PROTOCOL_VERSION,
        "agent_id": "jarvis",
        "runtime_instance_id": "jarvis-runtime-001",
        "owner_principal_id": "principal:jarvis-owner",
        "runtime_type": "candidate",
        "role": "implementation",
        "capabilities": ["implementation"],
        "authority_scopes": ["workflow.command"],
        "privacy_scopes": ["project"],
        "no_go_scope": ["no business execution", "no private-agent invocation"],
        "broker_profile_ref": "broker-profile://nexus-distributed-uat",
        "broker_url": "nats://192.168.31.124:7422",
        "allowed_subject_patterns": ["nexus.candidate.jarvis.assignment.*", "nexus.candidate.jarvis.drain"],
        "allowed_message_families": ["assignment", "lifecycle", "evidence"],
        "evidence_output_ref": "evidence://candidate-adapter/jarvis",
        "trust_material_ref": "trust-ref://jarvis",
        "credential_ref": "credential-ref://nats/jarvis",
    }
    data.update(overrides)
    path = tmp_path / "candidate-profile.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_candidate_profile_requires_broker_profile_and_no_go_scope(tmp_path):
    result = load_candidate_adapter_profile(_write_profile(tmp_path, broker_profile_ref="", no_go_scope=[]))

    assert result.accepted is False
    assert "MISSING_PROFILE_FIELD: broker_profile_ref" in result.errors
    assert "MISSING_PROFILE_FIELD: no_go_scope" in result.errors


def test_candidate_profile_rejects_unauthorized_subject_pattern(tmp_path):
    result = load_candidate_adapter_profile(_write_profile(tmp_path, allowed_subject_patterns=[">"]))

    assert result.accepted is False
    assert "UNAUTHORIZED_SUBJECT_PATTERN: >" in result.errors


def test_candidate_profile_rejects_protocol_version_mismatch(tmp_path):
    result = load_candidate_adapter_profile(_write_profile(tmp_path, adapter_protocol_version="4.19.unsupported"))

    assert result.accepted is False
    assert "UNSUPPORTED_ADAPTER_PROTOCOL_VERSION: 4.19.unsupported" in result.errors


def test_candidate_profile_rejects_openclaw_4222_for_distributed_uat(tmp_path):
    result = load_candidate_adapter_profile(_write_profile(tmp_path, broker_url="nats://openclaw.local:4222"))

    assert result.accepted is False
    assert "BROKER_ENDPOINT_FORBIDDEN_FOR_DISTRIBUTED_UAT: openclaw.local:4222" in result.errors


def test_candidate_profile_rejects_jarvis_loopback_for_distributed_uat(tmp_path):
    result = load_candidate_adapter_profile(_write_profile(tmp_path, broker_url="nats://127.0.0.1:7422"))

    assert result.accepted is False
    assert "BROKER_LOOPBACK_FORBIDDEN_FOR_DISTRIBUTED_UAT: 127.0.0.1" in result.errors


def test_candidate_profile_allows_loopback_only_with_explicit_local_authorization(tmp_path):
    result = load_candidate_adapter_profile(
        _write_profile(tmp_path, broker_url="nats://127.0.0.1:7422"),
        local_only_authorization=True,
    )

    assert result.accepted is True
    assert result.profile.local_only_authorized is True


def test_candidate_profile_requires_evidence_output_policy(tmp_path):
    result = load_candidate_adapter_profile(_write_profile(tmp_path, evidence_output_ref=""))

    assert result.accepted is False
    assert "MISSING_PROFILE_FIELD: evidence_output_ref" in result.errors


def test_candidate_profile_digest_changes_on_authority_fields(tmp_path):
    first = load_candidate_adapter_profile(_write_profile(tmp_path))
    second = load_candidate_adapter_profile(_write_profile(tmp_path, authority_scopes=["workflow.readonly"]))

    assert first.accepted is True
    assert second.accepted is True
    assert profile_digest(first.profile) != profile_digest(second.profile)
