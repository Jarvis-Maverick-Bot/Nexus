"""4.19 agent registry, readiness, heartbeat, and dispatch eligibility."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import uuid


REGISTRY_STATUSES = {"proposed", "active", "suspended", "revoked", "quarantined"}
INITIALIZATION_STATUSES = {"not_started", "initializing", "ready", "failed", "quarantined", "superseded"}
PRESENCE_STATES = {"online", "idle", "busy", "degraded", "draining", "offline", "stale"}
DISPATCH_STATES = {
    "queued",
    "assigned",
    "intake_acknowledged",
    "running",
    "stalled",
    "reallocated",
    "completed_candidate",
    "rejected",
    "dlq",
    "cancelled",
}


@dataclass
class AgentRegistryRecord:
    agent_id: str
    runtime_instance_id: str
    role: str
    owner_principal_id: str
    runtime_type: str
    channel_bindings: list[str]
    capabilities: list[str]
    authority_scopes: list[str]
    allowed_task_boundaries: list[str]
    initialization_status: str
    registry_status: str
    presence_state: str
    heartbeat_ttl_seconds: int
    last_heartbeat_at: Optional[str]
    current_assignment_refs: list[str]
    protocol_versions_supported: list[str]
    trust_material_ref: str
    startup_packet_ref: Optional[str]
    readiness_evidence_ref: Optional[str]
    startup_packet_expires_at: Optional[str]
    created_at: str
    updated_at: str
    privacy_scopes: list[str] = field(default_factory=lambda: ["project"])
    load_score: float = 0.0
    accepting_new_work: bool = True
    readiness_blocker: Optional[str] = None
    not_business_completion: bool = True
    candidate_profile_ref: Optional[str] = None
    runtime_provider: Optional[str] = None
    runtime_version: Optional[str] = None
    host_ref: Optional[str] = None
    source_repo_refs: list[str] = field(default_factory=list)
    credential_ref: Optional[str] = None
    legacy_runtime_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DispatchAssignmentRecord:
    assignment_id: str
    work_ref: str
    message_envelope_ref: str
    required_capability: str
    required_authority_scope: str
    required_privacy_scope: str
    allowed_task_boundary: str
    assigned_agent_id: Optional[str]
    assigned_runtime_instance_id: Optional[str]
    dispatch_state: str
    accepted_at: Optional[str]
    timeout_at: Optional[str]
    reallocation_count: int
    evidence_refs: list[str]
    last_error_ref: Optional[str] = None
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DispatchDecision:
    accepted: bool
    assignment: Optional[DispatchAssignmentRecord]
    eligible_agent_ids: list[str] = field(default_factory=list)
    rejected: dict[str, list[str]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class AgentRegistry:
    def __init__(self, records: Optional[list[AgentRegistryRecord]] = None):
        self._records: dict[str, AgentRegistryRecord] = {}
        for record in records or []:
            self.upsert(record)

    def upsert(self, record: AgentRegistryRecord) -> AgentRegistryRecord:
        errors = validate_agent_registry_record(record)
        if errors:
            raise ValueError("; ".join(errors))
        self._records[record.agent_id] = record
        return record

    def get(self, agent_id: str) -> Optional[AgentRegistryRecord]:
        return self._records.get(agent_id)

    def all_records(self) -> list[AgentRegistryRecord]:
        return list(self._records.values())

    def record_heartbeat(
        self,
        *,
        agent_id: str,
        runtime_instance_id: str,
        heartbeat_at: str,
        presence_state: str = "idle",
        load_score: float = 0.0,
        accepting_new_work: bool = True,
    ) -> AgentRegistryRecord:
        record = self._require(agent_id)
        if record.runtime_instance_id != runtime_instance_id:
            raise ValueError("RUNTIME_INSTANCE_MISMATCH")
        if presence_state not in PRESENCE_STATES:
            raise ValueError(f"INVALID_PRESENCE_STATE: {presence_state}")
        record.last_heartbeat_at = heartbeat_at
        record.presence_state = presence_state
        record.load_score = load_score
        record.accepting_new_work = accepting_new_work
        record.updated_at = heartbeat_at
        return record

    def evaluate_presence(self, *, now_at: str) -> list[AgentRegistryRecord]:
        now_dt = _parse_iso(now_at)
        updated: list[AgentRegistryRecord] = []
        for record in self._records.values():
            heartbeat_dt = _parse_iso(record.last_heartbeat_at)
            stale = heartbeat_dt is None or (now_dt - heartbeat_dt).total_seconds() > record.heartbeat_ttl_seconds
            if stale and record.presence_state not in {"offline", "stale"}:
                record.presence_state = "stale"
                record.accepting_new_work = False
                record.updated_at = now_at
                updated.append(record)
        return updated

    def assign_work(
        self,
        *,
        work_ref: str,
        message_envelope_ref: str,
        required_capability: str,
        required_authority_scope: str,
        required_privacy_scope: str,
        allowed_task_boundary: str,
        now_at: str,
        timeout_at: Optional[str] = None,
        evidence_refs: Optional[list[str]] = None,
        exclude_agent_ids: Optional[set[str]] = None,
    ) -> DispatchDecision:
        self.evaluate_presence(now_at=now_at)
        rejected: dict[str, list[str]] = {}
        eligible: list[AgentRegistryRecord] = []
        for record in self._records.values():
            if exclude_agent_ids and record.agent_id in exclude_agent_ids:
                rejected[record.agent_id] = ["EXCLUDED_PREVIOUS_ASSIGNMENT"]
                continue
            reasons = dispatch_ineligibility_reasons(
                record,
                required_capability=required_capability,
                required_authority_scope=required_authority_scope,
                required_privacy_scope=required_privacy_scope,
                allowed_task_boundary=allowed_task_boundary,
                now_at=now_at,
            )
            if reasons:
                rejected[record.agent_id] = reasons
            else:
                eligible.append(record)
        if not eligible:
            return DispatchDecision(
                accepted=False,
                assignment=None,
                rejected=rejected,
                errors=["NO_ELIGIBLE_AGENT"],
            )
        selected = sorted(eligible, key=lambda item: (item.load_score, len(item.current_assignment_refs), item.agent_id))[0]
        assignment_id = f"assign-{uuid.uuid4().hex[:12]}"
        selected.current_assignment_refs.append(assignment_id)
        selected.presence_state = "busy"
        selected.updated_at = now_at
        assignment = DispatchAssignmentRecord(
            assignment_id=assignment_id,
            work_ref=work_ref,
            message_envelope_ref=message_envelope_ref,
            required_capability=required_capability,
            required_authority_scope=required_authority_scope,
            required_privacy_scope=required_privacy_scope,
            allowed_task_boundary=allowed_task_boundary,
            assigned_agent_id=selected.agent_id,
            assigned_runtime_instance_id=selected.runtime_instance_id,
            dispatch_state="assigned",
            accepted_at=now_at,
            timeout_at=timeout_at,
            reallocation_count=0,
            evidence_refs=list(evidence_refs or []),
        )
        return DispatchDecision(
            accepted=True,
            assignment=assignment,
            eligible_agent_ids=[record.agent_id for record in eligible],
            rejected=rejected,
        )

    def _require(self, agent_id: str) -> AgentRegistryRecord:
        record = self.get(agent_id)
        if record is None:
            raise KeyError(f"agent not found: {agent_id}")
        return record


def validate_agent_registry_record(record: AgentRegistryRecord) -> list[str]:
    errors: list[str] = []
    if record.registry_status not in REGISTRY_STATUSES:
        errors.append(f"INVALID_REGISTRY_STATUS: {record.registry_status}")
    if record.initialization_status not in INITIALIZATION_STATUSES:
        errors.append(f"INVALID_INITIALIZATION_STATUS: {record.initialization_status}")
    if record.presence_state not in PRESENCE_STATES:
        errors.append(f"INVALID_PRESENCE_STATE: {record.presence_state}")
    if record.initialization_status == "ready" and not record.startup_packet_ref:
        errors.append("MISSING_STARTUP_PACKET_REF")
    if record.initialization_status == "ready" and not record.readiness_evidence_ref:
        errors.append("MISSING_READINESS_EVIDENCE_REF")
    if record.initialization_status == "ready" and not record.startup_packet_expires_at:
        errors.append("MISSING_STARTUP_PACKET_FRESHNESS")
    if record.heartbeat_ttl_seconds <= 0:
        errors.append("INVALID_HEARTBEAT_TTL")
    return errors


def dispatch_ineligibility_reasons(
    record: AgentRegistryRecord,
    *,
    required_capability: str,
    required_authority_scope: str,
    required_privacy_scope: str,
    allowed_task_boundary: str,
    now_at: Optional[str] = None,
) -> list[str]:
    reasons: list[str] = []
    if record.registry_status != "active":
        reasons.append(f"REGISTRY_NOT_ACTIVE: {record.registry_status}")
    if record.initialization_status != "ready":
        reasons.append(f"INITIALIZATION_NOT_READY: {record.initialization_status}")
    if not record.startup_packet_ref or not record.readiness_evidence_ref:
        reasons.append("READINESS_EVIDENCE_MISSING")
    if not record.startup_packet_expires_at:
        reasons.append("STARTUP_PACKET_FRESHNESS_UNDECLARED")
    elif now_at:
        expires_dt = _parse_iso(record.startup_packet_expires_at)
        now_dt = _parse_iso(now_at)
        if expires_dt is None or now_dt is None:
            reasons.append("STARTUP_PACKET_FRESHNESS_INVALID")
        elif expires_dt <= now_dt:
            reasons.append("STARTUP_PACKET_EXPIRED")
    if record.readiness_blocker:
        reasons.append(f"READINESS_BLOCKED: {record.readiness_blocker}")
    if record.presence_state != "idle":
        reasons.append(f"PRESENCE_NOT_IDLE: {record.presence_state}")
    if not record.accepting_new_work:
        reasons.append("NOT_ACCEPTING_NEW_WORK")
    if required_capability not in record.capabilities:
        reasons.append(f"CAPABILITY_MISMATCH: {required_capability}")
    if required_authority_scope not in record.authority_scopes:
        reasons.append(f"AUTHORITY_SCOPE_MISMATCH: {required_authority_scope}")
    if required_privacy_scope not in record.privacy_scopes:
        reasons.append(f"PRIVACY_SCOPE_MISMATCH: {required_privacy_scope}")
    if allowed_task_boundary not in record.allowed_task_boundaries:
        reasons.append(f"TASK_BOUNDARY_MISMATCH: {allowed_task_boundary}")
    if record.load_score >= 1.0:
        reasons.append("LOAD_LIMIT_EXCEEDED")
    return reasons


def reallocate_or_dlq_assignment(
    assignment: DispatchAssignmentRecord,
    registry: AgentRegistry,
    *,
    now_at: str,
    reason: str,
    max_reallocations: int = 1,
) -> DispatchAssignmentRecord:
    if assignment.reallocation_count >= max_reallocations:
        assignment.dispatch_state = "dlq"
        assignment.last_error_ref = reason
        assignment.evidence_refs.append(f"dlq://4.19/{assignment.assignment_id}")
        return assignment
    decision = registry.assign_work(
        work_ref=assignment.work_ref,
        message_envelope_ref=assignment.message_envelope_ref,
        required_capability=assignment.required_capability,
        required_authority_scope=assignment.required_authority_scope,
        required_privacy_scope=assignment.required_privacy_scope,
        allowed_task_boundary=assignment.allowed_task_boundary,
        now_at=now_at,
        timeout_at=assignment.timeout_at,
        evidence_refs=[*assignment.evidence_refs, f"reallocation://4.19/{assignment.assignment_id}"],
        exclude_agent_ids={assignment.assigned_agent_id} if assignment.assigned_agent_id else None,
    )
    if decision.assignment is None:
        assignment.dispatch_state = "dlq"
        assignment.last_error_ref = reason
        assignment.evidence_refs.append(f"dlq://4.19/{assignment.assignment_id}")
        return assignment
    decision.assignment.dispatch_state = "reallocated"
    decision.assignment.reallocation_count = assignment.reallocation_count + 1
    decision.assignment.last_error_ref = reason
    return decision.assignment


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
