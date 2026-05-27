"""Heartbeat freshness and presence projection for 4.19 real-agent runtime supply."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class HeartbeatPresencePolicy:
    heartbeat_interval_seconds: int = 15
    heartbeat_ttl_seconds: int = 60
    stale_to_offline_grace_seconds: int = 180

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.heartbeat_interval_seconds <= 0:
            errors.append("INVALID_HEARTBEAT_INTERVAL")
        if self.heartbeat_ttl_seconds <= 0:
            errors.append("INVALID_HEARTBEAT_TTL")
        if self.heartbeat_ttl_seconds < self.heartbeat_interval_seconds:
            errors.append("HEARTBEAT_TTL_SHORTER_THAN_INTERVAL")
        if self.stale_to_offline_grace_seconds < 0:
            errors.append("INVALID_STALE_TO_OFFLINE_GRACE")
        return errors


@dataclass
class HeartbeatPresenceRecord:
    runtime_instance_id: str
    heartbeat_sequence: int
    last_heartbeat_at: str
    load_score: float = 0.0
    accepting_new_work: bool = True
    presence_state: str = "idle"
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HeartbeatPresenceResult:
    accepted: bool
    runtime_instance_id: str
    presence_state: str
    dispatch_fresh: bool
    heartbeat_sequence: int = 0
    last_heartbeat_at: str = ""
    errors: list[str] = field(default_factory=list)
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class HeartbeatPresenceController:
    def __init__(self, *, policy: HeartbeatPresencePolicy | None = None) -> None:
        self.policy = policy or HeartbeatPresencePolicy()
        errors = self.policy.validate()
        if errors:
            raise ValueError("; ".join(errors))
        self._records: dict[str, HeartbeatPresenceRecord] = {}

    def record_heartbeat(
        self,
        *,
        runtime_instance_id: str,
        sequence: int,
        observed_at: str,
        load_score: float = 0.0,
        accepting_new_work: bool = True,
    ) -> HeartbeatPresenceResult:
        current = self._records.get(runtime_instance_id)
        if current is not None and sequence <= current.heartbeat_sequence:
            return HeartbeatPresenceResult(
                accepted=False,
                runtime_instance_id=runtime_instance_id,
                presence_state=current.presence_state,
                dispatch_fresh=False,
                heartbeat_sequence=current.heartbeat_sequence,
                last_heartbeat_at=current.last_heartbeat_at,
                errors=["HEARTBEAT_SEQUENCE_REGRESSION"],
            )
        presence_state = "idle" if accepting_new_work else "busy"
        self._records[runtime_instance_id] = HeartbeatPresenceRecord(
            runtime_instance_id=runtime_instance_id,
            heartbeat_sequence=sequence,
            last_heartbeat_at=observed_at,
            load_score=load_score,
            accepting_new_work=accepting_new_work,
            presence_state=presence_state,
        )
        return HeartbeatPresenceResult(
            accepted=True,
            runtime_instance_id=runtime_instance_id,
            presence_state=presence_state,
            dispatch_fresh=accepting_new_work,
            heartbeat_sequence=sequence,
            last_heartbeat_at=observed_at,
        )

    def evaluate_presence(self, *, runtime_instance_id: str, now_at: str) -> HeartbeatPresenceResult:
        record = self._records.get(runtime_instance_id)
        if record is None:
            return HeartbeatPresenceResult(
                accepted=False,
                runtime_instance_id=runtime_instance_id,
                presence_state="offline",
                dispatch_fresh=False,
                errors=["HEARTBEAT_MISSING"],
            )
        heartbeat_at = _parse_iso(record.last_heartbeat_at)
        now = _parse_iso(now_at)
        if heartbeat_at is None or now is None:
            return HeartbeatPresenceResult(
                accepted=False,
                runtime_instance_id=runtime_instance_id,
                presence_state="stale",
                dispatch_fresh=False,
                heartbeat_sequence=record.heartbeat_sequence,
                last_heartbeat_at=record.last_heartbeat_at,
                errors=["HEARTBEAT_TIMESTAMP_INVALID"],
            )
        elapsed = (now - heartbeat_at).total_seconds()
        if elapsed > self.policy.heartbeat_ttl_seconds + self.policy.stale_to_offline_grace_seconds:
            state = "offline"
            errors = ["RUNTIME_OFFLINE_BY_TTL"]
            fresh = False
        elif elapsed > self.policy.heartbeat_ttl_seconds:
            state = "stale"
            errors = ["HEARTBEAT_STALE"]
            fresh = False
        else:
            state = "idle" if record.accepting_new_work else "busy"
            errors = []
            fresh = record.accepting_new_work
        record.presence_state = state
        return HeartbeatPresenceResult(
            accepted=not errors,
            runtime_instance_id=runtime_instance_id,
            presence_state=state,
            dispatch_fresh=fresh,
            heartbeat_sequence=record.heartbeat_sequence,
            last_heartbeat_at=record.last_heartbeat_at,
            errors=errors,
        )

    def get(self, runtime_instance_id: str) -> HeartbeatPresenceRecord | None:
        return self._records.get(runtime_instance_id)


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
