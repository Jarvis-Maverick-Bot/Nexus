from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .errors import ErrorCode
from .execution import Layer1WorkPacket, validate_layer1_workpacket
from .schemas import ActorRef, CommandEnvelope, ValidationResult, validate_command_envelope


DISPATCH_COMPONENT = "Layer 1 / Layer 2 Dispatch Contract"
DISPATCH_COMMAND_TYPES: tuple[str, ...] = (
    "EvaluateDispatchReadiness",
    "CreateDispatchControllerHandoffCandidate",
    "NormalizeDispatchReturn",
)
READINESS_REVIEW_STATUSES: tuple[str, ...] = ("draft", "passed", "failed", "blocked", "superseded")
DISPATCH_DECISION_STATUSES: tuple[str, ...] = (
    "draft",
    "accepted_for_dispatch",
    "blocked",
    "stale",
    "superseded",
)
HANDOFF_CANDIDATE_STATUSES: tuple[str, ...] = ("candidate", "mapped", "blocked", "returned", "superseded")
RETURNED_RESULT_STATUSES: tuple[str, ...] = (
    "returned_result_candidate",
    "under_review",
    "revise",
    "rejected",
    "superseded",
)
RETURNED_BLOCKED_STATUSES: tuple[str, ...] = ("returned_blocked", "open", "routed", "resolved", "superseded")
RUNTIME_OR_ACCEPTANCE_STATUSES: tuple[str, ...] = (
    "dispatch",
    "dispatch_execute",
    "dispatched",
    "accepted",
    "complete",
    "final_pass",
    "production_ready",
    "executed",
)
COMPLETION_OR_ACCEPTANCE_RETURN_KINDS: tuple[str, ...] = ("final_pass", "complete", "accepted", "production_ready")
LEGAL_RETURN_KINDS: tuple[str, ...] = (
    "result_candidate",
    "returned_result_candidate",
    "blocked_reason",
    "returned_blocked",
)
DISALLOWED_EXPECTED_OUTPUT_TERMS: tuple[str, ...] = (
    "dispatch",
    "runtime dispatch",
    "actual dispatch",
    "live dispatch",
    "controller call",
    "controller execution",
    "controller request",
    "controller action",
    "controller invocation",
    "adapter call",
    "route activation",
    "private-agent invocation",
    "private agent invocation",
    "runtime invocation",
    "transport call",
    "workpacket execution",
)
LIVE_INTENT_KEYS: tuple[str, ...] = (
    "controller_call",
    "controller_request",
    "controller_action",
    "runtime_invocation",
    "runtime_route",
    "private_agent_invocation",
    "transport_call",
    "route_activation",
    "adapter_call",
    "workpacket_execution",
    "actual_dispatch",
)
LIVE_INTENT_VALUE_KEYS: tuple[str, ...] = (
    "requested_action",
    "action",
    "dispatch_action",
    "runtime_action",
    "controller_action",
)


@dataclass(frozen=True)
class DispatchValidationResult:
    accepted: bool
    error_code: ErrorCode | None = None
    message: str = ""
    missing_fields: tuple[str, ...] = ()
    blocked_reasons: tuple[str, ...] = ()
    invalid_items: tuple[str, ...] = ()

    def to_evidence(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "blocked_reasons": list(self.blocked_reasons),
            "error_code": self.error_code.value if self.error_code else None,
            "invalid_items": list(self.invalid_items),
            "message": self.message,
            "missing_fields": list(self.missing_fields),
        }


@dataclass(frozen=True)
class Layer2CapabilityProfileRef:
    profile_id: str = ""
    profile_version: str = ""
    eligible_owner_roles: tuple[str, ...] = ()
    eligible_runtime_classes: tuple[str, ...] = ()
    capability_tags: tuple[str, ...] = ()
    readiness_constraints: tuple[str, ...] = ()
    authority_constraints: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    baseline_ref: str = ""
    status: str = ""


