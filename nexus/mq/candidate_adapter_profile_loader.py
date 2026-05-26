"""Candidate Adapter onboarding profile loading and validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import hashlib
import json

from nexus.mq.agent_registry_events import secret_material_errors
from nexus.mq.candidate_adapter_subject_broker_policy import (
    validate_broker_endpoint,
    validate_subject_patterns,
)


CANDIDATE_ADAPTER_PROFILE_SCHEMA_VERSION = "4.19.candidate_adapter.profile.v1"
CANDIDATE_ADAPTER_PROTOCOL_VERSION = "4.19.candidate_adapter.v1"


@dataclass
class CandidateAdapterProfile:
    agent_id: str
    runtime_instance_id: str
    owner_principal_id: str
    runtime_type: str
    role: str
    capabilities: list[str]
    authority_scopes: list[str]
    privacy_scopes: list[str]
    no_go_scope: list[str]
    broker_profile_ref: str
    broker_url: str
    allowed_subject_patterns: list[str]
    allowed_message_families: list[str]
    evidence_output_ref: str
    trust_material_ref: str
    credential_ref: str
    profile_schema_version: str = CANDIDATE_ADAPTER_PROFILE_SCHEMA_VERSION
    adapter_protocol_version: str = CANDIDATE_ADAPTER_PROTOCOL_VERSION
    heartbeat_interval_seconds: int = 30
    heartbeat_ttl_seconds: int = 90
    local_only_authorized: bool = False
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CandidateAdapterProfileLoadResult:
    accepted: bool
    profile: CandidateAdapterProfile | None = None
    profile_digest: str = ""
    errors: list[str] = field(default_factory=list)
    not_business_completion: bool = True


def load_candidate_adapter_profile(
    path: str | Path,
    *,
    local_only_authorization: bool = False,
) -> CandidateAdapterProfileLoadResult:
    profile_path = Path(path)
    if not profile_path.exists():
        return CandidateAdapterProfileLoadResult(False, errors=[f"PROFILE_NOT_FOUND: {profile_path}"])
    try:
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return CandidateAdapterProfileLoadResult(False, errors=[f"PROFILE_JSON_INVALID: {exc.msg}"])
    if not isinstance(payload, dict):
        return CandidateAdapterProfileLoadResult(False, errors=["PROFILE_MUST_BE_JSON_OBJECT"])

    payload = dict(payload)
    payload["local_only_authorized"] = bool(local_only_authorization or payload.get("local_only_authorized"))
    profile = _profile_from_payload(payload)
    errors = validate_candidate_adapter_profile(profile, local_only_authorization=profile.local_only_authorized)
    if errors:
        return CandidateAdapterProfileLoadResult(False, profile=profile, errors=errors)
    return CandidateAdapterProfileLoadResult(True, profile=profile, profile_digest=profile_digest(profile))


def validate_candidate_adapter_profile(
    profile: CandidateAdapterProfile,
    *,
    local_only_authorization: bool = False,
) -> list[str]:
    errors: list[str] = []
    if profile.profile_schema_version != CANDIDATE_ADAPTER_PROFILE_SCHEMA_VERSION:
        errors.append(f"UNSUPPORTED_PROFILE_SCHEMA_VERSION: {profile.profile_schema_version}")
    if profile.adapter_protocol_version != CANDIDATE_ADAPTER_PROTOCOL_VERSION:
        errors.append(f"UNSUPPORTED_ADAPTER_PROTOCOL_VERSION: {profile.adapter_protocol_version}")
    if profile.not_business_completion is not True:
        errors.append("CANDIDATE_ADAPTER_PROFILE_CANNOT_BE_BUSINESS_COMPLETION")

    required_fields = (
        "agent_id",
        "runtime_instance_id",
        "owner_principal_id",
        "runtime_type",
        "role",
        "capabilities",
        "authority_scopes",
        "privacy_scopes",
        "no_go_scope",
        "broker_profile_ref",
        "broker_url",
        "allowed_subject_patterns",
        "allowed_message_families",
        "evidence_output_ref",
        "trust_material_ref",
        "credential_ref",
    )
    for field_name in required_fields:
        if not getattr(profile, field_name):
            errors.append(f"MISSING_PROFILE_FIELD: {field_name}")

    errors.extend(validate_broker_endpoint(profile.broker_url, local_only_authorization=local_only_authorization).errors)
    errors.extend(validate_subject_patterns(profile.allowed_subject_patterns).errors)
    errors.extend(secret_material_errors(profile.to_dict(), path="candidate_adapter_profile"))
    return _dedupe(errors)


def profile_digest(profile: CandidateAdapterProfile) -> str:
    authority_payload = {
        "profile_schema_version": profile.profile_schema_version,
        "adapter_protocol_version": profile.adapter_protocol_version,
        "agent_id": profile.agent_id,
        "runtime_instance_id": profile.runtime_instance_id,
        "owner_principal_id": profile.owner_principal_id,
        "runtime_type": profile.runtime_type,
        "role": profile.role,
        "capabilities": sorted(profile.capabilities),
        "authority_scopes": sorted(profile.authority_scopes),
        "privacy_scopes": sorted(profile.privacy_scopes),
        "no_go_scope": sorted(profile.no_go_scope),
        "broker_profile_ref": profile.broker_profile_ref,
        "broker_url": profile.broker_url,
        "allowed_subject_patterns": sorted(profile.allowed_subject_patterns),
        "allowed_message_families": sorted(profile.allowed_message_families),
        "evidence_output_ref": profile.evidence_output_ref,
        "trust_material_ref": profile.trust_material_ref,
        "credential_ref": profile.credential_ref,
        "heartbeat_interval_seconds": profile.heartbeat_interval_seconds,
        "heartbeat_ttl_seconds": profile.heartbeat_ttl_seconds,
    }
    encoded = json.dumps(authority_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _profile_from_payload(payload: dict[str, Any]) -> CandidateAdapterProfile:
    return CandidateAdapterProfile(
        agent_id=str(payload.get("agent_id") or ""),
        runtime_instance_id=str(payload.get("runtime_instance_id") or ""),
        owner_principal_id=str(payload.get("owner_principal_id") or ""),
        runtime_type=str(payload.get("runtime_type") or ""),
        role=str(payload.get("role") or ""),
        capabilities=_list_of_str(payload.get("capabilities")),
        authority_scopes=_list_of_str(payload.get("authority_scopes")),
        privacy_scopes=_list_of_str(payload.get("privacy_scopes")),
        no_go_scope=_list_of_str(payload.get("no_go_scope")),
        broker_profile_ref=str(payload.get("broker_profile_ref") or ""),
        broker_url=str(payload.get("broker_url") or ""),
        allowed_subject_patterns=_list_of_str(payload.get("allowed_subject_patterns")),
        allowed_message_families=_list_of_str(payload.get("allowed_message_families")),
        evidence_output_ref=str(payload.get("evidence_output_ref") or ""),
        trust_material_ref=str(payload.get("trust_material_ref") or ""),
        credential_ref=str(payload.get("credential_ref") or ""),
        profile_schema_version=str(
            payload.get("profile_schema_version") or CANDIDATE_ADAPTER_PROFILE_SCHEMA_VERSION
        ),
        adapter_protocol_version=str(
            payload.get("adapter_protocol_version") or CANDIDATE_ADAPTER_PROTOCOL_VERSION
        ),
        heartbeat_interval_seconds=int(payload.get("heartbeat_interval_seconds") or 30),
        heartbeat_ttl_seconds=int(payload.get("heartbeat_ttl_seconds") or 90),
        local_only_authorized=bool(payload.get("local_only_authorized")),
        not_business_completion=bool(payload.get("not_business_completion", True)),
    )


def _list_of_str(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error not in deduped:
            deduped.append(error)
    return deduped
