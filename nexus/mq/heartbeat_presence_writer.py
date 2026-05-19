"""Registry-backed heartbeat presence writer for WBS 7.9."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from nexus.mq.agent_registry import AgentRegistryRecord
from nexus.mq.agent_registry_events import AgentRegistryEvent
from nexus.mq.agent_registry_service import AgentRegistryService
from nexus.mq.heartbeat_policy import HeartbeatPolicy
from nexus.mq.heartbeat_runtime import HeartbeatPacket, validate_heartbeat_packet


@dataclass
class HeartbeatWriteResult:
    accepted: bool
    record: Optional[AgentRegistryRecord] = None
    revision: Optional[int] = None
    errors: list[str] = field(default_factory=list)
    event: Optional[AgentRegistryEvent] = None
    not_business_completion: bool = True


@dataclass
class TtlEvaluationResult:
    transitioned: bool
    record: Optional[AgentRegistryRecord]
    revision: Optional[int]
    presence_state: Optional[str]
    errors: list[str] = field(default_factory=list)
    not_business_completion: bool = True


class HeartbeatPresenceWriter:
    def __init__(self, registry_service: AgentRegistryService, policy: HeartbeatPolicy):
        self._registry_service = registry_service
        self._policy = policy

    def apply_heartbeat(self, packet: HeartbeatPacket, *, now_at: str) -> HeartbeatWriteResult:
        read = self._registry_service.read_registry_record(packet.agent_id, now_at=now_at)
        previous_sequence = self._registry_service.get_heartbeat_sequence(packet.agent_id)
        validation = validate_heartbeat_packet(
            packet,
            current_record=read.record,
            current_revision=read.revision,
            policy=self._policy,
            previous_sequence=previous_sequence,
            now_at=now_at,
        )
        if not read.accepted or not validation.valid or read.revision is None:
            return HeartbeatWriteResult(
                accepted=False,
                errors=_dedupe([*read.errors, *validation.errors]),
            )
        accepting_new_work = packet.accepting_new_work and packet.desired_presence_state == "idle"
        write = self._registry_service.write_presence_update(
            packet.agent_id,
            runtime_instance_id=packet.runtime_instance_id,
            presence_state=packet.desired_presence_state,
            heartbeat_at=packet.emitted_at,
            heartbeat_sequence=packet.heartbeat_sequence,
            expected_revision=read.revision,
            load_score=packet.load_score,
            accepting_new_work=accepting_new_work,
            evidence_refs=packet.evidence_refs,
            health_summary_ref=packet.health_summary_ref,
            event_type="heartbeat_accepted",
            now_at=now_at,
        )
        return HeartbeatWriteResult(
            accepted=write.accepted,
            record=write.record,
            revision=write.revision,
            errors=write.errors,
            event=write.event,
        )


class HeartbeatTtlEvaluator:
    def __init__(self, registry_service: AgentRegistryService, policy: HeartbeatPolicy):
        self._registry_service = registry_service
        self._policy = policy

    def evaluate_agent(self, agent_id: str, *, now_at: str) -> TtlEvaluationResult:
        read = self._registry_service.read_registry_record(agent_id, now_at=now_at)
        if not read.accepted or read.record is None or read.revision is None:
            return TtlEvaluationResult(
                transitioned=False,
                record=read.record,
                revision=read.revision,
                presence_state=read.record.presence_state if read.record else None,
                errors=read.errors,
            )
        record = read.record
        now_dt = _parse_iso(now_at)
        last_dt = _parse_iso(record.last_heartbeat_at)
        if now_dt is None:
            return TtlEvaluationResult(
                transitioned=False,
                record=record,
                revision=read.revision,
                presence_state=record.presence_state,
                errors=["TTL_EVALUATION_TIME_INVALID"],
            )
        stale = last_dt is None or (now_dt - last_dt).total_seconds() > record.heartbeat_ttl_seconds
        if not stale:
            return TtlEvaluationResult(
                transitioned=False,
                record=record,
                revision=read.revision,
                presence_state=record.presence_state,
            )
        offline = (
            last_dt is None
            or (now_dt - last_dt).total_seconds() > record.heartbeat_ttl_seconds + self._policy.stale_to_offline_grace_seconds
        )
        target_presence = "offline" if offline else "stale"
        if record.presence_state == target_presence and record.accepting_new_work is False:
            return TtlEvaluationResult(
                transitioned=False,
                record=record,
                revision=read.revision,
                presence_state=record.presence_state,
            )
        write = self._registry_service.write_presence_update(
            agent_id,
            runtime_instance_id=record.runtime_instance_id,
            presence_state=target_presence,
            heartbeat_at=now_at,
            heartbeat_sequence=self._registry_service.get_heartbeat_sequence(agent_id),
            expected_revision=read.revision,
            load_score=record.load_score,
            accepting_new_work=False,
            event_type="heartbeat_offline" if target_presence == "offline" else "heartbeat_stale",
            now_at=now_at,
            allow_lifecycle_downgrade=True,
        )
        return TtlEvaluationResult(
            transitioned=write.accepted,
            record=write.record,
            revision=write.revision,
            presence_state=target_presence if write.accepted else record.presence_state,
            errors=write.errors,
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
        if error not in deduped:
            deduped.append(error)
    return deduped