@dataclass(frozen=True)
class Layer3TransportConstraintRef:
    constraint_id: str = ""
    constraint_version: str = ""
    durability_ref: str = ""
    retry_policy_ref: str = ""
    recovery_constraint_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    baseline_ref: str = ""
    status: str = ""
    ack_is_progress: bool = False


@dataclass(frozen=True)
class DispatchContext:
    command_id: str = ""
    correlation_id: str = ""
    causation_id: str = ""
    requester_role: str = ""
    request_timestamp: str = ""
    idempotency_key: str = ""
    expected_version: int = 0


@dataclass(frozen=True)
class DispatchContractOutputBase:
    item_id: str = ""
    item_type: str = ""
    project_id: str = ""
    workspace_id: str = ""
    packet_id: str = ""
    packet_version: int = 1
    source_authority_refs: tuple[str, ...] = ()
    kernel_packet_record_ref: str = ""
    status: str = ""
    owning_component: str = ""
    consumer_component_refs: tuple[str, ...] = ()
    correlation_id: str = ""
    causation_id: str = ""
    idempotency_key: str = ""
    notes: str = ""
    created_by_component: str = DISPATCH_COMPONENT
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass(frozen=True)
class DispatchReadinessReview(DispatchContractOutputBase):
    review_id: str = ""
    packet_ref: str = ""
    authority_check: str = ""
    completeness_check: str = ""
    owner_eligibility_check: str = ""
    capability_check: str = ""
    transport_constraint_check: str = ""
    no_go_check: str = ""
    stop_rule_check: str = ""
    idempotency_check: str = ""
    result: str = ""
    blocked_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class DispatchDecision(DispatchContractOutputBase):
    decision_id: str = ""
    packet_ref: str = ""
    readiness_review_ref: str = ""
    route_basis: str = ""
    capability_basis: str = ""
    reason: str = ""
    blocked_reason: str = ""
    result_refs: tuple[str, ...] = ()
    reviewer_or_authority_refs: tuple[str, ...] = ()
    kernel_record_ref: str = ""


@dataclass(frozen=True)
class DispatchControllerHandoffCandidate(DispatchContractOutputBase):
    handoff_candidate_id: str = ""
    dispatch_decision_ref: str = ""
    packet_ref: str = ""
    route_basis: str = ""
    required_capability: str = ""
    owner_role: str = ""
    no_go_refs: tuple[str, ...] = ()
    evidence_contract_ref: str = ""
    expected_outputs: tuple[str, ...] = ()
    forbidden_outputs: tuple[str, ...] = ()
    stop_rules: tuple[str, ...] = ()
    blocked_return_schema: dict[str, str] = field(default_factory=dict)
    controller_baseline_ref: str = ""
    controller_call: dict[str, Any] = field(default_factory=dict)
    runtime_invocation: dict[str, Any] = field(default_factory=dict)
    transport_call: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReturnedResultCandidate(DispatchContractOutputBase):
    result_candidate_id: str = ""
    dispatch_decision_ref: str = ""
    packet_ref: str = ""
    result_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    owner_notes: str = ""
    validation_candidate: str = ""
    monitor_task_ref: str = ""


@dataclass(frozen=True)
class ReturnedBlockedReason(DispatchContractOutputBase):
    blocked_id: str = ""
    dispatch_decision_ref: str = ""
    packet_ref: str = ""
    category: str = ""
    affected_layer: str = ""
    required_decision_or_action: str = ""
    source_refs: tuple[str, ...] = ()
    repair_hint: str = ""
    impact_candidate_ref: str = ""


