"""Capacity-before-claim contracts for candidate runtimes."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from nexus.mq.agent_registry_events import secret_material_errors


CAPACITY_SCHEMA_VERSION = "4.19.candidate.capacity.v1"
BLOCKING_LOAD_STATES = {"draining", "offline", "stale", "unknown"}


@dataclass
class CandidateRuntimeCapacitySnapshot:
    runtime_instance_id: str
    capacity_revision: int
    observed_at: str
    accepting_new_work: bool
    active_assignment_count: int
    max_concurrent_assignments: int
    load_state: str
    supported_claim_classes: list[str]
    evidence_ref: str
    schema_version: str = CAPACITY_SCHEMA_VERSION
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CapacityDecision:
    accepted: bool
    errors: list[str] = field(default_factory=list)
    capacity_revision: Optional[int] = None
    not_business_completion: bool = True


def evaluate_capacity_before_claim(
    snapshot: Optional[CandidateRuntimeCapacitySnapshot],
    *,
    runtime_instance_id: str,
    required_claim_class: str,
    now_at: str,
    max_capacity_age_seconds: int = 60,
) -> CapacityDecision:
    if snapshot is None:
        return CapacityDecision(False, ["CAPACITY_SNAPSHOT_MISSING"])
    errors = validate_capacity_snapshot(snapshot, now_at=now_at, max_capacity_age_seconds=max_capacity_age_seconds)
    if snapshot.runtime_instance_id != runtime_instance_id:
        errors.append("CAPACITY_RUNTIME_INSTANCE_MISMATCH")
    if required_claim_class not in snapshot.supported_claim_classes:
        errors.append("CAPACITY_CLAIM_CLASS_UNSUPPORTED")
    if not snapshot.accepting_new_work:
        errors.append("CAPACITY_NOT_ACCEPTING_NEW_WORK")
    if snapshot.active_assignment_count >= snapshot.max_concurrent_assignments:
        errors.append("CAPACITY_LIMIT_EXCEEDED")
    if snapshot.load_state in BLOCKING_LOAD_STATES:
        errors.append(f"CAPACITY_LOAD_STATE_BLOCKED: {snapshot.load_state}")
    return CapacityDecision(
        accepted=not errors,
        errors=_dedupe(errors),
        capacity_revision=snapshot.capacity_revision,
    )


def validate_capacity_snapshot(
    snapshot: CandidateRuntimeCapacitySnapshot,
    *,
    now_at: str,
    max_capacity_age_seconds: int = 60,
) -> list[str]:
    errors: list[str] = []
    if snapshot.schema_version != CAPACITY_SCHEMA_VERSION:
        errors.append("UNSUPPORTED_CAPACITY_SCHEMA")
    if snapshot.not_business_completion is not True:
        errors.append("CAPACITY_CANNOT_BE_BUSINESS_COMPLETION")
    if not snapshot.runtime_instance_id:
        errors.append("MISSING_CAPACITY_RUNTIME_INSTANCE_ID")
    if snapshot.capacity_revision <= 0:
        errors.append("INVALID_CAPACITY_REVISION")
    if snapshot.active_assignment_count < 0:
        errors.append("INVALID_ACTIVE_ASSIGNMENT_COUNT")
    if snapshot.max_concurrent_assignments <= 0:
        errors.append("INVALID_MAX_CONCURRENT_ASSIGNMENTS")
    if not snapshot.load_state:
        errors.append("MISSING_LOAD_STATE")
    if not snapshot.supported_claim_classes:
        errors.append("MISSING_SUPPORTED_CLAIM_CLASSES")
    if not snapshot.evidence_ref:
        errors.append("MISSING_CAPACITY_EVIDENCE_REF")
    observed_dt = _parse_iso(snapshot.observed_at)
    now_dt = _parse_iso(now_at)
    if observed_dt is None or now_dt is None:
        errors.append("CAPACITY_TIME_INVALID")
    elif (now_dt - observed_dt).total_seconds() > max_capacity_age_seconds:
        errors.append("CAPACITY_SNAPSHOT_STALE")
    errors.extend(secret_material_errors(snapshot.to_dict(), path="capacity"))
    return _dedupe(errors)


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
