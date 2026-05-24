"""Registry/readiness/heartbeat observer for resident controller decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from nexus.mq.agent_registry import AgentRegistryRecord


@dataclass
class RuntimeObservationDecision:
    agent_id: str
    runtime_instance_id: str
    presence_state: str
    dispatch_eligible: bool
    errors: list[str] = field(default_factory=list)
    not_business_completion: bool = True


def evaluate_runtime_observation(
    record: AgentRegistryRecord,
    *,
    now_at: str,
    stale_after_missed_heartbeats: int = 1,
) -> RuntimeObservationDecision:
    errors: list[str] = []
    presence_state = record.presence_state
    heartbeat_dt = _parse_iso(record.last_heartbeat_at)
    now_dt = _parse_iso(now_at)
    if heartbeat_dt is None or now_dt is None:
        errors.append("HEARTBEAT_INVALID")
        presence_state = "stale"
    else:
        stale_after_seconds = record.heartbeat_ttl_seconds * max(1, stale_after_missed_heartbeats)
        if (now_dt - heartbeat_dt).total_seconds() > stale_after_seconds:
            errors.append("HEARTBEAT_STALE")
            presence_state = "stale"
    if record.registry_status != "active":
        errors.append(f"REGISTRY_NOT_ACTIVE: {record.registry_status}")
    if record.initialization_status != "ready":
        errors.append(f"INITIALIZATION_NOT_READY: {record.initialization_status}")
    if record.readiness_blocker:
        errors.append(f"READINESS_BLOCKED: {record.readiness_blocker}")
    if presence_state != "idle":
        errors.append(f"PRESENCE_NOT_DISPATCHABLE: {presence_state}")
    if not record.accepting_new_work:
        errors.append("NOT_ACCEPTING_NEW_WORK")
    return RuntimeObservationDecision(
        agent_id=record.agent_id,
        runtime_instance_id=record.runtime_instance_id,
        presence_state=presence_state,
        dispatch_eligible=not errors,
        errors=_dedupe(errors),
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
        if error and error not in deduped:
            deduped.append(error)
    return deduped