def validate_dispatch_output_base(item: DispatchContractOutputBase) -> DispatchValidationResult:
    missing = _missing_fields(
        item,
        (
            "item_id",
            "item_type",
            "project_id",
            "workspace_id",
            "packet_id",
            "packet_version",
            "source_authority_refs",
            "kernel_packet_record_ref",
            "status",
            "owning_component",
            "consumer_component_refs",
            "correlation_id",
            "idempotency_key",
        ),
    )
    blocked_reasons: list[str] = []
    if item.created_by_component != DISPATCH_COMPONENT:
        blocked_reasons.append("created_by_component must be Layer 1 / Layer 2 Dispatch Contract")
    if item.owning_component != DISPATCH_COMPONENT:
        blocked_reasons.append("owning_component must be Layer 1 / Layer 2 Dispatch Contract")
    if not _is_positive_int(item.packet_version):
        blocked_reasons.append("packet_version must be a positive integer")
    if missing or blocked_reasons:
        return DispatchValidationResult(
            False,
            ErrorCode.DISPATCH_RECORD_INVALID,
            message="dispatch output base rejected",
            missing_fields=missing,
            blocked_reasons=tuple(blocked_reasons),
        )
    return DispatchValidationResult(True, message="dispatch output base accepted")


def validate_layer2_capability_profile(profile: Layer2CapabilityProfileRef) -> DispatchValidationResult:
    missing = _missing_fields(
        profile,
        (
            "profile_id",
            "profile_version",
            "eligible_owner_roles",
            "eligible_runtime_classes",
            "capability_tags",
            "readiness_constraints",
            "authority_constraints",
            "source_refs",
            "baseline_ref",
            "status",
        ),
    )
    blocked_reasons: list[str] = []
    if profile.baseline_ref != "4.19":
        blocked_reasons.append("Layer2CapabilityProfileRef must cite 4.19 baseline")
    if profile.status != "validated":
        blocked_reasons.append("Layer2CapabilityProfileRef status must be validated")
    return _record_result(missing, blocked_reasons, "layer 2 capability profile rejected")


def validate_layer3_transport_constraint(constraint: Layer3TransportConstraintRef) -> DispatchValidationResult:
    missing = _missing_fields(
        constraint,
        (
            "constraint_id",
            "constraint_version",
            "durability_ref",
            "retry_policy_ref",
            "recovery_constraint_refs",
            "source_refs",
            "baseline_ref",
            "status",
        ),
    )
    blocked_reasons: list[str] = []
    if constraint.ack_is_progress:
        return DispatchValidationResult(
            False,
            ErrorCode.ACK_NOT_ACCEPTANCE,
            message="transport constraint rejected",
            missing_fields=missing,
            blocked_reasons=("ACK/progress cannot be treated as Layer 1 progress",),
        )
    if constraint.baseline_ref != "3.5":
        blocked_reasons.append("Layer3TransportConstraintRef must cite 3.5 baseline")
    if constraint.status != "validated":
        blocked_reasons.append("Layer3TransportConstraintRef status must be validated")
    return _record_result(missing, blocked_reasons, "layer 3 transport constraint rejected")


def validate_dispatch_readiness_inputs(
    *,
    packet: Layer1WorkPacket,
    capability: Layer2CapabilityProfileRef,
    transport_constraints: tuple[Layer3TransportConstraintRef, ...],
    context: DispatchContext,
    kernel_packet_record_ref: str,
) -> DispatchValidationResult:
    blocked_reasons: list[str] = []
    if not kernel_packet_record_ref:
        blocked_reasons.append("Kernel-ready packet record ref is required")
    packet_result = validate_layer1_workpacket(packet)
    if not packet_result.accepted:
        blocked_reasons.extend(packet_result.blocked_reasons or packet_result.missing_fields or (packet_result.message,))
    if packet.status != "ready":
        blocked_reasons.append("packet must be Kernel-ready before dispatch readiness review")
    if not packet.no_go or not packet.stop_rules:
        blocked_reasons.append("packet no-go and stop rules must be preserved")
    capability_result = validate_layer2_capability_profile(capability)
    if not capability_result.accepted:
        blocked_reasons.extend(capability_result.blocked_reasons or capability_result.missing_fields)
    if packet.owner_role and packet.owner_role not in capability.eligible_owner_roles:
        blocked_reasons.append("packet owner_role is not eligible for Layer 2 capability profile")
    if not transport_constraints:
        blocked_reasons.append("Layer3 transport constraints are required")
    for constraint in transport_constraints:
        constraint_result = validate_layer3_transport_constraint(constraint)
        if not constraint_result.accepted:
            return constraint_result if constraint_result.error_code == ErrorCode.ACK_NOT_ACCEPTANCE else DispatchValidationResult(
                False,
                ErrorCode.DISPATCH_RECORD_INVALID,
                message="dispatch readiness rejected",
                blocked_reasons=tuple(blocked_reasons + list(constraint_result.blocked_reasons)),
                missing_fields=constraint_result.missing_fields,
            )
    context_missing = _missing_fields(
        context,
        ("command_id", "correlation_id", "causation_id", "requester_role", "request_timestamp", "idempotency_key"),
    )
    if context_missing:
        blocked_reasons.append(f"dispatch context missing: {', '.join(context_missing)}")
    if not _is_non_negative_int(context.expected_version):
        blocked_reasons.append("dispatch context expected_version must be a non-negative integer")
    if blocked_reasons:
        return DispatchValidationResult(
            False,
            ErrorCode.DISPATCH_RECORD_INVALID,
            message="dispatch readiness rejected",
            missing_fields=context_missing,
            blocked_reasons=tuple(dict.fromkeys(blocked_reasons)),
        )
    return DispatchValidationResult(True, message="dispatch readiness accepted")


