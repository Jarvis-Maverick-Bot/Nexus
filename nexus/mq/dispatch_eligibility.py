"""Pure dispatch eligibility evaluator for WBS 7.10.

This module only reads registry/heartbeat state and builds inert candidates. It
does not publish to MQ, invoke runtimes, persist assignments, or mutate business
state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from nexus.mq.agent_registry import AgentRegistryRecord
from nexus.mq.agent_registry_service import AgentRegistryService
from nexus.mq.agent_registry_store import AgentRegistryLoadResult, StoredAgentRegistryRecord
from nexus.mq.dispatch_assignment import DispatchAssignmentCandidate, build_assignment_candidate, validate_assignment_candidate
from nexus.mq.dispatch_request import BUSINESS_ASSIGNMENT_KIND, DispatchRequest, validate_dispatch_request


class DispatchRejectionCode:
    DISPATCH_DISABLED = "DISPATCH_DISABLED"
    BUSINESS_DISPATCH_NOT_AUTHORIZED = "BUSINESS_DISPATCH_NOT_AUTHORIZED"
    REGISTRY_UNAVAILABLE = "REGISTRY_UNAVAILABLE"
    REGISTRY_UNVERIFIED = "REGISTRY_UNVERIFIED"
    REGISTRY_MALFORMED = "REGISTRY_MALFORMED"
    REGISTRY_STALE = "REGISTRY_STALE"
    AGENT_RECORD_MISSING = "AGENT_RECORD_MISSING"
    REGISTRY_NOT_ACTIVE = "REGISTRY_NOT_ACTIVE"
    REGISTRY_SUSPENDED = "REGISTRY_SUSPENDED"
    REGISTRY_REVOKED = "REGISTRY_REVOKED"
    REGISTRY_QUARANTINED = "REGISTRY_QUARANTINED"
    RUNTIME_INSTANCE_MISMATCH = "RUNTIME_INSTANCE_MISMATCH"
    INITIALIZATION_NOT_READY = "INITIALIZATION_NOT_READY"
    READINESS_EVIDENCE_MISSING = "READINESS_EVIDENCE_MISSING"
    READINESS_BLOCKED = "READINESS_BLOCKED"
    STARTUP_PACKET_MISSING = "STARTUP_PACKET_MISSING"
    STARTUP_PACKET_INVALID = "STARTUP_PACKET_INVALID"
    STARTUP_PACKET_EXPIRED = "STARTUP_PACKET_EXPIRED"
    HEARTBEAT_MISSING = "HEARTBEAT_MISSING"
    HEARTBEAT_INVALID = "HEARTBEAT_INVALID"
    HEARTBEAT_STALE = "HEARTBEAT_STALE"
    PRESENCE_ONLINE_ONLY = "PRESENCE_ONLINE_ONLY"
    PRESENCE_BUSY = "PRESENCE_BUSY"
    PRESENCE_DEGRADED = "PRESENCE_DEGRADED"
    PRESENCE_DRAINING = "PRESENCE_DRAINING"
    PRESENCE_OFFLINE = "PRESENCE_OFFLINE"
    PRESENCE_STALE = "PRESENCE_STALE"
    PRESENCE_NOT_DISPATCHABLE = "PRESENCE_NOT_DISPATCHABLE"
    NOT_ACCEPTING_NEW_WORK = "NOT_ACCEPTING_NEW_WORK"
    LOAD_LIMIT_EXCEEDED = "LOAD_LIMIT_EXCEEDED"
    CAPABILITY_MISMATCH = "CAPABILITY_MISMATCH"
    AUTHORITY_SCOPE_MISMATCH = "AUTHORITY_SCOPE_MISMATCH"
    PRIVACY_SCOPE_MISMATCH = "PRIVACY_SCOPE_MISMATCH"
    TASK_BOUNDARY_MISMATCH = "TASK_BOUNDARY_MISMATCH"
    BLOCKING_ANOMALY_PRESENT = "BLOCKING_ANOMALY_PRESENT"
    NO_ELIGIBLE_AGENT = "NO_ELIGIBLE_AGENT"


@dataclass
class DispatchPolicy:
    dispatch_enabled: bool = False
    allowed_assignment_kinds: set[str] = field(default_factory=lambda: {"non_business_probe"})
    business_dispatch_enabled: bool = False
    max_load_score: float = 1.0


@dataclass
class DispatchEligibilityDecision:
    accepted: bool
    candidate: Optional[DispatchAssignmentCandidate] = None
    eligible_agent_ids: list[str] = field(default_factory=list)
    rejected: dict[str, list[str]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_dispatch_from_registry_service(
    request: DispatchRequest,
    registry_service: AgentRegistryService,
    *,
    policy: DispatchPolicy,
    now_at: str,
    blocking_anomalies: Optional[dict[str, list[str]]] = None,
) -> DispatchEligibilityDecision:
    preflight_errors = _pre_registry_errors(request, policy=policy, now_at=now_at)
    if preflight_errors:
        return _blocked(preflight_errors)
    registry = registry_service.load_registry_records(now_at=now_at)
    return evaluate_dispatch_eligibility(
        request,
        registry,
        policy=policy,
        now_at=now_at,
        blocking_anomalies=blocking_anomalies,
    )


def evaluate_dispatch_eligibility(
    request: DispatchRequest,
    registry: AgentRegistryLoadResult,
    *,
    policy: DispatchPolicy,
    now_at: str,
    blocking_anomalies: Optional[dict[str, list[str]]] = None,
) -> DispatchEligibilityDecision:
    preflight_errors = _pre_registry_errors(request, policy=policy, now_at=now_at)
    if preflight_errors:
        return _blocked(preflight_errors)

    registry_errors = _registry_load_errors(registry)
    if registry_errors:
        return _blocked(registry_errors)

    rejected = _rejected_rows(registry)
    eligible: list[StoredAgentRegistryRecord] = []
    for stored in registry.records:
        record = stored.record
        if request.target_agent_id and record.agent_id != request.target_agent_id:
            continue
        reasons = dispatch_ineligibility_reasons(
            record,
            request=request,
            policy=policy,
            now_at=now_at,
            blocking_anomalies=blocking_anomalies,
        )
        if reasons:
            rejected[record.agent_id] = reasons
        else:
            eligible.append(stored)

    if request.target_agent_id and request.target_agent_id not in rejected and not any(
        item.record.agent_id == request.target_agent_id for item in eligible
    ):
        rejected[request.target_agent_id] = [DispatchRejectionCode.AGENT_RECORD_MISSING]

    if not eligible:
        return DispatchEligibilityDecision(
            accepted=False,
            rejected=rejected,
            errors=[DispatchRejectionCode.NO_ELIGIBLE_AGENT],
        )

    selected = sorted(
        eligible,
        key=lambda item: (item.record.load_score, len(item.record.current_assignment_refs), item.record.agent_id),
    )[0]
    candidate = build_assignment_candidate(
        request,
        selected.record,
        registry_revision_seen=selected.revision,
        now_at=now_at,
    )
    candidate_validation = validate_assignment_candidate(candidate)
    if not candidate_validation.valid:
        return DispatchEligibilityDecision(
            accepted=False,
            rejected=rejected,
            errors=candidate_validation.errors,
        )
    return DispatchEligibilityDecision(
        accepted=True,
        candidate=candidate,
        eligible_agent_ids=[item.record.agent_id for item in eligible],
        rejected=rejected,
    )


def dispatch_ineligibility_reasons(
    record: AgentRegistryRecord,
    *,
    request: DispatchRequest,
    policy: DispatchPolicy,
    now_at: str,
    blocking_anomalies: Optional[dict[str, list[str]]] = None,
) -> list[str]:
    reasons: list[str] = []
    if record.registry_status == "suspended":
        reasons.append(DispatchRejectionCode.REGISTRY_SUSPENDED)
    elif record.registry_status == "revoked":
        reasons.append(DispatchRejectionCode.REGISTRY_REVOKED)
    elif record.registry_status == "quarantined":
        reasons.append(DispatchRejectionCode.REGISTRY_QUARANTINED)
    elif record.registry_status != "active":
        reasons.append(DispatchRejectionCode.REGISTRY_NOT_ACTIVE)

    if record.initialization_status == "quarantined":
        reasons.append(DispatchRejectionCode.REGISTRY_QUARANTINED)
    elif record.initialization_status != "ready":
        reasons.append(DispatchRejectionCode.INITIALIZATION_NOT_READY)

    if request.target_runtime_instance_id and request.target_runtime_instance_id != record.runtime_instance_id:
        reasons.append(DispatchRejectionCode.RUNTIME_INSTANCE_MISMATCH)
    if not record.readiness_evidence_ref:
        reasons.append(DispatchRejectionCode.READINESS_EVIDENCE_MISSING)
    if record.readiness_blocker:
        reasons.append(DispatchRejectionCode.READINESS_BLOCKED)
    if not record.startup_packet_ref:
        reasons.append(DispatchRejectionCode.STARTUP_PACKET_MISSING)
    reasons.extend(_startup_packet_reasons(record, now_at=now_at))
    reasons.extend(_heartbeat_reasons(record, now_at=now_at))
    reasons.extend(_presence_reasons(record))
    if not record.accepting_new_work:
        reasons.append(DispatchRejectionCode.NOT_ACCEPTING_NEW_WORK)
    if record.load_score >= policy.max_load_score:
        reasons.append(DispatchRejectionCode.LOAD_LIMIT_EXCEEDED)
    if request.required_capability not in record.capabilities:
        reasons.append(DispatchRejectionCode.CAPABILITY_MISMATCH)
    if request.required_authority_scope not in record.authority_scopes:
        reasons.append(DispatchRejectionCode.AUTHORITY_SCOPE_MISMATCH)
    if request.required_privacy_scope not in record.privacy_scopes:
        reasons.append(DispatchRejectionCode.PRIVACY_SCOPE_MISMATCH)
    if request.allowed_task_boundary not in record.allowed_task_boundaries:
        reasons.append(DispatchRejectionCode.TASK_BOUNDARY_MISMATCH)
    if blocking_anomalies and blocking_anomalies.get(record.agent_id):
        reasons.append(DispatchRejectionCode.BLOCKING_ANOMALY_PRESENT)
    return _dedupe(reasons)


def _request_errors(request: DispatchRequest, *, policy: DispatchPolicy, now_at: str) -> list[str]:
    validation = validate_dispatch_request(request, now_at=now_at)
    errors = list(validation.errors)
    if request.assignment_kind not in policy.allowed_assignment_kinds:
        if request.assignment_kind == BUSINESS_ASSIGNMENT_KIND:
            errors.append(DispatchRejectionCode.BUSINESS_DISPATCH_NOT_AUTHORIZED)
        else:
            errors.append(f"ASSIGNMENT_KIND_NOT_ALLOWED: {request.assignment_kind}")
    if request.assignment_kind == BUSINESS_ASSIGNMENT_KIND and (
        not request.business_dispatch_authorized or not policy.business_dispatch_enabled
    ):
        errors.append(DispatchRejectionCode.BUSINESS_DISPATCH_NOT_AUTHORIZED)
    return _dedupe(errors)


def _pre_registry_errors(request: DispatchRequest, *, policy: DispatchPolicy, now_at: str) -> list[str]:
    if not policy.dispatch_enabled:
        return [DispatchRejectionCode.DISPATCH_DISABLED]
    return _request_errors(request, policy=policy, now_at=now_at)


def _registry_load_errors(registry: AgentRegistryLoadResult) -> list[str]:
    if registry.accepted:
        return []
    return _normalize_registry_errors(registry.store_errors or [DispatchRejectionCode.REGISTRY_UNAVAILABLE])


def _rejected_rows(registry: AgentRegistryLoadResult) -> dict[str, list[str]]:
    rejected: dict[str, list[str]] = {}
    for agent_id, errors in registry.rejected_agents.items():
        rejected[agent_id] = _normalize_registry_errors(errors)
    return rejected


def _normalize_registry_errors(errors: list[str]) -> list[str]:
    normalized: list[str] = []
    for error in errors:
        if error == "REGISTRY_TRUTH_UNVERIFIED":
            normalized.append(DispatchRejectionCode.REGISTRY_UNVERIFIED)
        elif error == "REGISTRY_RECORD_NOT_FOUND":
            normalized.append(DispatchRejectionCode.AGENT_RECORD_MISSING)
        elif error == "STARTUP_PACKET_EXPIRED":
            normalized.append(DispatchRejectionCode.STARTUP_PACKET_EXPIRED)
        elif error in {"MISSING_READINESS_EVIDENCE_REF", "MISSING_STARTUP_PACKET_REF"}:
            normalized.append(
                DispatchRejectionCode.READINESS_EVIDENCE_MISSING
                if error == "MISSING_READINESS_EVIDENCE_REF"
                else DispatchRejectionCode.STARTUP_PACKET_MISSING
            )
        elif error == "STALE_REVISION":
            normalized.append(DispatchRejectionCode.REGISTRY_STALE)
        elif error.startswith("MALFORMED_REGISTRY_ROW") or error.startswith("UNSUPPORTED_REGISTRY"):
            normalized.append(DispatchRejectionCode.REGISTRY_MALFORMED)
        elif error == "REGISTRY_STORE_CORRUPTED":
            normalized.append(DispatchRejectionCode.REGISTRY_MALFORMED)
        elif error == "STARTUP_PACKET_FRESHNESS_INVALID":
            normalized.append(DispatchRejectionCode.STARTUP_PACKET_INVALID)
        else:
            normalized.append(error)
    return _dedupe(normalized)


def _startup_packet_reasons(record: AgentRegistryRecord, *, now_at: str) -> list[str]:
    if not record.startup_packet_expires_at:
        return [DispatchRejectionCode.STARTUP_PACKET_INVALID]
    expires_dt = _parse_iso(record.startup_packet_expires_at)
    now_dt = _parse_iso(now_at)
    if expires_dt is None or now_dt is None:
        return [DispatchRejectionCode.STARTUP_PACKET_INVALID]
    if expires_dt <= now_dt:
        return [DispatchRejectionCode.STARTUP_PACKET_EXPIRED]
    return []


def _heartbeat_reasons(record: AgentRegistryRecord, *, now_at: str) -> list[str]:
    if not record.last_heartbeat_at:
        return [DispatchRejectionCode.HEARTBEAT_MISSING]
    heartbeat_dt = _parse_iso(record.last_heartbeat_at)
    now_dt = _parse_iso(now_at)
    if heartbeat_dt is None or now_dt is None:
        return [DispatchRejectionCode.HEARTBEAT_INVALID]
    if record.heartbeat_ttl_seconds <= 0:
        return [DispatchRejectionCode.HEARTBEAT_INVALID]
    if (now_dt - heartbeat_dt).total_seconds() > record.heartbeat_ttl_seconds:
        return [DispatchRejectionCode.HEARTBEAT_STALE]
    return []


def _presence_reasons(record: AgentRegistryRecord) -> list[str]:
    mapping = {
        "online": DispatchRejectionCode.PRESENCE_ONLINE_ONLY,
        "busy": DispatchRejectionCode.PRESENCE_BUSY,
        "degraded": DispatchRejectionCode.PRESENCE_DEGRADED,
        "draining": DispatchRejectionCode.PRESENCE_DRAINING,
        "offline": DispatchRejectionCode.PRESENCE_OFFLINE,
        "stale": DispatchRejectionCode.PRESENCE_STALE,
    }
    if record.presence_state == "idle":
        return []
    return [mapping.get(record.presence_state, DispatchRejectionCode.PRESENCE_NOT_DISPATCHABLE)]


def _blocked(errors: list[str]) -> DispatchEligibilityDecision:
    return DispatchEligibilityDecision(accepted=False, errors=_dedupe(errors))


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
