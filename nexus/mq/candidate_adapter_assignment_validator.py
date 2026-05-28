"""Candidate Adapter assignment intake validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from nexus.mq.candidate_adapter_subject_broker_policy import validate_assignment_subject
from nexus.mq.candidate_adapter_session_store import CandidateAdapterSession


@dataclass
class CandidateAssignmentEvent:
    assignment_id: str
    idempotency_key: str
    lifecycle_decision_id: str
    reservation_lease_id: str
    assignment_subject: str
    agent_id: str
    runtime_instance_id: str
    adapter_protocol_version: str
    no_go_scope: list[str]
    payload: dict[str, Any] = field(default_factory=dict)
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CandidateAssignmentEvent":
        return cls(
            assignment_id=str(payload.get("assignment_id") or ""),
            idempotency_key=str(payload.get("idempotency_key") or ""),
            lifecycle_decision_id=str(payload.get("lifecycle_decision_id") or ""),
            reservation_lease_id=str(payload.get("reservation_lease_id") or ""),
            assignment_subject=str(payload.get("assignment_subject") or ""),
            agent_id=str(payload.get("agent_id") or ""),
            runtime_instance_id=str(payload.get("runtime_instance_id") or ""),
            adapter_protocol_version=str(payload.get("adapter_protocol_version") or ""),
            no_go_scope=[str(item) for item in payload.get("no_go_scope") or []],
            payload=dict(payload.get("payload") or {}),
            not_business_completion=bool(payload.get("not_business_completion", True)),
        )


@dataclass
class CandidateReservationLease:
    lease_id: str
    lifecycle_decision_id: str
    assignment_id: str
    runtime_instance_id: str
    active: bool
    expires_at: str
    revoked: bool = False
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CandidateReservationLease":
        return cls(
            lease_id=str(payload.get("lease_id") or ""),
            lifecycle_decision_id=str(payload.get("lifecycle_decision_id") or ""),
            assignment_id=str(payload.get("assignment_id") or ""),
            runtime_instance_id=str(payload.get("runtime_instance_id") or ""),
            active=bool(payload.get("active")),
            expires_at=str(payload.get("expires_at") or ""),
            revoked=bool(payload.get("revoked")),
            not_business_completion=bool(payload.get("not_business_completion", True)),
        )


@dataclass
class CandidateAssignmentValidationResult:
    accepted: bool
    errors: list[str] = field(default_factory=list)
    assignment: CandidateAssignmentEvent | None = None
    not_business_completion: bool = True


def validate_candidate_assignment(
    assignment: CandidateAssignmentEvent,
    *,
    session: CandidateAdapterSession,
    lease: CandidateReservationLease | None,
    now_at: str | None = None,
) -> CandidateAssignmentValidationResult:
    errors: list[str] = assignment_intake_prerequisite_errors(session, operation="ACK")
    if not assignment.assignment_id:
        errors.append("MISSING_ASSIGNMENT_ID")
    if not assignment.idempotency_key:
        errors.append("MISSING_IDEMPOTENCY_KEY")
    if not assignment.lifecycle_decision_id:
        errors.append("MISSING_LIFECYCLE_DECISION_ID")
    if not assignment.reservation_lease_id:
        errors.append("MISSING_RESERVATION_LEASE_ID")
    if assignment.agent_id != session.agent_id:
        errors.append("ASSIGNMENT_AGENT_ID_MISMATCH")
    if assignment.runtime_instance_id != session.runtime_instance_id:
        errors.append("ASSIGNMENT_RUNTIME_ID_MISMATCH")
    if assignment.adapter_protocol_version != session.adapter_protocol_version:
        errors.append("ADAPTER_PROTOCOL_VERSION_MISMATCH")
    if not set(session.no_go_scope).issubset(set(assignment.no_go_scope)):
        errors.append("NO_GO_SCOPE_MISMATCH")

    subject_decision = validate_assignment_subject(assignment.assignment_subject, session.allowed_subject_patterns)
    errors.extend(subject_decision.errors)
    errors.extend(_lease_errors(assignment, lease, now_at=now_at))
    errors.extend(_duplicate_assignment_binding_errors(assignment, session=session))
    if assignment.not_business_completion is not True:
        errors.append("ASSIGNMENT_CANNOT_BE_BUSINESS_COMPLETION")
    return CandidateAssignmentValidationResult(not errors, _dedupe(errors), assignment=assignment)


def assignment_intake_prerequisite_errors(
    session: CandidateAdapterSession,
    *,
    operation: str,
) -> list[str]:
    errors: list[str] = []
    normalized_operation = operation.upper().replace("-", "_")
    if not session.registration_ref:
        errors.append("MISSING_REGISTRATION_REF")
    if not session.startup_packet_ref:
        errors.append("MISSING_STARTUP_PACKET_REF")
    if not session.readiness_evidence_ref:
        errors.append("MISSING_READINESS_EVIDENCE_REF")
    if session.last_heartbeat_sequence <= 0:
        errors.append("MISSING_HEARTBEAT_FRESHNESS")
    if session.lifecycle_state in {"draining", "offline", "failed", "quarantined", "stale"}:
        errors.append(f"SESSION_NOT_ACCEPTING_ASSIGNMENTS: {session.lifecycle_state}")
    elif session.lifecycle_state not in _allowed_assignment_states(normalized_operation):
        errors.append(f"SESSION_NOT_READY_FOR_ASSIGNMENT_{normalized_operation}: {session.lifecycle_state}")
    return _dedupe(errors)


def _allowed_assignment_states(operation: str) -> set[str]:
    if operation == "ACK":
        return {"idle", "assigned"}
    return {"idle"}


def _lease_errors(
    assignment: CandidateAssignmentEvent,
    lease: CandidateReservationLease | None,
    *,
    now_at: str | None,
) -> list[str]:
    errors: list[str] = []
    if lease is None:
        errors.append("RESERVATION_LEASE_NOT_FOUND")
        return errors
    if lease.lease_id != assignment.reservation_lease_id:
        errors.append("RESERVATION_LEASE_ID_MISMATCH")
    if lease.lifecycle_decision_id != assignment.lifecycle_decision_id:
        errors.append("LIFECYCLE_DECISION_ID_MISMATCH")
    if lease.assignment_id != assignment.assignment_id:
        errors.append("LEASE_ASSIGNMENT_ID_MISMATCH")
    if lease.runtime_instance_id != assignment.runtime_instance_id:
        errors.append("LEASE_RUNTIME_ID_MISMATCH")
    if not lease.active:
        errors.append("RESERVATION_LEASE_INACTIVE")
    if lease.revoked:
        errors.append("RESERVATION_LEASE_REVOKED")
    if now_at and _parse_iso(lease.expires_at) and _parse_iso(lease.expires_at) <= _parse_iso(now_at):
        errors.append("RESERVATION_LEASE_EXPIRED")
    if lease.not_business_completion is not True:
        errors.append("RESERVATION_LEASE_CANNOT_BE_BUSINESS_COMPLETION")
    return errors


def _duplicate_assignment_binding_errors(
    assignment: CandidateAssignmentEvent,
    *,
    session: CandidateAdapterSession,
) -> list[str]:
    try:
        index = session.active_assignment_refs.index(assignment.assignment_id)
    except ValueError:
        return []

    errors: list[str] = []
    checks = (
        (session.active_idempotency_keys, assignment.idempotency_key, "DUPLICATE_ASSIGNMENT_IDEMPOTENCY_CONFLICT"),
        (session.active_decision_ids, assignment.lifecycle_decision_id, "DUPLICATE_ASSIGNMENT_DECISION_ID_CONFLICT"),
        (session.active_reservation_lease_ids, assignment.reservation_lease_id, "DUPLICATE_ASSIGNMENT_LEASE_ID_CONFLICT"),
    )
    for recorded_values, current_value, error_code in checks:
        recorded_value = recorded_values[index] if index < len(recorded_values) else ""
        if recorded_value != current_value:
            errors.append(error_code)
    if errors:
        return ["DUPLICATE_ASSIGNMENT_BINDING_CONFLICT"] + errors
    return []


def _parse_iso(value: str | None) -> datetime | None:
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