def validate_dispatch_readiness_review(review: DispatchReadinessReview) -> DispatchValidationResult:
    base = validate_dispatch_output_base(review)
    if not base.accepted:
        return base
    missing = _missing_fields(
        review,
        (
            "review_id",
            "packet_ref",
            "authority_check",
            "completeness_check",
            "owner_eligibility_check",
            "capability_check",
            "transport_constraint_check",
            "no_go_check",
            "stop_rule_check",
            "idempotency_check",
            "result",
        ),
    )
    blocked_reasons: list[str] = []
    if review.status not in READINESS_REVIEW_STATUSES:
        blocked_reasons.append(f"DispatchReadinessReview status rejected: {review.status}")
    if review.result == "failed" and not review.blocked_reasons:
        blocked_reasons.append("failed readiness review requires blocked reasons")
    return _record_result(missing, blocked_reasons, "dispatch readiness review rejected")


def validate_dispatch_decision(decision: DispatchDecision) -> DispatchValidationResult:
    if _is_runtime_or_acceptance_status(decision.status):
        return DispatchValidationResult(
            False,
            ErrorCode.NO_GO_BOUNDARY,
            message="dispatch decision crossed Slice 005 boundary",
            blocked_reasons=(f"DispatchDecision cannot claim {decision.status}",),
        )
    base = validate_dispatch_output_base(decision)
    if not base.accepted:
        return base
    missing = _missing_fields(
        decision,
        (
            "decision_id",
            "packet_ref",
            "readiness_review_ref",
            "route_basis",
            "capability_basis",
            "reason",
            "reviewer_or_authority_refs",
        ),
    )
    blocked_reasons: list[str] = []
    if decision.status not in DISPATCH_DECISION_STATUSES:
        blocked_reasons.append(f"DispatchDecision status rejected: {decision.status}")
    if decision.status == "blocked" and not decision.blocked_reason:
        blocked_reasons.append("blocked dispatch decisions require blocked_reason")
    return _record_result(missing, blocked_reasons, "dispatch decision rejected")


