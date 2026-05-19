"""Inert assignment candidate/envelope model for WBS 7.10."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Optional

from nexus.mq.agent_registry import AgentRegistryRecord
from nexus.mq.agent_registry_events import secret_material_errors
from nexus.mq.dispatch_request import DispatchRequest


DISPATCH_ASSIGNMENT_SCHEMA_VERSION = "4.19.assignment.v1"
ASSIGNMENT_CANDIDATE_STATE = "candidate"
ASSIGNMENT_REJECTED_STATE = "rejected"
ASSIGNMENT_EXPIRED_STATE = "expired"
INERT_ASSIGNMENT_STATES = {
    ASSIGNMENT_CANDIDATE_STATE,
    ASSIGNMENT_REJECTED_STATE,
    ASSIGNMENT_EXPIRED_STATE,
}


@dataclass
class DispatchAssignmentCandidate:
    assignment_id: str
    idempotency_key: str
    request_id: str
    correlation_id: str
    work_ref: str
    target_agent_id: str
    target_runtime_instance_id: str
    registry_revision_seen: int
    heartbeat_timestamp_observed: str
    startup_packet_ref: str
    startup_packet_expires_at: str
    readiness_evidence_ref: str
    required_capability: str
    required_authority_scope: str
    required_privacy_scope: str
    allowed_task_boundary: str
    assignment_kind: str
    business_execution_allowed: bool
    no_go_scope: list[str]
    expires_at: str
    evidence_refs: list[str] = field(default_factory=list)
    state: str = ASSIGNMENT_CANDIDATE_STATE
    schema_version: str = DISPATCH_ASSIGNMENT_SCHEMA_VERSION
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AssignmentCandidateValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


def build_assignment_candidate(
    request: DispatchRequest,
    record: AgentRegistryRecord,
    *,
    registry_revision_seen: int,
    now_at: str,
) -> DispatchAssignmentCandidate:
    expires_at = request.expires_at or _expires_at(now_at, request.candidate_ttl_seconds)
    assignment_seed = "|".join(
        [
            request.request_id,
            request.correlation_id,
            record.agent_id,
            record.runtime_instance_id,
            str(registry_revision_seen),
            record.last_heartbeat_at or "",
        ]
    )
    digest = sha256(assignment_seed.encode("utf-8")).hexdigest()
    return DispatchAssignmentCandidate(
        assignment_id=f"assign-{digest[:16]}",
        idempotency_key=f"dispatch:{digest}",
        request_id=request.request_id,
        correlation_id=request.correlation_id,
        work_ref=request.work_ref,
        target_agent_id=record.agent_id,
        target_runtime_instance_id=record.runtime_instance_id,
        registry_revision_seen=registry_revision_seen,
        heartbeat_timestamp_observed=record.last_heartbeat_at or "",
        startup_packet_ref=record.startup_packet_ref or "",
        startup_packet_expires_at=record.startup_packet_expires_at or "",
        readiness_evidence_ref=record.readiness_evidence_ref or "",
        required_capability=request.required_capability,
        required_authority_scope=request.required_authority_scope,
        required_privacy_scope=request.required_privacy_scope,
        allowed_task_boundary=request.allowed_task_boundary,
        assignment_kind=request.assignment_kind,
        business_execution_allowed=False,
        no_go_scope=list(request.no_go_scope),
        expires_at=expires_at,
        evidence_refs=list(request.evidence_refs),
    )


def validate_assignment_candidate(candidate: DispatchAssignmentCandidate) -> AssignmentCandidateValidationResult:
    errors: list[str] = []
    if candidate.schema_version != DISPATCH_ASSIGNMENT_SCHEMA_VERSION:
        errors.append("UNSUPPORTED_ASSIGNMENT_SCHEMA")
    if candidate.state not in INERT_ASSIGNMENT_STATES:
        errors.append(f"UNSUPPORTED_INERT_ASSIGNMENT_STATE: {candidate.state}")
    if candidate.not_business_completion is not True:
        errors.append("ASSIGNMENT_CANDIDATE_CANNOT_BE_BUSINESS_COMPLETION")
    if candidate.business_execution_allowed:
        errors.append("ASSIGNMENT_CANDIDATE_CANNOT_ALLOW_BUSINESS_EXECUTION")
    for field_name in [
        "assignment_id",
        "idempotency_key",
        "request_id",
        "correlation_id",
        "target_agent_id",
        "target_runtime_instance_id",
        "startup_packet_ref",
        "startup_packet_expires_at",
        "readiness_evidence_ref",
        "expires_at",
    ]:
        if not getattr(candidate, field_name):
            errors.append(f"MISSING_{field_name.upper()}")
    if candidate.registry_revision_seen <= 0:
        errors.append("INVALID_REGISTRY_REVISION_SEEN")
    errors.extend(secret_material_errors(candidate.to_dict(), path="assignment_candidate"))
    return AssignmentCandidateValidationResult(valid=not errors, errors=_dedupe(errors))


def _expires_at(now_at: str, ttl_seconds: int) -> str:
    now_dt = _parse_iso(now_at) or datetime.now(timezone.utc)
    return (now_dt + timedelta(seconds=ttl_seconds)).isoformat()


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
