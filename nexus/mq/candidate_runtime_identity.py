"""Generic candidate-agent runtime identity contracts for WBS 7.18."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from nexus.mq.agent_registry import AgentRegistryRecord
from nexus.mq.agent_registry_events import secret_material_errors


CANDIDATE_PROFILE_SCHEMA_VERSION = "4.19.candidate.profile.v1"
CANDIDATE_RUNTIME_IDENTITY_SCHEMA_VERSION = "4.19.candidate.runtime_identity.v1"


@dataclass
class CandidateAgentProfile:
    agent_id: str
    candidate_profile_ref: str
    role: str
    capabilities: list[str]
    authority_scopes: list[str]
    privacy_scopes: list[str]
    allowed_task_boundaries: list[str]
    no_go_scope: list[str]
    business_dispatch_allowed: bool = False
    schema_version: str = CANDIDATE_PROFILE_SCHEMA_VERSION
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CandidateRuntimeIdentity:
    agent_id: str
    runtime_instance_id: str
    runtime_type: str
    runtime_provider: str
    host_ref: str
    owner_principal_id: str
    role: str
    candidate_profile_ref: str
    startup_packet_ref: str
    readiness_evidence_ref: str
    startup_packet_expires_at: str
    source_repo_refs: list[str]
    trust_material_ref: str
    credential_ref: str
    runtime_version: Optional[str] = None
    legacy_runtime_refs: list[str] = field(default_factory=list)
    schema_version: str = CANDIDATE_RUNTIME_IDENTITY_SCHEMA_VERSION
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CandidateValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


def validate_candidate_agent_profile(profile: CandidateAgentProfile) -> CandidateValidationResult:
    errors: list[str] = []
    if profile.schema_version != CANDIDATE_PROFILE_SCHEMA_VERSION:
        errors.append("UNSUPPORTED_CANDIDATE_PROFILE_SCHEMA")
    if profile.not_business_completion is not True:
        errors.append("CANDIDATE_PROFILE_CANNOT_BE_BUSINESS_COMPLETION")
    if profile.business_dispatch_allowed:
        errors.append("BUSINESS_DISPATCH_NOT_AUTHORIZED")
    for field_name in (
        "agent_id",
        "candidate_profile_ref",
        "role",
        "capabilities",
        "authority_scopes",
        "privacy_scopes",
        "allowed_task_boundaries",
        "no_go_scope",
    ):
        if not getattr(profile, field_name):
            errors.append(f"MISSING_CANDIDATE_PROFILE_FIELD: {field_name}")
    if "jarvis-only" in profile.candidate_profile_ref.lower():
        errors.append("CANDIDATE_PROFILE_MUST_BE_GENERIC_NOT_JARVIS_ONLY")
    errors.extend(secret_material_errors(profile.to_dict(), path="candidate_profile"))
    return CandidateValidationResult(valid=not errors, errors=_dedupe(errors))


def validate_candidate_runtime_identity(
    identity: CandidateRuntimeIdentity,
    *,
    profile: Optional[CandidateAgentProfile] = None,
) -> CandidateValidationResult:
    errors: list[str] = []
    if identity.schema_version != CANDIDATE_RUNTIME_IDENTITY_SCHEMA_VERSION:
        errors.append("UNSUPPORTED_CANDIDATE_RUNTIME_IDENTITY_SCHEMA")
    if identity.not_business_completion is not True:
        errors.append("CANDIDATE_RUNTIME_IDENTITY_CANNOT_BE_BUSINESS_COMPLETION")
    for field_name in (
        "agent_id",
        "runtime_instance_id",
        "runtime_type",
        "runtime_provider",
        "host_ref",
        "owner_principal_id",
        "role",
        "candidate_profile_ref",
        "startup_packet_ref",
        "readiness_evidence_ref",
        "startup_packet_expires_at",
        "source_repo_refs",
        "trust_material_ref",
        "credential_ref",
    ):
        if not getattr(identity, field_name):
            errors.append(f"MISSING_CANDIDATE_RUNTIME_IDENTITY_FIELD: {field_name}")
    if profile is not None:
        profile_validation = validate_candidate_agent_profile(profile)
        errors.extend(profile_validation.errors)
        if identity.agent_id != profile.agent_id:
            errors.append("CANDIDATE_AGENT_ID_MISMATCH")
        if identity.role != profile.role:
            errors.append("CANDIDATE_ROLE_MISMATCH")
        if identity.candidate_profile_ref != profile.candidate_profile_ref:
            errors.append("CANDIDATE_PROFILE_REF_MISMATCH")
    errors.extend(secret_material_errors(identity.to_dict(), path="candidate_runtime_identity"))
    return CandidateValidationResult(valid=not errors, errors=_dedupe(errors))


def build_candidate_registry_record(
    *,
    profile: CandidateAgentProfile,
    identity: CandidateRuntimeIdentity,
    now_at: str,
    heartbeat_ttl_seconds: int = 60,
    presence_state: str = "idle",
) -> AgentRegistryRecord:
    validation = validate_candidate_runtime_identity(identity, profile=profile)
    if not validation.valid:
        raise ValueError("; ".join(validation.errors))
    return AgentRegistryRecord(
        agent_id=identity.agent_id,
        runtime_instance_id=identity.runtime_instance_id,
        role=identity.role,
        owner_principal_id=identity.owner_principal_id,
        runtime_type=identity.runtime_type,
        channel_bindings=[],
        capabilities=list(profile.capabilities),
        authority_scopes=list(profile.authority_scopes),
        allowed_task_boundaries=list(profile.allowed_task_boundaries),
        initialization_status="ready",
        registry_status="active",
        presence_state=presence_state,
        heartbeat_ttl_seconds=heartbeat_ttl_seconds,
        last_heartbeat_at=now_at,
        current_assignment_refs=[],
        protocol_versions_supported=["3.5", "4.19"],
        trust_material_ref=identity.trust_material_ref,
        startup_packet_ref=identity.startup_packet_ref,
        readiness_evidence_ref=identity.readiness_evidence_ref,
        startup_packet_expires_at=identity.startup_packet_expires_at,
        created_at=now_at,
        updated_at=now_at,
        privacy_scopes=list(profile.privacy_scopes),
        accepting_new_work=True,
        candidate_profile_ref=identity.candidate_profile_ref,
        runtime_provider=identity.runtime_provider,
        runtime_version=identity.runtime_version,
        host_ref=identity.host_ref,
        source_repo_refs=list(identity.source_repo_refs),
        credential_ref=identity.credential_ref,
        legacy_runtime_refs=list(identity.legacy_runtime_refs),
    )


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error not in deduped:
            deduped.append(error)
    return deduped