def validate_handoff_candidate(candidate: DispatchControllerHandoffCandidate) -> DispatchValidationResult:
    if _payload_has_live_intent(candidate.__dict__):
        return DispatchValidationResult(
            False,
            ErrorCode.NO_GO_BOUNDARY,
            message="handoff candidate crossed Slice 005 boundary",
            blocked_reasons=("handoff candidate must remain non-live",),
        )
    if _expected_outputs_request_runtime_dispatch(candidate.expected_outputs):
        return DispatchValidationResult(
            False,
            ErrorCode.NO_GO_BOUNDARY,
            message="handoff candidate crossed Slice 005 boundary",
            blocked_reasons=("handoff candidate expected_outputs cannot request runtime dispatch",),
        )
    if _expected_outputs_request_execution(candidate.expected_outputs):
        return DispatchValidationResult(
            False,
            ErrorCode.NO_GO_BOUNDARY,
            message="handoff candidate crossed Slice 005 boundary",
            blocked_reasons=("handoff candidate expected_outputs cannot request dispatch/controller/runtime execution",),
        )
    base = validate_dispatch_output_base(candidate)
    if not base.accepted:
        return base
    missing = _missing_fields(
        candidate,
        (
            "handoff_candidate_id",
            "dispatch_decision_ref",
            "packet_ref",
            "route_basis",
            "required_capability",
            "owner_role",
            "no_go_refs",
            "evidence_contract_ref",
            "expected_outputs",
            "forbidden_outputs",
            "stop_rules",
            "blocked_return_schema",
            "controller_baseline_ref",
        ),
    )
    blocked_reasons: list[str] = []
    if candidate.status not in HANDOFF_CANDIDATE_STATUSES:
        blocked_reasons.append(f"DispatchControllerHandoffCandidate status rejected: {candidate.status}")
    if candidate.controller_baseline_ref != "4.19":
        blocked_reasons.append("handoff candidate must cite 4.19 baseline only")
    return _record_result(missing, blocked_reasons, "handoff candidate rejected")


def validate_returned_result_candidate(candidate: ReturnedResultCandidate) -> DispatchValidationResult:
    if _is_runtime_or_acceptance_status(candidate.status):
        return DispatchValidationResult(
            False,
            ErrorCode.ACK_NOT_ACCEPTANCE,
            message="returned result candidate is not acceptance",
            blocked_reasons=("returned result candidate cannot accept progress",),
        )
    base = validate_dispatch_output_base(candidate)
    if not base.accepted:
        return base
    missing = _missing_fields(
        candidate,
        (
            "result_candidate_id",
            "dispatch_decision_ref",
            "packet_ref",
            "result_refs",
            "evidence_refs",
            "owner_notes",
            "validation_candidate",
            "monitor_task_ref",
        ),
    )
    blocked_reasons: list[str] = []
    if candidate.status not in RETURNED_RESULT_STATUSES:
        blocked_reasons.append(f"ReturnedResultCandidate status rejected: {candidate.status}")
    if missing or blocked_reasons:
        return DispatchValidationResult(
            False,
            ErrorCode.DISPATCH_RETURN_INVALID,
            message="returned result candidate rejected",
            missing_fields=missing,
            blocked_reasons=tuple(blocked_reasons),
        )
    return DispatchValidationResult(True, message="returned result candidate accepted")


def validate_returned_blocked_reason(blocked: ReturnedBlockedReason) -> DispatchValidationResult:
    base = validate_dispatch_output_base(blocked)
    if not base.accepted:
        return base
    missing = _missing_fields(
        blocked,
        (
            "blocked_id",
            "dispatch_decision_ref",
            "packet_ref",
            "category",
            "affected_layer",
            "required_decision_or_action",
            "source_refs",
            "repair_hint",
        ),
    )
    blocked_reasons: list[str] = []
    if blocked.status not in RETURNED_BLOCKED_STATUSES:
        blocked_reasons.append(f"ReturnedBlockedReason status rejected: {blocked.status}")
    if missing or blocked_reasons:
        return DispatchValidationResult(
            False,
            ErrorCode.DISPATCH_RETURN_INVALID,
            message="returned blocked reason rejected",
            missing_fields=missing,
            blocked_reasons=tuple(blocked_reasons),
        )
    return DispatchValidationResult(True, message="returned blocked reason accepted")


