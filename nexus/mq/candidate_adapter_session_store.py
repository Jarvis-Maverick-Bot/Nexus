"""Local Candidate Adapter session persistence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import json
import os

from nexus.mq.candidate_adapter_profile_loader import (
    CANDIDATE_ADAPTER_PROTOCOL_VERSION,
    CandidateAdapterProfile,
    profile_digest,
)


CANDIDATE_ADAPTER_SESSION_SCHEMA_VERSION = "4.19.candidate_adapter.session.v1"


@dataclass
class CandidateAdapterSession:
    session_id: str
    agent_id: str
    runtime_instance_id: str
    owner_principal_id: str
    runtime_type: str
    adapter_protocol_version: str
    broker_profile_ref: str
    broker_url: str
    authority_scopes: list[str]
    capabilities: list[str]
    no_go_scope: list[str]
    allowed_message_families: list[str]
    allowed_subject_patterns: list[str]
    evidence_output_ref: str
    profile_digest: str
    privacy_scopes: list[str] = field(default_factory=list)
    registration_ref: str = ""
    startup_packet_ref: str = ""
    readiness_evidence_ref: str = ""
    last_heartbeat_sequence: int = 0
    active_assignment_refs: list[str] = field(default_factory=list)
    active_decision_ids: list[str] = field(default_factory=list)
    active_reservation_lease_ids: list[str] = field(default_factory=list)
    active_idempotency_keys: list[str] = field(default_factory=list)
    lifecycle_state: str = "connected"
    schema_version: str = CANDIDATE_ADAPTER_SESSION_SCHEMA_VERSION
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CandidateAdapterSession":
        return cls(
            session_id=str(payload.get("session_id") or ""),
            agent_id=str(payload.get("agent_id") or ""),
            runtime_instance_id=str(payload.get("runtime_instance_id") or ""),
            owner_principal_id=str(payload.get("owner_principal_id") or ""),
            runtime_type=str(payload.get("runtime_type") or ""),
            adapter_protocol_version=str(payload.get("adapter_protocol_version") or ""),
            broker_profile_ref=str(payload.get("broker_profile_ref") or ""),
            broker_url=str(payload.get("broker_url") or ""),
            authority_scopes=_list_of_str(payload.get("authority_scopes")),
            capabilities=_list_of_str(payload.get("capabilities")),
            no_go_scope=_list_of_str(payload.get("no_go_scope")),
            allowed_message_families=_list_of_str(payload.get("allowed_message_families")),
            allowed_subject_patterns=_list_of_str(payload.get("allowed_subject_patterns")),
            evidence_output_ref=str(payload.get("evidence_output_ref") or ""),
            profile_digest=str(payload.get("profile_digest") or ""),
            privacy_scopes=_list_of_str(payload.get("privacy_scopes")),
            registration_ref=str(payload.get("registration_ref") or ""),
            startup_packet_ref=str(payload.get("startup_packet_ref") or ""),
            readiness_evidence_ref=str(payload.get("readiness_evidence_ref") or ""),
            last_heartbeat_sequence=int(payload.get("last_heartbeat_sequence") or 0),
            active_assignment_refs=_list_of_str(payload.get("active_assignment_refs")),
            active_decision_ids=_list_of_str(payload.get("active_decision_ids")),
            active_reservation_lease_ids=_list_of_str(payload.get("active_reservation_lease_ids")),
            active_idempotency_keys=_list_of_str(payload.get("active_idempotency_keys")),
            lifecycle_state=str(payload.get("lifecycle_state") or "connected"),
            schema_version=str(payload.get("schema_version") or CANDIDATE_ADAPTER_SESSION_SCHEMA_VERSION),
            not_business_completion=bool(payload.get("not_business_completion", True)),
        )


class CandidateAdapterSessionStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def bind(self, path: str | Path) -> "CandidateAdapterSessionStore":
        self.path = Path(path)
        return self

    def save(self, session: CandidateAdapterSession) -> CandidateAdapterSession:
        errors = validate_candidate_adapter_session(session)
        if errors:
            raise ValueError("; ".join(errors))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(session.to_dict(), sort_keys=True, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp_path, self.path)
        return session

    def load(self) -> CandidateAdapterSession:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        session = CandidateAdapterSession.from_dict(payload)
        errors = validate_candidate_adapter_session(session)
        if errors:
            raise ValueError("; ".join(errors))
        return session


def build_session_from_profile(profile: CandidateAdapterProfile, *, session_id: str | None = None) -> CandidateAdapterSession:
    return CandidateAdapterSession(
        session_id=session_id or f"candidate-session-{profile.agent_id}-{profile.runtime_instance_id}",
        agent_id=profile.agent_id,
        runtime_instance_id=profile.runtime_instance_id,
        owner_principal_id=profile.owner_principal_id,
        runtime_type=profile.runtime_type,
        adapter_protocol_version=profile.adapter_protocol_version,
        broker_profile_ref=profile.broker_profile_ref,
        broker_url=profile.broker_url,
        authority_scopes=list(profile.authority_scopes),
        capabilities=list(profile.capabilities),
        no_go_scope=list(profile.no_go_scope),
        allowed_message_families=list(profile.allowed_message_families),
        allowed_subject_patterns=list(profile.allowed_subject_patterns),
        evidence_output_ref=profile.evidence_output_ref,
        profile_digest=profile_digest(profile),
        privacy_scopes=list(profile.privacy_scopes),
    )


def validate_candidate_adapter_session(session: CandidateAdapterSession) -> list[str]:
    errors: list[str] = []
    if session.schema_version != CANDIDATE_ADAPTER_SESSION_SCHEMA_VERSION:
        errors.append("UNSUPPORTED_CANDIDATE_ADAPTER_SESSION_SCHEMA")
    if session.adapter_protocol_version != CANDIDATE_ADAPTER_PROTOCOL_VERSION:
        errors.append("UNSUPPORTED_ADAPTER_PROTOCOL_VERSION")
    if session.not_business_completion is not True:
        errors.append("CANDIDATE_ADAPTER_SESSION_CANNOT_BE_BUSINESS_COMPLETION")
    for field_name in (
        "session_id",
        "agent_id",
        "runtime_instance_id",
        "owner_principal_id",
        "runtime_type",
        "broker_profile_ref",
        "broker_url",
        "authority_scopes",
        "capabilities",
        "no_go_scope",
        "allowed_message_families",
        "allowed_subject_patterns",
        "evidence_output_ref",
        "profile_digest",
    ):
        if not getattr(session, field_name):
            errors.append(f"MISSING_SESSION_FIELD: {field_name}")
    return _dedupe(errors)


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
