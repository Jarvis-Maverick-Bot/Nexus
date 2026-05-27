"""4.19 eligibility decision and reservation lease publish guards.

This module is source-only: it validates lifecycle decisions and reservation
leases before an assignment can be published. It does not publish to MQ or
mutate broker state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any


@dataclass
class RuntimeEligibilityDecision:
    decision_id: str
    request_id: str
    dispatch_run_id: str
    assignment_id: str
    target_agent_id: str
    target_runtime_instance_id: str
    accepted: bool
    policy_hash: str
    idempotency_key: str
    evidence_refs: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RuntimeReservationLease:
    lease_id: str
    lifecycle_decision_id: str
    assignment_id: str
    dispatch_run_id: str
    target_runtime_instance_id: str
    active: bool
    status: str
    expires_at: str
    policy_hash: str
    idempotency_key: str
    revoked: bool = False
    consumed_at: str = ""
    released_at: str = ""
    release_reason_ref: str = ""
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AssignmentPublishValidationResult:
    accepted: bool
    errors: list[str] = field(default_factory=list)
    not_business_completion: bool = True


def validate_assignment_publish(
    *,
    decision: RuntimeEligibilityDecision | None,
    lease: RuntimeReservationLease | None,
    assignment_id: str,
    dispatch_run_id: str,
    runtime_instance_id: str,
    idempotency_key: str,
    now_at: str,
) -> AssignmentPublishValidationResult:
    errors: list[str] = []
    if not assignment_id:
        errors.append("MISSING_ASSIGNMENT_ID")
    if not dispatch_run_id:
        errors.append("MISSING_DISPATCH_RUN_ID")
    if not runtime_instance_id:
        errors.append("MISSING_RUNTIME_INSTANCE_ID")
    if not idempotency_key:
        errors.append("MISSING_IDEMPOTENCY_KEY")

    if decision is None:
        errors.append("MISSING_LIFECYCLE_DECISION")
    else:
        errors.extend(_decision_errors(decision, assignment_id, dispatch_run_id, runtime_instance_id, idempotency_key))

    if lease is None:
        errors.append("MISSING_RESERVATION_LEASE")
    else:
        errors.extend(_lease_errors(lease, decision, assignment_id, dispatch_run_id, runtime_instance_id, idempotency_key, now_at))

    return AssignmentPublishValidationResult(accepted=not errors, errors=_dedupe(errors))


def consume_reservation_lease(lease: RuntimeReservationLease, *, consumed_at: str) -> RuntimeReservationLease:
    return replace(lease, active=False, status="consumed", consumed_at=consumed_at)


def release_reservation_lease(
    lease: RuntimeReservationLease,
    *,
    released_at: str,
    reason_ref: str,
) -> RuntimeReservationLease:
    return replace(lease, active=False, status="released", released_at=released_at, release_reason_ref=reason_ref)


def _decision_errors(
    decision: RuntimeEligibilityDecision,
    assignment_id: str,
    dispatch_run_id: str,
    runtime_instance_id: str,
    idempotency_key: str,
) -> list[str]:
    errors: list[str] = []
    if not decision.decision_id:
        errors.append("MISSING_LIFECYCLE_DECISION_ID")
    if not decision.accepted:
        errors.append("LIFECYCLE_DECISION_NOT_ALLOWED")
    if decision.assignment_id != assignment_id:
        errors.append("DECISION_ASSIGNMENT_ID_MISMATCH")
    if decision.dispatch_run_id != dispatch_run_id:
        errors.append("DECISION_DISPATCH_RUN_ID_MISMATCH")
    if decision.target_runtime_instance_id != runtime_instance_id:
        errors.append("DECISION_RUNTIME_ID_MISMATCH")
    if decision.idempotency_key != idempotency_key:
        errors.append("DECISION_IDEMPOTENCY_KEY_MISMATCH")
    if decision.not_business_completion is not True:
        errors.append("LIFECYCLE_DECISION_CANNOT_BE_BUSINESS_COMPLETION")
    return errors


def _lease_errors(
    lease: RuntimeReservationLease,
    decision: RuntimeEligibilityDecision | None,
    assignment_id: str,
    dispatch_run_id: str,
    runtime_instance_id: str,
    idempotency_key: str,
    now_at: str,
) -> list[str]:
    errors: list[str] = []
    if not lease.lease_id:
        errors.append("MISSING_RESERVATION_LEASE_ID")
    if decision is not None:
        if lease.lifecycle_decision_id != decision.decision_id:
            errors.append("LIFECYCLE_DECISION_ID_MISMATCH")
        if lease.policy_hash != decision.policy_hash:
            errors.append("LEASE_POLICY_HASH_MISMATCH")
    if lease.assignment_id != assignment_id:
        errors.append("LEASE_ASSIGNMENT_ID_MISMATCH")
    if lease.dispatch_run_id != dispatch_run_id:
        errors.append("LEASE_DISPATCH_RUN_ID_MISMATCH")
    if lease.target_runtime_instance_id != runtime_instance_id:
        errors.append("LEASE_RUNTIME_ID_MISMATCH")
    if lease.idempotency_key != idempotency_key:
        errors.append("LEASE_IDEMPOTENCY_KEY_MISMATCH")
    if lease.status == "consumed":
        errors.append("RESERVATION_LEASE_CONSUMED")
    if lease.status == "released":
        errors.append("RESERVATION_LEASE_RELEASED")
    if lease.revoked or lease.status == "revoked":
        errors.append("RESERVATION_LEASE_REVOKED")
    if not lease.active or lease.status != "active":
        errors.append("RESERVATION_LEASE_NOT_ACTIVE")
    expires_at = _parse_iso(lease.expires_at)
    now = _parse_iso(now_at)
    if expires_at is None:
        errors.append("RESERVATION_LEASE_EXPIRY_INVALID")
    elif now is None:
        errors.append("VALIDATION_TIME_INVALID")
    elif expires_at <= now:
        errors.append("RESERVATION_LEASE_EXPIRED")
    if lease.not_business_completion is not True:
        errors.append("RESERVATION_LEASE_CANNOT_BE_BUSINESS_COMPLETION")
    return errors


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
        if error and error not in deduped:
            deduped.append(error)
    return deduped