def evaluate_dispatch_readiness_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    packet_ref: str,
    packet_version: int,
    kernel_packet_record_ref: str,
    readiness_review_id: str,
    capability_ref: str,
    transport_constraint_refs: tuple[str, ...],
    dispatch_context: dict[str, Any],
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="EvaluateDispatchReadiness",
        actor=actor,
        authority_refs=authority_refs,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        affects_state=False,
        payload={
            "capability_ref": capability_ref,
            "dispatch_context": dispatch_context,
            "expected_version": expected_version,
            "idempotency_key": idempotency_key,
            "kernel_packet_record_ref": kernel_packet_record_ref,
            "packet_ref": packet_ref,
            "packet_version": packet_version,
            "projection_type": "dispatch-readiness",
            "readiness_review_id": readiness_review_id,
            "source_refs": authority_refs,
            "transport_constraint_refs": transport_constraint_refs,
        },
    )


def create_dispatch_controller_handoff_candidate_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    dispatch_decision_ref: str,
    packet_ref: str,
    packet_version: int,
    kernel_packet_record_ref: str,
    route_basis: str,
    required_capability: str,
    owner_role: str,
    correlation_id: str,
    causation_id: str,
    idempotency_key: str,
    no_go_refs: tuple[str, ...],
    evidence_contract_ref: str,
    expected_outputs: tuple[str, ...],
    forbidden_outputs: tuple[str, ...],
    stop_rules: tuple[str, ...],
    blocked_return_schema: dict[str, str],
    controller_baseline_ref: str,
    expected_version: int,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="CreateDispatchControllerHandoffCandidate",
        actor=actor,
        authority_refs=authority_refs,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        affects_state=False,
        payload={
            "blocked_return_schema": blocked_return_schema,
            "causation_id": causation_id,
            "controller_baseline_ref": controller_baseline_ref,
            "correlation_id": correlation_id,
            "dispatch_decision_ref": dispatch_decision_ref,
            "evidence_contract_ref": evidence_contract_ref,
            "expected_outputs": expected_outputs,
            "expected_version": expected_version,
            "forbidden_outputs": forbidden_outputs,
            "idempotency_key": idempotency_key,
            "kernel_packet_record_ref": kernel_packet_record_ref,
            "no_go_refs": no_go_refs,
            "owner_role": owner_role,
            "packet_ref": packet_ref,
            "packet_version": packet_version,
            "projection_type": "dispatch-handoff-candidate",
            "required_capability": required_capability,
            "route_basis": route_basis,
            "source_refs": authority_refs,
            "stop_rules": stop_rules,
        },
    )


def normalize_dispatch_return_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    dispatch_decision_ref: str,
    correlation_id: str,
    return_kind: str,
    result_refs: tuple[str, ...],
    evidence_refs: tuple[str, ...],
    blocked_reason: str,
    owner_notes: str,
    source_refs: tuple[str, ...],
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="NormalizeDispatchReturn",
        actor=actor,
        authority_refs=authority_refs,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        affects_state=False,
        payload={
            "blocked_reason": blocked_reason,
            "correlation_id": correlation_id,
            "dispatch_decision_ref": dispatch_decision_ref,
            "evidence_refs": evidence_refs,
            "expected_version": expected_version,
            "idempotency_key": idempotency_key,
            "owner_notes": owner_notes,
            "projection_type": "dispatch-return-normalization",
            "result_refs": result_refs,
            "return_kind": return_kind,
            "source_refs": source_refs,
        },
    )


