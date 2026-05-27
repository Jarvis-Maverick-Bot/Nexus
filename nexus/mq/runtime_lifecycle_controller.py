"""4.19 Runtime Lifecycle Controller for source-only real-agent tests.

The controller owns runtime supply state: registration, readiness, heartbeat
freshness, lifecycle controls, eligibility decisions, and reservation leases.
It does not publish assignments or own broker transport behavior.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any

from nexus.mq.eligibility_reservation_policy import RuntimeEligibilityDecision, RuntimeReservationLease
from nexus.mq.heartbeat_presence_controller import HeartbeatPresenceController, HeartbeatPresencePolicy


@dataclass
class RuntimeLifecyclePolicy:
    heartbeat_interval_seconds: int = 15
    heartbeat_ttl_seconds: int = 60
    lease_ttl_seconds: int = 60
    assignment_timeout_seconds: int = 30
    stale_to_offline_grace_seconds: int = 180
    max_concurrent_assignments: int = 1

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.heartbeat_interval_seconds <= 0:
            errors.append("INVALID_HEARTBEAT_INTERVAL")
        if self.heartbeat_ttl_seconds <= 0:
            errors.append("INVALID_HEARTBEAT_TTL")
        if self.heartbeat_ttl_seconds < self.heartbeat_interval_seconds:
            errors.append("HEARTBEAT_TTL_SHORTER_THAN_INTERVAL")
        if self.lease_ttl_seconds <= 0:
            errors.append("INVALID_LEASE_TTL")
        if self.assignment_timeout_seconds <= 0:
            errors.append("INVALID_ASSIGNMENT_TIMEOUT")
        if self.max_concurrent_assignments <= 0:
            errors.append("INVALID_MAX_CONCURRENT_ASSIGNMENTS")
        return errors


@dataclass
class RuntimeRegistrationRequest:
    agent_id: str
    runtime_instance_id: str
    owner_principal_id: str
    runtime_type: str
    role: str
    capabilities: list[str]
    authority_scopes: list[str]
    privacy_scopes: list[str]
    allowed_task_boundaries: list[str]
    no_go_scope: list[str]
    protocol_versions_supported: list[str]
    trust_material_ref: str
    profile_ref: str
    evidence_refs: list[str] = field(default_factory=list)
    not_business_completion: bool = True


@dataclass
class RuntimeEligibilityRequest:
    request_id: str
    dispatch_run_id: str
    assignment_id: str
    idempotency_key: str
    source_authority_ref: str
    target_agent_id: str
    target_runtime_instance_id: str
    required_capability: str
    required_authority_scope: str
    required_privacy_scope: str
    allowed_task_boundary: str
    no_go_scope: list[str]
    required_protocol_version: str
    policy_hash: str
    not_business_completion: bool = True


@dataclass
class RuntimeLifecycleRecord:
    agent_id: str
    runtime_instance_id: str
    owner_principal_id: str
    runtime_type: str
    role: str
    capabilities: list[str]
    authority_scopes: list[str]
    privacy_scopes: list[str]
    allowed_task_boundaries: list[str]
    no_go_scope: list[str]
    protocol_versions_supported: list[str]
    trust_material_ref: str
    profile_ref: str
    lifecycle_state: str
    registry_status: str
    presence_state: str
    startup_packet_ref: str = ""
    readiness_evidence_ref: str = ""
    startup_packet_expires_at: str = ""
    last_heartbeat_at: str = ""
    heartbeat_sequence: int = 0
    load_score: float = 0.0
    accepting_new_work: bool = True
    active_assignment_ids: list[str] = field(default_factory=list)
    active_decision_ids: list[str] = field(default_factory=list)
    active_reservation_lease_ids: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RuntimeLifecycleControlResult:
    accepted: bool
    runtime_instance_id: str
    lifecycle_state: str
    errors: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    not_business_completion: bool = True


class RuntimeLifecycleController:
    def __init__(self, *, policy: RuntimeLifecyclePolicy | None = None) -> None:
        self.policy = policy or RuntimeLifecyclePolicy()
        errors = self.policy.validate()
        if errors:
            raise ValueError("; ".join(errors))
        self._records: dict[str, RuntimeLifecycleRecord] = {}
        self._presence = HeartbeatPresenceController(
            policy=HeartbeatPresencePolicy(
                heartbeat_interval_seconds=self.policy.heartbeat_interval_seconds,
                heartbeat_ttl_seconds=self.policy.heartbeat_ttl_seconds,
                stale_to_offline_grace_seconds=self.policy.stale_to_offline_grace_seconds,
            )
        )

    def register_runtime(self, request: RuntimeRegistrationRequest, *, now_at: str) -> RuntimeLifecycleRecord:
        errors = _registration_errors(request)
        if errors:
            raise ValueError("; ".join(errors))
        record = RuntimeLifecycleRecord(
            agent_id=request.agent_id,
            runtime_instance_id=request.runtime_instance_id,
            owner_principal_id=request.owner_principal_id,
            runtime_type=request.runtime_type,
            role=request.role,
            capabilities=list(request.capabilities),
            authority_scopes=list(request.authority_scopes),
            privacy_scopes=list(request.privacy_scopes),
            allowed_task_boundaries=list(request.allowed_task_boundaries),
            no_go_scope=list(request.no_go_scope),
            protocol_versions_supported=list(request.protocol_versions_supported),
            trust_material_ref=request.trust_material_ref,
            profile_ref=request.profile_ref,
            lifecycle_state="registered",
            registry_status="active",
            presence_state="offline",
            evidence_refs=list(request.evidence_refs),
            created_at=now_at,
            updated_at=now_at,
        )
        self._records[request.runtime_instance_id] = record
        return record

    def submit_readiness(
        self,
        *,
        runtime_instance_id: str,
        startup_packet_ref: str,
        readiness_evidence_ref: str,
        startup_packet_expires_at: str,
        now_at: str,
    ) -> RuntimeLifecycleRecord:
        record = self.get_runtime(runtime_instance_id)
        errors: list[str] = []
        if not startup_packet_ref:
            errors.append("MISSING_STARTUP_PACKET_REF")
        if not readiness_evidence_ref:
            errors.append("MISSING_READINESS_EVIDENCE_REF")
        if not startup_packet_expires_at:
            errors.append("MISSING_STARTUP_PACKET_FRESHNESS")
        if errors:
            record.lifecycle_state = "quarantined"
            record.updated_at = now_at
            raise ValueError("; ".join(errors))
        record.startup_packet_ref = startup_packet_ref
        record.readiness_evidence_ref = readiness_evidence_ref
        record.startup_packet_expires_at = startup_packet_expires_at
        record.lifecycle_state = "ready"
        record.updated_at = now_at
        return record

    def record_heartbeat(
        self,
        *,
        runtime_instance_id: str,
        sequence: int,
        observed_at: str,
        load_score: float = 0.0,
        accepting_new_work: bool = True,
    ) -> RuntimeLifecycleRecord:
        record = self.get_runtime(runtime_instance_id)
        result = self._presence.record_heartbeat(
            runtime_instance_id=runtime_instance_id,
            sequence=sequence,
            observed_at=observed_at,
            load_score=load_score,
            accepting_new_work=accepting_new_work,
        )
        if not result.accepted:
            raise ValueError("; ".join(result.errors))
        record.last_heartbeat_at = observed_at
        record.heartbeat_sequence = sequence
        record.load_score = load_score
        record.accepting_new_work = accepting_new_work
        record.presence_state = result.presence_state
        if record.lifecycle_state == "ready":
            record.lifecycle_state = "idle"
        record.updated_at = observed_at
        return record

    def apply_lifecycle_control(
        self,
        *,
        runtime_instance_id: str,
        action: str,
        reason_ref: str,
        now_at: str,
    ) -> RuntimeLifecycleControlResult:
        record = self.get_runtime(runtime_instance_id)
        normalized = action.lower().replace("-", "_")
        target_state = {
            "pause": "paused",
            "resume": "idle",
            "suspend": "suspended",
            "drain": "draining",
            "offline": "offline",
            "revoke": "revoked",
            "quarantine": "quarantined",
        }.get(normalized)
        if target_state is None:
            return RuntimeLifecycleControlResult(
                accepted=False,
                runtime_instance_id=runtime_instance_id,
                lifecycle_state=record.lifecycle_state,
                errors=[f"UNKNOWN_LIFECYCLE_CONTROL: {action}"],
            )
        record.lifecycle_state = target_state
        if target_state in {"offline", "revoked", "quarantined", "draining", "paused", "suspended"}:
            record.accepting_new_work = False
        record.updated_at = now_at
        if reason_ref:
            record.evidence_refs.append(reason_ref)
        return RuntimeLifecycleControlResult(
            accepted=True,
            runtime_instance_id=runtime_instance_id,
            lifecycle_state=target_state,
            evidence_refs=[reason_ref] if reason_ref else [],
        )

    def evaluate_eligibility(
        self,
        request: RuntimeEligibilityRequest,
        *,
        now_at: str,
    ) -> RuntimeEligibilityDecision:
        record = self._records.get(request.target_runtime_instance_id)
        errors: list[str] = _eligibility_request_errors(request)
        if record is None:
            errors.append("RUNTIME_NOT_REGISTERED")
            return _decision(request, errors=errors)

        if record.agent_id != request.target_agent_id:
            errors.append("TARGET_AGENT_ID_MISMATCH")
        errors.extend(_readiness_errors(record, now_at=now_at))
        presence = self._presence.evaluate_presence(runtime_instance_id=record.runtime_instance_id, now_at=now_at)
        if not presence.dispatch_fresh:
            errors.extend(presence.errors or ["HEARTBEAT_NOT_FRESH"])
        record.presence_state = presence.presence_state
        if record.lifecycle_state != "idle":
            errors.append(f"LIFECYCLE_STATE_BLOCKS_ASSIGNMENT: {record.lifecycle_state}")
        if not record.accepting_new_work:
            errors.append("RUNTIME_NOT_ACCEPTING_NEW_WORK")
        if record.load_score >= 1.0:
            errors.append("RUNTIME_LOAD_LIMIT_EXCEEDED")
        if len(record.active_assignment_ids) >= self.policy.max_concurrent_assignments:
            errors.append("RUNTIME_CAPACITY_EXHAUSTED")
        if request.required_capability not in record.capabilities:
            errors.append("CAPABILITY_MISMATCH")
        if request.required_authority_scope not in record.authority_scopes:
            errors.append("AUTHORITY_SCOPE_MISMATCH")
        if request.required_privacy_scope not in record.privacy_scopes:
            errors.append("PRIVACY_SCOPE_MISMATCH")
        if request.allowed_task_boundary not in record.allowed_task_boundaries:
            errors.append("TASK_BOUNDARY_MISMATCH")
        if not set(record.no_go_scope).issubset(set(request.no_go_scope)):
            errors.append("NO_GO_SCOPE_MISMATCH")
        if request.required_protocol_version not in record.protocol_versions_supported:
            errors.append("PROTOCOL_VERSION_MISMATCH")
        return _decision(request, record=record, errors=errors)

    def reserve_runtime(
        self,
        decision: RuntimeEligibilityDecision,
        *,
        assignment_id: str,
        now_at: str,
    ) -> RuntimeReservationLease:
        if not decision.accepted:
            raise ValueError("ELIGIBILITY_DECISION_NOT_ALLOWED")
        if decision.assignment_id != assignment_id:
            raise ValueError("DECISION_ASSIGNMENT_ID_MISMATCH")
        record = self.get_runtime(decision.target_runtime_instance_id)
        lease_id = _stable_id("lease", decision.decision_id, assignment_id, now_at)
        expires_at = (_parse_iso(now_at) + timedelta(seconds=self.policy.lease_ttl_seconds)).isoformat()
        lease = RuntimeReservationLease(
            lease_id=lease_id,
            lifecycle_decision_id=decision.decision_id,
            assignment_id=assignment_id,
            dispatch_run_id=decision.dispatch_run_id,
            target_runtime_instance_id=decision.target_runtime_instance_id,
            active=True,
            status="active",
            expires_at=expires_at,
            policy_hash=decision.policy_hash,
            idempotency_key=decision.idempotency_key,
        )
        record.lifecycle_state = "reserved"
        _append_unique(record.active_decision_ids, decision.decision_id)
        _append_unique(record.active_reservation_lease_ids, lease_id)
        record.updated_at = now_at
        return lease

    def get_runtime(self, runtime_instance_id: str) -> RuntimeLifecycleRecord:
        record = self._records.get(runtime_instance_id)
        if record is None:
            raise KeyError(f"runtime not found: {runtime_instance_id}")
        return record


def _registration_errors(request: RuntimeRegistrationRequest) -> list[str]:
    errors: list[str] = []
    for field_name in (
        "agent_id",
        "runtime_instance_id",
        "owner_principal_id",
        "runtime_type",
        "role",
        "capabilities",
        "authority_scopes",
        "privacy_scopes",
        "allowed_task_boundaries",
        "no_go_scope",
        "protocol_versions_supported",
        "trust_material_ref",
        "profile_ref",
    ):
        if not getattr(request, field_name):
            errors.append(f"MISSING_RUNTIME_REGISTRATION_FIELD: {field_name}")
    if request.not_business_completion is not True:
        errors.append("RUNTIME_REGISTRATION_CANNOT_BE_BUSINESS_COMPLETION")
    return _dedupe(errors)


def _eligibility_request_errors(request: RuntimeEligibilityRequest) -> list[str]:
    errors: list[str] = []
    for field_name in (
        "request_id",
        "dispatch_run_id",
        "assignment_id",
        "idempotency_key",
        "source_authority_ref",
        "target_agent_id",
        "target_runtime_instance_id",
        "required_capability",
        "required_authority_scope",
        "required_privacy_scope",
        "allowed_task_boundary",
        "no_go_scope",
        "required_protocol_version",
        "policy_hash",
    ):
        if not getattr(request, field_name):
            errors.append(f"MISSING_ELIGIBILITY_REQUEST_FIELD: {field_name}")
    if request.not_business_completion is not True:
        errors.append("ELIGIBILITY_REQUEST_CANNOT_BE_BUSINESS_COMPLETION")
    return _dedupe(errors)


def _readiness_errors(record: RuntimeLifecycleRecord, *, now_at: str) -> list[str]:
    errors: list[str] = []
    if not record.startup_packet_ref or not record.readiness_evidence_ref:
        errors.append("RUNTIME_NOT_READY")
        errors.append("READINESS_EVIDENCE_MISSING")
    if not record.startup_packet_expires_at:
        errors.append("STARTUP_PACKET_FRESHNESS_UNDECLARED")
    else:
        expires = _parse_iso(record.startup_packet_expires_at)
        now = _parse_iso(now_at)
        if expires is None or now is None:
            errors.append("STARTUP_PACKET_FRESHNESS_INVALID")
        elif expires <= now:
            errors.append("STARTUP_PACKET_EXPIRED")
    return _dedupe(errors)


def _decision(
    request: RuntimeEligibilityRequest,
    *,
    record: RuntimeLifecycleRecord | None = None,
    errors: list[str],
) -> RuntimeEligibilityDecision:
    accepted = not errors
    decision_id = _stable_id(
        "decision",
        request.request_id,
        request.dispatch_run_id,
        request.assignment_id,
        request.idempotency_key,
    )
    target_agent_id = record.agent_id if record is not None else request.target_agent_id
    target_runtime_instance_id = record.runtime_instance_id if record is not None else request.target_runtime_instance_id
    return RuntimeEligibilityDecision(
        decision_id=decision_id,
        request_id=request.request_id,
        dispatch_run_id=request.dispatch_run_id,
        assignment_id=request.assignment_id,
        target_agent_id=target_agent_id,
        target_runtime_instance_id=target_runtime_instance_id,
        accepted=accepted,
        policy_hash=request.policy_hash,
        idempotency_key=request.idempotency_key,
        evidence_refs=[f"evidence://runtime-lifecycle/decision/{decision_id}"],
        errors=_dedupe(errors),
    )


def _stable_id(prefix: str, *parts: str) -> str:
    digest = sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


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


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error and error not in deduped:
            deduped.append(error)
    return deduped
