from nexus.mq.codex_runtime_adapter import (
    CodexRuntimeRegistration,
    CodexStartupReadiness,
    build_codex_registry_record,
    validate_codex_runtime_registration,
    validate_codex_startup_readiness,
)


NOW = "2026-05-24T13:40:00+00:00"
EXPIRES = "2026-05-24T14:40:00+00:00"


def _registration(**overrides):
    data = {
        "agent_id": "codex-thunder",
        "runtime_instance_id": "codex-runtime-001",
        "host_ref": "host://thunder-windows",
        "owner_principal_id": "principal://thunder",
        "capabilities": ["code_read", "code_edit", "test_run", "lint_run", "git_diff", "evidence_generation"],
        "authority_scopes": ["wbs://7.19.13"],
        "allowed_task_boundaries": ["bounded_implementation_candidate", "non_business_probe"],
        "allowed_workspace_refs": ["workspace://nexus"],
        "allowed_write_surfaces": ["nexus/mq/codex_*.py", "nexus/mq/tests/test_codex_*.py"],
        "prohibited_write_surfaces": ["config/**", ".env", "broker/**"],
        "startup_packet_ref": "startup-packet://codex/001",
        "readiness_evidence_ref": "evidence://codex/readiness/001",
        "startup_packet_expires_at": EXPIRES,
        "trust_material_ref": "trust-ref://codex/thunder",
        "credential_ref": "credential-ref://nats/codex",
    }
    data.update(overrides)
    return CodexRuntimeRegistration(**data)


def _readiness(**overrides):
    data = {
        "readiness_id": "readiness-codex-001",
        "runtime_instance_id": "codex-runtime-001",
        "startup_packet_ref": "startup-packet://codex/001",
        "readiness_evidence_ref": "evidence://codex/readiness/001",
        "startup_packet_expires_at": EXPIRES,
        "validated_at": NOW,
        "allowed_workspace_refs": ["workspace://nexus"],
        "allowed_tools": ["git", "pytest"],
        "no_go_scope": ["no live worker start", "no credential mutation"],
        "status": "ready",
    }
    data.update(overrides)
    return CodexStartupReadiness(**data)


def test_codex_runtime_registration_builds_registry_record_as_coding_agent():
    record = build_codex_registry_record(registration=_registration(), now_at=NOW)

    assert record.agent_id == "codex-thunder"
    assert record.runtime_type == "coding_agent"
    assert record.runtime_provider == "codex"
    assert record.role == "codex"
    assert record.initialization_status == "ready"
    assert record.registry_status == "active"
    assert record.not_business_completion is True


def test_codex_registration_rejects_secret_material_and_business_completion():
    result = validate_codex_runtime_registration(
        _registration(credential_ref="token=" + "abc123", not_business_completion=False)
    )

    assert result.valid is False
    assert "CODEX_RUNTIME_REGISTRATION_CANNOT_BE_BUSINESS_COMPLETION" in result.errors
    assert any(error.startswith("SECRET_MATERIAL_VALUE") for error in result.errors)


def test_codex_registration_requires_bounded_workspace_and_write_surfaces():
    result = validate_codex_runtime_registration(
        _registration(allowed_workspace_refs=[], allowed_write_surfaces=[])
    )

    assert result.valid is False
    assert "MISSING_CODEX_RUNTIME_REGISTRATION_FIELD: allowed_workspace_refs" in result.errors
    assert "MISSING_CODEX_RUNTIME_REGISTRATION_FIELD: allowed_write_surfaces" in result.errors


def test_codex_startup_readiness_rejects_expired_packet():
    result = validate_codex_startup_readiness(
        _readiness(startup_packet_expires_at="2026-05-24T13:00:00+00:00"),
        now_at=NOW,
    )

    assert result.valid is False
    assert "CODEX_STARTUP_PACKET_EXPIRED" in result.errors


def test_codex_startup_readiness_rejects_missing_no_go_scope():
    result = validate_codex_startup_readiness(_readiness(no_go_scope=[]), now_at=NOW)

    assert result.valid is False
    assert "MISSING_CODEX_STARTUP_READINESS_FIELD: no_go_scope" in result.errors
