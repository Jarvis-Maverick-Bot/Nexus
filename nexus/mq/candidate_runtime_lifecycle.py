"""Candidate runtime lifecycle evaluation for WBS 7.18."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from nexus.mq.agent_registry import AgentRegistryRecord


@dataclass
class CandidateLifecycleDecision:
    accepted: bool
    lifecycle_state: str
    errors: list[str] = field(default_factory=list)
    not_business_completion: bool = True


def evaluate_candidate_runtime_lifecycle(
    record: Optional[AgentRegistryRecord],
    *,
    now_at: str,
) -> CandidateLifecycleDecision:
    if record is None:
        return CandidateLifecycleDecision(False, "unregistered", ["REGISTRY_RECORD_NOT_FOUND"])

    errors: list[str] = []
    if record.registry_status != "active":
        errors.append(f"REGISTRY_NOT_ACTIVE: {record.registry_status}")
    if record.initialization_status != "ready":
        errors.append(f"INITIALIZATION_NOT_READY: {record.initialization_status}")
    if not record.startup_packet_ref:
        errors.append("STARTUP_PACKET_MISSING")
    if not record.readiness_evidence_ref:
        errors.append("READINESS_EVIDENCE_MISSING")
    if record.readiness_blocker:
        errors.append(f"READINESS_BLOCKED: {record.readiness_blocker}")
    if not record.not_business_completion:
        errors.append("RUNTIME_LIFECYCLE_CANNOT_BE_BUSINESS_COMPLETION")
    errors.extend(_startup_freshness_errors(record, now_at=now_at))
    if record.presence_state in {"stale", "offline", "draining"}:
        errors.append(f"PRESENCE_BLOCKS_CLAIM: {record.presence_state}")
    if not record.accepting_new_work:
        errors.append("NOT_ACCEPTING_NEW_WORK")

    if errors:
        return CandidateLifecycleDecision(False, _blocked_state(record), _dedupe(errors))
    if record.presence_state == "idle":
        return CandidateLifecycleDecision(True, "eligible_for_claim")
    return CandidateLifecycleDecision(False, record.presence_state, [f"PRESENCE_NOT_ELIGIBLE: {record.presence_state}"])


def _startup_freshness_errors(record: AgentRegistryRecord, *, now_at: str) -> list[str]:
    if not record.startup_packet_expires_at:
        return ["STARTUP_PACKET_FRESHNESS_UNDECLARED"]
    expires_dt = _parse_iso(record.startup_packet_expires_at)
    now_dt = _parse_iso(now_at)
    if expires_dt is None or now_dt is None:
        return ["STARTUP_PACKET_FRESHNESS_INVALID"]
    if expires_dt <= now_dt:
        return ["STARTUP_PACKET_EXPIRED"]
    return []


def _blocked_state(record: AgentRegistryRecord) -> str:
    if record.registry_status in {"revoked", "suspended", "quarantined"}:
        return record.registry_status
    if record.initialization_status == "quarantined":
        return "quarantined"
    if record.presence_state in {"stale", "offline", "draining"}:
        return record.presence_state
    return "validating"


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
