"""Heartbeat packet contract and validation for WBS 7.9.

This module is intentionally transport-free. It validates manual heartbeat
packets and never starts a daemon, dispatches work, or mutates business state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import uuid

from nexus.mq.agent_registry import AgentRegistryRecord
from nexus.mq.agent_registry_events import secret_material_errors
from nexus.mq.heartbeat_policy import HeartbeatPolicy


HEARTBEAT_SCHEMA_VERSION = "4.19.heartbeat.v1"
DESIRED_PRESENCE_STATES = {"online", "idle", "busy", "degraded", "draining", "offline"}


@dataclass
class HeartbeatPacket:
    agent_id: str
    runtime_instance_id: str
    registry_revision_seen: int
    emitted_at: str
    heartbeat_sequence: int
    desired_presence_state: str
    startup_packet_ref: str
    readiness_evidence_ref: str
    heartbeat_id: str = field(default_factory=lambda: f"heartbeat-{uuid.uuid4().hex[:12]}")
    schema_version: str = HEARTBEAT_SCHEMA_VERSION
    load_score: float = 0.0
    accepting_new_work: bool = True
    evidence_refs: list[str] = field(default_factory=list)
    health_summary_ref: Optional[str] = None
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HeartbeatValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


def validate_heartbeat_packet(
    packet: HeartbeatPacket,
    *,
    current_record: Optional[AgentRegistryRecord],
    current_revision: Optional[int],
    policy: HeartbeatPolicy,
    previous_sequence: Optional[int] = None,
    now_at: Optional[str] = None,
) -> HeartbeatValidationResult:
    errors = policy.validate()
    if packet.schema_version != HEARTBEAT_SCHEMA_VERSION:
        errors.append(f"UNSUPPORTED_HEARTBEAT_SCHEMA: {packet.schema_version}")
    if packet.not_business_completion is not True:
        errors.append("HEARTBEAT_CANNOT_BE_BUSINESS_COMPLETION")
    if packet.desired_presence_state not in DESIRED_PRESENCE_STATES:
        errors.append(f"INVALID_HEARTBEAT_PRESENCE_STATE: {packet.desired_presence_state}")
    if packet.heartbeat_sequence <= 0:
        errors.append("INVALID_HEARTBEAT_SEQUENCE")
    if previous_sequence is not None and packet.heartbeat_sequence <= previous_sequence:
        errors.append("STALE_HEARTBEAT_SEQUENCE")
    if packet.registry_revision_seen <= 0:
        errors.append("MISSING_REGISTRY_REVISION")
    if current_revision is not None and packet.registry_revision_seen != current_revision:
        errors.append("STALE_REGISTRY_REVISION")
    if not 0 <= packet.load_score <= 1:
        errors.append("INVALID_HEARTBEAT_LOAD_SCORE")
    errors.extend(secret_material_errors(packet.to_dict(), path="heartbeat"))

    now_dt = _parse_iso(now_at) if now_at else datetime.now(timezone.utc)
    emitted_dt = _parse_iso(packet.emitted_at)
    if emitted_dt is None:
        errors.append("HEARTBEAT_EMITTED_AT_INVALID")
    elif now_dt is None:
        errors.append("HEARTBEAT_TIME_UNVERIFIABLE")
    else:
        skew = abs((now_dt - emitted_dt).total_seconds())
        if skew > policy.max_clock_skew_seconds:
            errors.append("HEARTBEAT_CLOCK_SKEW_EXCEEDED")

    if current_record is None:
        errors.append("REGISTRY_RECORD_NOT_FOUND")
        return HeartbeatValidationResult(valid=False, errors=_dedupe(errors))

    if packet.agent_id != current_record.agent_id:
        errors.append("AGENT_ID_MISMATCH")
    if packet.runtime_instance_id != current_record.runtime_instance_id:
        errors.append("RUNTIME_INSTANCE_MISMATCH")
    if current_record.registry_status != "active":
        errors.append(f"REGISTRY_NOT_ACTIVE: {current_record.registry_status}")
    if current_record.initialization_status != "ready":
        errors.append(f"INITIALIZATION_NOT_READY: {current_record.initialization_status}")
    if packet.startup_packet_ref != current_record.startup_packet_ref:
        errors.append("STARTUP_PACKET_REF_MISMATCH")
    if packet.readiness_evidence_ref != current_record.readiness_evidence_ref:
        errors.append("READINESS_EVIDENCE_REF_MISMATCH")
    if not current_record.startup_packet_ref or not current_record.readiness_evidence_ref:
        errors.append("READINESS_EVIDENCE_MISSING")
    if current_record.startup_packet_expires_at:
        expires_dt = _parse_iso(current_record.startup_packet_expires_at)
        if expires_dt is None:
            errors.append("STARTUP_PACKET_FRESHNESS_INVALID")
        elif now_dt is None:
            errors.append("REGISTRY_TRUTH_TIME_UNVERIFIABLE")
        elif expires_dt <= now_dt:
            errors.append("STARTUP_PACKET_EXPIRED")
    else:
        errors.append("STARTUP_PACKET_FRESHNESS_UNDECLARED")

    return HeartbeatValidationResult(valid=not errors, errors=_dedupe(errors))


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
