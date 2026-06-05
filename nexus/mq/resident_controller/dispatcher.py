"""Bounded resident controller dispatch guards.

The functions in this module only build deterministic decisions. They do not
publish to NATS or mutate any broker state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any, Optional

from nexus.mq.agent_registry import AgentRegistryRecord
from nexus.mq.agent_registry_events import secret_material_errors
from nexus.mq.eligibility_reservation_policy import (
    RuntimeEligibilityDecision,
    RuntimeReservationLease,
    validate_assignment_publish,
)
from nexus.mq.resident_controller.observer import evaluate_runtime_observation


RESIDENT_DISPATCH_REQUEST_SCHEMA_VERSION = "4.19.resident_controller.dispatch_request.v1"
ALLOWED_ASSIGNMENT_KINDS = {"non_business_probe", "readiness_probe", "diagnostic_probe"}
DEFAULT_ALLOWED_WBS_IDS = {"7.19.14.5", "7.19.15", "7.19.15.2"}
COMMAND_TO_FAMILY = {
    "controller_init": "controller.init",
    "bounded_assignment": "assignment",
    "duplicate_replay": "assignment.duplicate_replay",
    "drain": "drain",
}


@dataclass
class SubjectPolicyDecision:
    accepted: bool
    errors: list[str] = field(default_factory=list)
    not_business_completion: bool = True


@dataclass
class ResidentControllerSubjectPolicy:
    namespace: str
    run_id: str
    allowed_agents: list[str]
    publish_allowlist: list[str]
    not_business_completion: bool = True


@dataclass
class ResidentControllerDispatchPolicy:
    dispatch_enabled: bool = False
    uat_authorized: bool = False
    allowed_wbs_ids: set[str] = field(default_factory=lambda: set(DEFAULT_ALLOWED_WBS_IDS))
    allowed_commands: set[str] = field(default_factory=lambda: set(COMMAND_TO_FAMILY))
    business_execution_allowed: bool = False


@dataclass
class ResidentControllerDispatchRequest:
    assignment_id: str
    idempotency_key: str
    run_id: str
    wbs_id: str
    target_agent_id: str
    target_runtime_instance_id: str
    assignment_kind: str
    command: str
    source_authority_ref: str
    no_go_scope_ref: str
    lifecycle_decision_id: str = ""
    reservation_lease_id: str = ""
    schema_version: str = RESIDENT_DISPATCH_REQUEST_SCHEMA_VERSION
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResidentControllerDispatchDecision:
    accepted: bool
    published: bool = False
    subject: Optional[str] = None
    message_id: Optional[str] = None
    lifecycle_decision_id: str = ""
    reservation_lease_id: str = ""
    duplicate_suppressed: bool = False
    errors: list[str] = field(default_factory=list)
    not_business_completion: bool = True


def validate_publish_subject(subject: str, policy: ResidentControllerSubjectPolicy) -> SubjectPolicyDecision:
    errors: list[str] = []
    if "*" in subject or ">" in subject:
        errors.append("PUBLISH_SUBJECT_CANNOT_CONTAIN_WILDCARD")
    parts = subject.split(".")
    namespace_parts = policy.namespace.split(".")
    if parts[: len(namespace_parts)] != namespace_parts:
        errors.append("PUBLISH_SUBJECT_NAMESPACE_MISMATCH")
    run_index = len(namespace_parts)
    agent_index = run_index + 1
    if len(parts) <= agent_index:
        errors.append("PUBLISH_SUBJECT_MALFORMED")
    else:
        if parts[run_index] != policy.run_id:
            errors.append("PUBLISH_SUBJECT_RUN_ID_MISMATCH")
        if parts[agent_index] not in policy.allowed_agents:
            errors.append("PUBLISH_SUBJECT_AGENT_NOT_ALLOWED")
    if not _matches_publish_allowlist(subject, policy):
        errors.append("PUBLISH_SUBJECT_NOT_ALLOWLISTED")
    return SubjectPolicyDecision(accepted=not errors, errors=_dedupe(errors))


def evaluate_resident_dispatch(
    *,
    request: ResidentControllerDispatchRequest,
    runtime: AgentRegistryRecord,
    subject_policy: ResidentControllerSubjectPolicy,
    policy: ResidentControllerDispatchPolicy,
    now_at: str,
    prior_idempotency_keys: Optional[set[str]] = None,
    lifecycle_decision: RuntimeEligibilityDecision | None = None,
    reservation_lease: RuntimeReservationLease | None = None,
) -> ResidentControllerDispatchDecision:
    errors = _request_errors(request, subject_policy=subject_policy, policy=policy)
    observation = evaluate_runtime_observation(runtime, now_at=now_at)
    if not observation.dispatch_eligible:
        errors.extend(observation.errors)
    if request.target_runtime_instance_id != runtime.runtime_instance_id:
        errors.append("TARGET_RUNTIME_INSTANCE_MISMATCH")
    family = COMMAND_TO_FAMILY.get(request.command, "")
    subject = f"{subject_policy.namespace}.{request.run_id}.{request.target_agent_id}.{family}"
    subject_result = validate_publish_subject(subject, subject_policy)
    if not subject_result.accepted:
        errors.extend(subject_result.errors)
    errors.extend(
        _lifecycle_identity_errors(
            request=request,
            lifecycle_decision=lifecycle_decision,
            reservation_lease=reservation_lease,
        )
    )
    publish_validation = validate_assignment_publish(
        decision=lifecycle_decision,
        lease=reservation_lease,
        assignment_id=request.assignment_id,
        dispatch_run_id=request.run_id,
        runtime_instance_id=request.target_runtime_instance_id,
        idempotency_key=request.idempotency_key,
        now_at=now_at,
    )
    if not publish_validation.accepted:
        errors.extend(publish_validation.errors)
    errors.extend(secret_material_errors(request.to_dict(), path="resident_dispatch_request"))
    if errors:
        return ResidentControllerDispatchDecision(
            accepted=False,
            published=False,
            subject=subject,
            lifecycle_decision_id=request.lifecycle_decision_id,
            reservation_lease_id=request.reservation_lease_id,
            errors=_dedupe(errors),
        )
    if request.idempotency_key and prior_idempotency_keys and request.idempotency_key in prior_idempotency_keys:
        return ResidentControllerDispatchDecision(
            accepted=True,
            published=False,
            subject=subject,
            lifecycle_decision_id=request.lifecycle_decision_id,
            reservation_lease_id=request.reservation_lease_id,
            duplicate_suppressed=True,
            errors=["DUPLICATE_ASSIGNMENT_SUPPRESSED"],
        )
    message_digest = sha256(f"{request.assignment_id}|{request.idempotency_key}|{subject}".encode("utf-8")).hexdigest()
    return ResidentControllerDispatchDecision(
        accepted=True,
        published=False,
        subject=subject,
        message_id=f"resident-candidate-{message_digest[:16]}",
        lifecycle_decision_id=request.lifecycle_decision_id,
        reservation_lease_id=request.reservation_lease_id,
    )


def _request_errors(
    request: ResidentControllerDispatchRequest,
    *,
    subject_policy: ResidentControllerSubjectPolicy,
    policy: ResidentControllerDispatchPolicy,
) -> list[str]:
    errors: list[str] = []
    if request.schema_version != RESIDENT_DISPATCH_REQUEST_SCHEMA_VERSION:
        errors.append("UNSUPPORTED_RESIDENT_DISPATCH_REQUEST_SCHEMA")
    if not policy.dispatch_enabled:
        errors.append("RESIDENT_DISPATCH_DISABLED")
    if not policy.uat_authorized:
        errors.append("UAT_AUTHORIZATION_REQUIRED")
    if request.wbs_id not in policy.allowed_wbs_ids:
        errors.append(f"WBS_ID_NOT_ALLOWED: {request.wbs_id}")
    if request.command not in policy.allowed_commands:
        errors.append(f"COMMAND_NOT_ALLOWED: {request.command}")
    if request.assignment_kind not in ALLOWED_ASSIGNMENT_KINDS:
        errors.append("BUSINESS_EXECUTION_NOT_AUTHORIZED")
    if request.not_business_completion is not True:
        errors.append("BUSINESS_EXECUTION_NOT_AUTHORIZED")
    if policy.business_execution_allowed:
        errors.append("BUSINESS_EXECUTION_NOT_AUTHORIZED")
    for field_name in (
        "assignment_id",
        "idempotency_key",
        "run_id",
        "wbs_id",
        "target_agent_id",
        "target_runtime_instance_id",
        "assignment_kind",
        "command",
        "source_authority_ref",
        "no_go_scope_ref",
        "lifecycle_decision_id",
        "reservation_lease_id",
    ):
        if not getattr(request, field_name):
            errors.append(f"MISSING_RESIDENT_DISPATCH_FIELD: {field_name}")
    if request.run_id != subject_policy.run_id:
        errors.append("DISPATCH_RUN_ID_MISMATCH")
    if request.target_agent_id not in subject_policy.allowed_agents:
        errors.append("TARGET_AGENT_NOT_ALLOWED")
    return errors


def _lifecycle_identity_errors(
    *,
    request: ResidentControllerDispatchRequest,
    lifecycle_decision: RuntimeEligibilityDecision | None,
    reservation_lease: RuntimeReservationLease | None,
) -> list[str]:
    errors: list[str] = []
    if not request.lifecycle_decision_id:
        errors.append("MISSING_LIFECYCLE_DECISION_ID")
    if not request.reservation_lease_id:
        errors.append("MISSING_RESERVATION_LEASE_ID")
    if lifecycle_decision is not None and request.lifecycle_decision_id != lifecycle_decision.decision_id:
        errors.append("LIFECYCLE_DECISION_ID_MISMATCH")
    if reservation_lease is not None and request.reservation_lease_id != reservation_lease.lease_id:
        errors.append("RESERVATION_LEASE_ID_MISMATCH")
    return errors


def _matches_publish_allowlist(subject: str, policy: ResidentControllerSubjectPolicy) -> bool:
    for pattern in policy.publish_allowlist:
        if pattern.count("*") == 1:
            prefix, suffix = pattern.split("*", 1)
            if subject.startswith(prefix) and subject.endswith(suffix):
                middle = subject[len(prefix) : len(subject) - len(suffix)]
                if len([part for part in middle.split(".") if part]) == 2:
                    return True
            continue
        pattern_parts = pattern.split(".")
        subject_parts = subject.split(".")
        if len(pattern_parts) != len(subject_parts):
            continue
        matched = True
        for pattern_part, subject_part in zip(pattern_parts, subject_parts):
            if pattern_part == "*":
                continue
            if pattern_part != subject_part:
                matched = False
                break
        if matched:
            return True
    return False


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error and error not in deduped:
            deduped.append(error)
    return deduped
