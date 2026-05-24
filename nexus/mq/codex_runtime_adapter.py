"""Codex-specific runtime registration and readiness records for WBS 7.19.13."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from nexus.mq.agent_registry import AgentRegistryRecord
from nexus.mq.agent_registry_events import secret_material_errors


CODEX_RUNTIME_REGISTRATION_SCHEMA_VERSION = "4.19.codex.runtime_registration.v1"
CODEX_STARTUP_READINESS_SCHEMA_VERSION = "4.19.codex.startup_readiness.v1"


@dataclass
class CodexValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


@dataclass
class CodexRuntimeRegistration:
    agent_id: str
    runtime_instance_id: str
    host_ref: str
    owner_principal_id: str
    capabilities: list[str]
    authority_scopes: list[str]
    allowed_task_boundaries: list[str]
    allowed_workspace_refs: list[str]
    allowed_write_surfaces: list[str]
    prohibited_write_surfaces: list[str]
    startup_packet_ref: str
    readiness_evidence_ref: str
    startup_packet_expires_at: str
    trust_material_ref: str
    credential_ref: str
    runtime_type: str = "coding_agent"
    runtime_provider: str = "codex"
    role: str = "codex"
    registry_status: str = "active"
    initialization_status: str = "ready"
    presence_state: str = "idle"
    accepting_new_work: bool = True
    heartbeat_ttl_seconds: int = 60
    runtime_version: Optional[str] = None
    schema_version: str = CODEX_RUNTIME_REGISTRATION_SCHEMA_VERSION
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CodexStartupReadiness:
    readiness_id: str
    runtime_instance_id: str
    startup_packet_ref: str
    readiness_evidence_ref: str
    startup_packet_expires_at: str
    validated_at: str
    allowed_workspace_refs: list[str]
    allowed_tools: list[str]
    no_go_scope: list[str]
    status: str
    schema_version: str = CODEX_STARTUP_READINESS_SCHEMA_VERSION
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_codex_runtime_registration(registration: CodexRuntimeRegistration) -> CodexValidationResult:
    errors: list[str] = []
    if registration.schema_version != CODEX_RUNTIME_REGISTRATION_SCHEMA_VERSION:
        errors.append("UNSUPPORTED_CODEX_RUNTIME_REGISTRATION_SCHEMA")
    if registration.not_business_completion is not True:
        errors.append("CODEX_RUNTIME_REGISTRATION_CANNOT_BE_BUSINESS_COMPLETION")
    if registration.runtime_type != "coding_agent":
        errors.append(f"CODEX_RUNTIME_TYPE_MUST_BE_CODING_AGENT: {registration.runtime_type}")
    if registration.runtime_provider != "codex":
        errors.append(f"CODEX_RUNTIME_PROVIDER_MUST_BE_CODEX: {registration.runtime_provider}")
    if registration.role != "codex":
        errors.append(f"CODEX_RUNTIME_ROLE_MUST_BE_CODEX: {registration.role}")
    for field_name in (
        "agent_id",
        "runtime_instance_id",
        "host_ref",
        "owner_principal_id",
        "capabilities",
        "authority_scopes",
        "allowed_task_boundaries",
        "allowed_workspace_refs",
        "allowed_write_surfaces",
        "startup_packet_ref",
        "readiness_evidence_ref",
        "startup_packet_expires_at",
        "trust_material_ref",
        "credential_ref",
    ):
        if not getattr(registration, field_name):
            errors.append(f"MISSING_CODEX_RUNTIME_REGISTRATION_FIELD: {field_name}")
    if registration.heartbeat_ttl_seconds <= 0:
        errors.append("INVALID_CODEX_HEARTBEAT_TTL")
    errors.extend(secret_material_errors(registration.to_dict(), path="codex_runtime_registration"))
    return CodexValidationResult(valid=not errors, errors=_dedupe(errors))


def validate_codex_startup_readiness(
    readiness: CodexStartupReadiness,
    *,
    now_at: str,
) -> CodexValidationResult:
    errors: list[str] = []
    if readiness.schema_version != CODEX_STARTUP_READINESS_SCHEMA_VERSION:
        errors.append("UNSUPPORTED_CODEX_STARTUP_READINESS_SCHEMA")
    if readiness.not_business_completion is not True:
        errors.append("CODEX_STARTUP_READINESS_CANNOT_BE_BUSINESS_COMPLETION")
    for field_name in (
        "readiness_id",
        "runtime_instance_id",
        "startup_packet_ref",
        "readiness_evidence_ref",
        "startup_packet_expires_at",
        "validated_at",
        "allowed_workspace_refs",
        "allowed_tools",
        "no_go_scope",
        "status",
    ):
        if not getattr(readiness, field_name):
            errors.append(f"MISSING_CODEX_STARTUP_READINESS_FIELD: {field_name}")
    if readiness.status not in {"not_started", "validating", "ready", "failed", "expired", "quarantined"}:
        errors.append(f"UNSUPPORTED_CODEX_STARTUP_READINESS_STATUS: {readiness.status}")
    expires_dt = _parse_iso(readiness.startup_packet_expires_at)
    now_dt = _parse_iso(now_at)
    if expires_dt is None or now_dt is None:
        errors.append("CODEX_STARTUP_PACKET_FRESHNESS_INVALID")
    elif expires_dt <= now_dt:
        errors.append("CODEX_STARTUP_PACKET_EXPIRED")
    errors.extend(secret_material_errors(readiness.to_dict(), path="codex_startup_readiness"))
    return CodexValidationResult(valid=not errors, errors=_dedupe(errors))


def build_codex_registry_record(
    *,
    registration: CodexRuntimeRegistration,
    now_at: str,
) -> AgentRegistryRecord:
    validation = validate_codex_runtime_registration(registration)
    if not validation.valid:
        raise ValueError("; ".join(validation.errors))
    return AgentRegistryRecord(
        agent_id=registration.agent_id,
        runtime_instance_id=registration.runtime_instance_id,
        role=registration.role,
        owner_principal_id=registration.owner_principal_id,
        runtime_type=registration.runtime_type,
        channel_bindings=[],
        capabilities=list(registration.capabilities),
        authority_scopes=list(registration.authority_scopes),
        allowed_task_boundaries=list(registration.allowed_task_boundaries),
        initialization_status=registration.initialization_status,
        registry_status=registration.registry_status,
        presence_state=registration.presence_state,
        heartbeat_ttl_seconds=registration.heartbeat_ttl_seconds,
        last_heartbeat_at=now_at,
        current_assignment_refs=[],
        protocol_versions_supported=["3.5", "4.19"],
        trust_material_ref=registration.trust_material_ref,
        startup_packet_ref=registration.startup_packet_ref,
        readiness_evidence_ref=registration.readiness_evidence_ref,
        startup_packet_expires_at=registration.startup_packet_expires_at,
        created_at=now_at,
        updated_at=now_at,
        privacy_scopes=["project"],
        accepting_new_work=registration.accepting_new_work,
        runtime_provider=registration.runtime_provider,
        runtime_version=registration.runtime_version,
        host_ref=registration.host_ref,
        source_repo_refs=list(registration.allowed_workspace_refs),
        credential_ref=registration.credential_ref,
    )


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error not in deduped:
            deduped.append(error)
    return deduped