def validate_dispatch_command(command: CommandEnvelope) -> ValidationResult:
    validation = validate_command_envelope(command)
    if not validation.accepted:
        return validation
    if command.command_type not in DISPATCH_COMMAND_TYPES:
        return ValidationResult(False, ErrorCode.DISPATCH_COMMAND_INVALID, "unknown Dispatch Contract command")
    if _command_has_live_intent(command):
        return ValidationResult(
            False,
            ErrorCode.NO_GO_BOUNDARY,
            "Dispatch Contract command cannot execute runtime or controller work",
        )
    if command.command_type == "CreateDispatchControllerHandoffCandidate" and _expected_outputs_request_runtime_dispatch(
        command.payload.get("expected_outputs", ())
    ):
        return ValidationResult(
            False,
            ErrorCode.NO_GO_BOUNDARY,
            "Dispatch Contract command expected_outputs cannot request runtime dispatch",
        )
    if command.command_type == "CreateDispatchControllerHandoffCandidate" and _expected_outputs_request_execution(
        command.payload.get("expected_outputs", ())
    ):
        return ValidationResult(
            False,
            ErrorCode.NO_GO_BOUNDARY,
            "Dispatch Contract command expected_outputs cannot request dispatch/controller/runtime execution",
        )
    if _command_treats_ack_as_acceptance(command):
        return ValidationResult(
            False,
            ErrorCode.ACK_NOT_ACCEPTANCE,
            "ACK/progress/controller output is not Layer 1 acceptance",
        )
    if command.command_type == "NormalizeDispatchReturn" and _return_kind_claims_completion_or_acceptance(
        command.payload.get("return_kind", "")
    ):
        return ValidationResult(
            False,
            ErrorCode.ACK_NOT_ACCEPTANCE,
            "Dispatch return kind cannot claim completion or acceptance",
        )
    if command.command_type == "NormalizeDispatchReturn" and not _return_kind_is_legal(command.payload.get("return_kind", "")):
        return ValidationResult(
            False,
            ErrorCode.DISPATCH_COMMAND_INVALID,
            "return_kind is not legal for Dispatch Contract normalization",
        )
    for field_name in _required_payload_fields(command.command_type):
        if _payload_field_missing(command.payload, field_name):
            return ValidationResult(False, ErrorCode.DISPATCH_COMMAND_INVALID, f"{field_name} is required")
    source_refs = command.payload["source_refs"]
    if not isinstance(source_refs, (list, tuple)) or tuple(source_refs) != tuple(command.authority_refs):
        return ValidationResult(False, ErrorCode.DISPATCH_COMMAND_INVALID, "source_refs must match authority_refs")
    if not _is_non_negative_int(command.payload["expected_version"]):
        return ValidationResult(False, ErrorCode.DISPATCH_COMMAND_INVALID, "expected_version must be a non-negative integer")
    if not _payload_version_matches_envelope(command):
        return ValidationResult(
            False,
            ErrorCode.DISPATCH_COMMAND_INVALID,
            "payload expected_version must match envelope expected_version",
        )
    if command.payload["idempotency_key"] != command.idempotency_key:
        return ValidationResult(
            False,
            ErrorCode.DISPATCH_COMMAND_INVALID,
            "payload idempotency_key must match envelope idempotency_key",
        )
    if command.command_type in ("EvaluateDispatchReadiness", "CreateDispatchControllerHandoffCandidate") and not _is_positive_int(
        command.payload["packet_version"]
    ):
        return ValidationResult(False, ErrorCode.DISPATCH_COMMAND_INVALID, "packet_version must be a positive integer")
    if command.command_type == "CreateDispatchControllerHandoffCandidate" and command.payload["controller_baseline_ref"] != "4.19":
        return ValidationResult(False, ErrorCode.DISPATCH_COMMAND_INVALID, "controller_baseline_ref must cite 4.19")
    return ValidationResult(True)


def _required_payload_fields(command_type: str) -> tuple[str, ...]:
    if command_type == "EvaluateDispatchReadiness":
        return (
            "packet_ref",
            "packet_version",
            "kernel_packet_record_ref",
            "readiness_review_id",
            "capability_ref",
            "transport_constraint_refs",
            "dispatch_context",
            "source_refs",
            "expected_version",
            "idempotency_key",
        )
    if command_type == "CreateDispatchControllerHandoffCandidate":
        return (
            "dispatch_decision_ref",
            "packet_ref",
            "packet_version",
            "kernel_packet_record_ref",
            "route_basis",
            "required_capability",
            "owner_role",
            "correlation_id",
            "causation_id",
            "no_go_refs",
            "evidence_contract_ref",
            "expected_outputs",
            "forbidden_outputs",
            "stop_rules",
            "blocked_return_schema",
            "controller_baseline_ref",
            "source_refs",
            "expected_version",
            "idempotency_key",
        )
    if command_type == "NormalizeDispatchReturn":
        return (
            "dispatch_decision_ref",
            "correlation_id",
            "return_kind",
            "source_refs",
            "expected_version",
            "idempotency_key",
        )
    return ()


