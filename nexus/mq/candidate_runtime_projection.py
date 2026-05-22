"""Read-only Agent Access projection for candidate runtimes."""

from __future__ import annotations

from typing import Any, Optional

from nexus.mq.agent_registry import AgentRegistryRecord
from nexus.mq.candidate_runtime_capacity import CandidateRuntimeCapacitySnapshot
from nexus.mq.candidate_runtime_scheduler import CandidateRuntimeClaim


CANDIDATE_RUNTIME_PROJECTION_FIELDS = {
    "projection_type",
    "agent_id",
    "candidate_profile_ref",
    "runtime_instance_id",
    "runtime_type",
    "runtime_provider",
    "runtime_version",
    "host_ref",
    "owner_principal_id",
    "registry_status",
    "initialization_status",
    "presence_state",
    "last_heartbeat_at",
    "heartbeat_ttl_seconds",
    "accepting_new_work",
    "capacity_revision",
    "capacity_observed_at",
    "active_assignment_count",
    "max_concurrent_assignments",
    "load_state",
    "claim_id",
    "claim_state",
    "stale_or_offline_reason",
    "evidence_refs",
    "read_only",
    "not_business_completion",
}


def build_candidate_runtime_projection(
    *,
    record: AgentRegistryRecord,
    capacity: Optional[CandidateRuntimeCapacitySnapshot] = None,
    claim: Optional[CandidateRuntimeClaim] = None,
    evidence_refs: Optional[list[str]] = None,
) -> dict[str, Any]:
    payload = {
        "projection_type": "candidate_runtime",
        "agent_id": record.agent_id,
        "candidate_profile_ref": record.candidate_profile_ref,
        "runtime_instance_id": record.runtime_instance_id,
        "runtime_type": record.runtime_type,
        "runtime_provider": record.runtime_provider,
        "runtime_version": record.runtime_version,
        "host_ref": record.host_ref,
        "owner_principal_id": record.owner_principal_id,
        "registry_status": record.registry_status,
        "initialization_status": record.initialization_status,
        "presence_state": record.presence_state,
        "last_heartbeat_at": record.last_heartbeat_at,
        "heartbeat_ttl_seconds": record.heartbeat_ttl_seconds,
        "accepting_new_work": record.accepting_new_work,
        "capacity_revision": capacity.capacity_revision if capacity else None,
        "capacity_observed_at": capacity.observed_at if capacity else None,
        "active_assignment_count": capacity.active_assignment_count if capacity else None,
        "max_concurrent_assignments": capacity.max_concurrent_assignments if capacity else None,
        "load_state": capacity.load_state if capacity else None,
        "claim_id": claim.claim_id if claim else None,
        "claim_state": claim.state if claim else None,
        "stale_or_offline_reason": _stale_or_offline_reason(record),
        "evidence_refs": list(evidence_refs or []),
        "read_only": True,
        "not_business_completion": True,
    }
    return _redact_value({key: value for key, value in payload.items() if key in CANDIDATE_RUNTIME_PROJECTION_FIELDS})


def _stale_or_offline_reason(record: AgentRegistryRecord) -> Optional[str]:
    if record.presence_state in {"stale", "offline", "draining"}:
        return record.presence_state
    if record.registry_status in {"suspended", "revoked", "quarantined"}:
        return record.registry_status
    if record.initialization_status != "ready":
        return record.initialization_status
    return None


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _is_secret_key(str(key)):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact_value(item)
        return redacted
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, str) and _looks_secret(value):
        return "[REDACTED]"
    return value


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    if lowered.endswith("_ref") or lowered.endswith("_refs"):
        return False
    return any(marker in lowered for marker in ("authorization", "credential", "password", "private_key", "secret", "token"))


def _looks_secret(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith("sk-") or any(
        marker in lowered for marker in ("authorization:", "bearer ", "password=", "secret=", "token=")
    )
