"""Heartbeat policy defaults for WBS 7.9 manual heartbeat runtime."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HeartbeatPolicy:
    heartbeat_interval_seconds: int = 15
    heartbeat_ttl_seconds: int = 60
    stale_to_offline_grace_seconds: int = 180
    max_clock_skew_seconds: int = 30
    degraded_flap_threshold: int = 3
    degraded_window_seconds: int = 300
    supervisor_mode: str = "manual"

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.heartbeat_interval_seconds <= 0:
            errors.append("INVALID_HEARTBEAT_INTERVAL")
        if self.heartbeat_ttl_seconds <= 0:
            errors.append("INVALID_HEARTBEAT_TTL")
        if self.stale_to_offline_grace_seconds < 0:
            errors.append("INVALID_STALE_TO_OFFLINE_GRACE")
        if self.max_clock_skew_seconds < 0:
            errors.append("INVALID_CLOCK_SKEW")
        if self.degraded_flap_threshold <= 0:
            errors.append("INVALID_DEGRADED_FLAP_THRESHOLD")
        if self.degraded_window_seconds <= 0:
            errors.append("INVALID_DEGRADED_WINDOW")
        if self.supervisor_mode != "manual":
            errors.append("HEARTBEAT_DAEMON_MODE_NOT_AUTHORIZED")
        return errors


@dataclass
class HeartbeatPolicyValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


def validate_heartbeat_policy(policy: HeartbeatPolicy) -> HeartbeatPolicyValidationResult:
    errors = policy.validate()
    return HeartbeatPolicyValidationResult(valid=not errors, errors=errors)
