"""Track 2 / 4.19 controller bridge data contracts.

These models are source-only coordination records. They do not start runtimes,
publish to MQ, or claim final readiness.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any


@dataclass
class ControllerBridgePolicy:
    heartbeat_interval_seconds: int = 15
    heartbeat_ttl_seconds: int = 60
    decision_validity_seconds: int = 30
    lease_ttl_seconds: int = 60
    release_deadline_seconds: int = 15
    assignment_ttl_seconds: int = 30
    result_timeout_seconds: int = 120
    allowed_work_classes: set[str] = field(default_factory=lambda: {"non_business_probe"})
    not_business_completion: bool = True


@dataclass
class Layer1ApprovedDecision:
    decision_id: str
    decision_authority_ref: str
    owner_principal_id: str
    work_class: str
    source_refs: dict[str, Any]
    dispatch_packet_ref: str
    target_agent_id: str
    target_runtime_instance_id: str
    target_runtime_role: str
    allowed_runtime_roles: list[str]
    required_capability: str
    required_authority_scope: str
    required_privacy_scope: str
    allowed_task_boundary: str
    required_protocol_version: str
    no_go_scope: list[str]
    evidence_required: list[str]
    idempotency_key: str
    expires_at: str
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DispatchRun:
    dispatch_run_id: str
    decision_id: str
    dispatch_packet_ref: str
    source_hash: str
    owner_principal_id: str
    target_agent_id: str
    target_runtime_instance_id: str
    target_runtime_role: str
    assignment_id: str
    assignment_ttl_seconds: int
    idempotency_key: str
    evidence_required: list[str]
    status: str
    created_at: str
    required_capability: str = ""
    required_authority_scope: str = ""
    required_privacy_scope: str = ""
    allowed_task_boundary: str = ""
    required_protocol_version: str = ""
    no_go_scope: list[str] = field(default_factory=list)
    source_authority_ref: str = ""
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DispatchEligibilityRequest:
    request_id: str
    dispatch_run_id: str
    decision_id: str
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
    assignment_ttl_seconds: int
    evidence_required: list[str]
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AssignmentPublishRequest:
    assignment_id: str
    dispatch_run_id: str
    dispatch_packet_ref: str
    decision_id: str
    lifecycle_decision_id: str
    reservation_lease_id: str
    runtime_instance_id: str
    idempotency_key: str
    subject: str
    assignment_ttl_seconds: int
    evidence_required: list[str]
    requested_at: str
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RuntimeResultCandidate:
    dispatch_run_id: str
    assignment_id: str
    runtime_instance_id: str
    decision_id: str
    lease_id: str
    result_ref: str
    evidence_refs: list[str]
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ControllerBridgeOperationResult:
    accepted: bool
    operation: str
    errors: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    duplicate_suppressed: bool = False
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "operation": self.operation,
            "errors": list(self.errors),
            "payload": _json_safe(self.payload),
            "duplicate_suppressed": self.duplicate_suppressed,
            "not_business_completion": self.not_business_completion,
        }


def validate_layer1_decision(
    decision: Layer1ApprovedDecision,
    *,
    now_at: str,
    policy: ControllerBridgePolicy,
) -> list[str]:
    errors: list[str] = []
    required = {
        "MISSING_DECISION_ID": decision.decision_id,
        "MISSING_SOURCE_AUTHORITY": decision.decision_authority_ref,
        "MISSING_OWNER_PRINCIPAL_ID": decision.owner_principal_id,
        "MISSING_WORK_CLASS": decision.work_class,
        "MISSING_DISPATCH_PACKET_REF": decision.dispatch_packet_ref,
        "MISSING_TARGET_AGENT_ID": decision.target_agent_id,
        "MISSING_TARGET_RUNTIME_INSTANCE_ID": decision.target_runtime_instance_id,
        "MISSING_TARGET_RUNTIME_ROLE": decision.target_runtime_role,
        "MISSING_IDEMPOTENCY_KEY": decision.idempotency_key,
        "MISSING_DECISION_EXPIRY": decision.expires_at,
    }
    for error, value in required.items():
        if not value:
            errors.append(error)
    if not decision.source_refs:
        errors.append("MISSING_SOURCE_REFS")
    if not decision.allowed_runtime_roles:
        errors.append("MISSING_ALLOWED_RUNTIME_ROLES")
    if decision.target_runtime_role and decision.target_runtime_role not in decision.allowed_runtime_roles:
        errors.append("TARGET_RUNTIME_ROLE_NOT_ALLOWED")
    if not decision.no_go_scope:
        errors.append("MISSING_NO_GO_SCOPE")
    if not decision.evidence_required:
        errors.append("MISSING_EVIDENCE_REQUIREMENTS")
    if decision.work_class not in policy.allowed_work_classes:
        errors.append("BUSINESS_EXECUTION_NOT_AUTHORIZED")
    if decision.not_business_completion is not True:
        errors.append("DECISION_CANNOT_BE_BUSINESS_COMPLETION")
    expires = parse_iso(decision.expires_at)
    now = parse_iso(now_at)
    if expires is not None and now is not None and expires <= now:
        errors.append("DECISION_EXPIRED")
    elif decision.expires_at and expires is None:
        errors.append("DECISION_EXPIRY_INVALID")
    return dedupe(errors)


def decision_source_hash(decision: Layer1ApprovedDecision) -> str:
    return stable_hash(
        {
            "decision_id": decision.decision_id,
            "decision_authority_ref": decision.decision_authority_ref,
            "source_refs": decision.source_refs,
            "dispatch_packet_ref": decision.dispatch_packet_ref,
            "no_go_scope": decision.no_go_scope,
            "evidence_required": decision.evidence_required,
        }
    )


def policy_hash(policy: ControllerBridgePolicy) -> str:
    return stable_hash(
        {
            "decision_validity_seconds": policy.decision_validity_seconds,
            "lease_ttl_seconds": policy.lease_ttl_seconds,
            "release_deadline_seconds": policy.release_deadline_seconds,
            "assignment_ttl_seconds": policy.assignment_ttl_seconds,
            "result_timeout_seconds": policy.result_timeout_seconds,
        }
    )


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return sha256(encoded).hexdigest()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error and error not in deduped:
            deduped.append(error)
    return deduped


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value