def _record_result(
    missing: tuple[str, ...],
    blocked_reasons: list[str],
    message: str,
) -> DispatchValidationResult:
    if missing or blocked_reasons:
        return DispatchValidationResult(
            False,
            ErrorCode.DISPATCH_RECORD_INVALID,
            message=message,
            missing_fields=missing,
            blocked_reasons=tuple(blocked_reasons),
        )
    return DispatchValidationResult(True, message=message.replace("rejected", "accepted"))


def _missing_fields(item: object, field_names: tuple[str, ...]) -> tuple[str, ...]:
    missing: list[str] = []
    values = item if isinstance(item, dict) else item.__dict__
    for field_name in field_names:
        if _payload_field_missing(values, field_name):
            missing.append(field_name)
    return tuple(missing)


def _payload_field_missing(payload: dict[str, Any], field_name: str) -> bool:
    if field_name not in payload:
        return True
    value = payload[field_name]
    if value is None:
        return True
    if isinstance(value, str):
        return value == ""
    if isinstance(value, (dict, list, set, tuple)):
        return len(value) == 0
    return False


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _payload_version_matches_envelope(command: CommandEnvelope) -> bool:
    return _is_non_negative_int(command.expected_version) and command.payload["expected_version"] == command.expected_version


def _is_runtime_or_acceptance_status(status: object) -> bool:
    return str(status).strip().lower() in RUNTIME_OR_ACCEPTANCE_STATUSES


def _return_kind_claims_completion_or_acceptance(return_kind: object) -> bool:
    return str(return_kind).strip().lower() in COMPLETION_OR_ACCEPTANCE_RETURN_KINDS


def _return_kind_is_legal(return_kind: object) -> bool:
    return str(return_kind).strip().lower() in LEGAL_RETURN_KINDS


def _expected_outputs_request_runtime_dispatch(expected_outputs: object) -> bool:
    return any(value == "runtime dispatch" for value in _normalized_expected_output_values(expected_outputs))


def _expected_outputs_request_execution(expected_outputs: object) -> bool:
    return any(value in DISALLOWED_EXPECTED_OUTPUT_TERMS for value in _normalized_expected_output_values(expected_outputs))


def _normalized_expected_output_values(expected_outputs: object) -> tuple[str, ...]:
    if isinstance(expected_outputs, str):
        return (_normalize_term(expected_outputs),)
    elif isinstance(expected_outputs, (list, tuple, set)):
        return tuple(_normalize_term(value) for value in expected_outputs)
    return ()


def _normalize_term(value: object) -> str:
    return str(value).strip().lower().replace("_", " ").replace("-", " ")


def _command_has_live_intent(command: CommandEnvelope) -> bool:
    return _payload_has_live_intent(command.payload)


def _payload_has_live_intent(payload: dict[str, Any]) -> bool:
    for key, value in payload.items():
        normalized_key = str(key).strip().lower()
        if normalized_key in LIVE_INTENT_KEYS and not _payload_value_empty(value):
            return True
        if normalized_key in LIVE_INTENT_VALUE_KEYS and _is_runtime_or_acceptance_status(value):
            return True
        if isinstance(value, dict) and _payload_has_live_intent(value):
            return True
        if isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, dict) and _payload_has_live_intent(item):
                    return True
    return False


def _payload_value_empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value == ""
    if isinstance(value, (dict, list, set, tuple)):
        return len(value) == 0
    return False


def _command_treats_ack_as_acceptance(command: CommandEnvelope) -> bool:
    if command.command_type != "NormalizeDispatchReturn":
        return False
    return_kind = str(command.payload.get("return_kind", "")).strip().lower()
    status = str(command.payload.get("status", "")).strip().lower()
    if return_kind not in ("ack", "progress", "controller_output"):
        return False
    return status in ("accepted", "complete", "final_pass", "production_ready")
