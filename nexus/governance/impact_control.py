from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeVar

from .errors import ErrorCode
from .schemas import ActorRef, CommandEnvelope, ValidationResult, validate_command_envelope


IMPACT_CONTROL_COMPONENT = "Layer Dependency And Impact Control"
IMPACT_CONTROL_COMMAND_TYPES: tuple[str, ...] = (
    "SubmitImpactControlRequest",
    "RecordImpactAssessment",
    "CreateMonitorTaskForImpact",
    "RecordLowerLayerRequestOutcome",
    "RequestWorkaroundDecision",
)
KERNEL_RECORDED_COMMANDS: tuple[str, ...] = (
    "SubmitImpactControlRequest",
    "RecordImpactAssessment",
    "CreateMonitorTaskForImpact",
)

IMPACT_REQUEST_STATUSES: tuple[str, ...] = ("submitted", "assessing", "assessed", "blocked", "superseded")
IMPACT_ASSESSMENT_STATUSES: tuple[str, ...] = (
    "no_impact",
    "local_only",
    "trace_required",
    "monitor_required",
    "lower_layer_owner_path_required",
    "blocked",
    "deferred",
    "superseded",
)
LAYER_IMPACT_STATUSES: tuple[str, ...] = (
    "detected",
    "classified",
    "monitor_opened",
    "approved_request",
    "revised_scope",
    "deferred",
    "blocked",
    "rejected",
    "workaround_approved",
    "closed",
    "superseded",
)
LOWER_LAYER_CANDIDATE_STATUSES: tuple[str, ...] = (
    "draft",
    "approved_candidate",
    "sent_for_owner_review",
    "accepted_by_owner",
    "rejected",
    "deferred",
    "superseded",
)
LOWER_LAYER_OUTCOMES: tuple[str, ...] = ("accepted", "rejected", "deferred", "needs_clarification", "superseded")
SCOPE_REVISION_STATUSES: tuple[str, ...] = (
    "draft",
    "monitor_required",
    "approved_for_standardization_review",
    "rejected",
    "superseded",
)
WORKAROUND_STATUSES: tuple[str, ...] = ("requested", "review_required", "approved", "rejected", "expired", "superseded")
REVIEW_TASK_STATUSES: tuple[str, ...] = ("monitor_opened", "blocked", "superseded")

APPROVED_AFFECTED_SURFACES: tuple[str, ...] = (
    "scope",
    "authority",
    "artifact_relationship",
    "gate_acceptance",
    "runtime_behavior",
    "dispatch_behavior",
    "implementation_contract",
    "evidence_sufficiency",
    "downstream_dependency",
    "rollback_reversibility",
    "lower_layer_dependency",
    "unclear",
)
BASELINE_AFFECTING_SURFACES: tuple[str, ...] = (
    "scope",
    "authority",
    "gate_acceptance",
    "runtime_behavior",
    "dispatch_behavior",
    "implementation_contract",
    "lower_layer_dependency",
)
APPROVED_GAP_TYPES: tuple[str, ...] = (
    "capability_gap_layer2",
    "capability_gap_layer3",
    "contract_mismatch",
    "authority_boundary_conflict",
    "runtime_readiness_gap",
    "evidence_gap",
    "transport_semantics_gap",
    "owner_eligibility_gap",
    "manual_workaround_requested",
)
APPROVED_AFFECTED_LAYERS: tuple[str, ...] = ("layer_1", "layer_2", "layer_3", "cross_layer", "unclear")
ALLOWED_NEXT_ACTIONS: tuple[str, ...] = (
    "proceed_local",
    "proceed_with_trace",
    "open_monitor_review",
    "create_lower_layer_request_candidate",
    "revise_scope_candidate",
    "request_workaround_decision",
    "defer",
    "block",
    "supersede",
)
DIRECT_APPROVAL_TRIGGERS: tuple[str, ...] = (
    "direct_ui_approval",
    "notification_as_decision",
    "status_card_approval",
    "chat_approval",
    "controller_approval",
)
FORBIDDEN_INTENT_TERMS: tuple[str, ...] = (
    "direct_419_controller_call",
    "direct 4.19 controller call",
    "direct 4 19 controller call",
    "direct_35_controller_call",
    "direct 3.5 controller call",
    "direct 3 5 controller call",
    "controller_call",
    "controller call",
    "controller execution",
    "controller request",
    "controller action",
    "owner_path_call",
    "owner path call",
    "call owner path",
    "adapter_call",
    "adapter call",
    "transport_call",
    "transport call",
    "route_activation",
    "route activation",
    "activate route",
    "workpacket_execution",
    "workpacket execution",
    "execute workpacket",
    "dispatch_execution",
    "dispatch execution",
    "actual_dispatch",
    "actual dispatch",
    "runtime_invocation",
    "runtime invocation",
    "runtime live invocation",
    "private_agent_invocation",
    "private-agent invocation",
    "private agent invocation",
    "lower_layer_submission",
    "lower-layer submission",
    "lower layer submission",
    "submit_lower_layer_request",
    "submit lower layer request",
    "submit lower layer",
    "lower layer request submission",
    "config_mutation",
    "config mutation",
    "credential_mutation",
    "credential mutation",
    "workaround_without_decision",
    "workaround without decision",
    "final_pass",
    "final pass",
    "delivery_complete",
    "delivery complete",
    "delivery completed",
    "production_ready",
    "production ready",
    "production readiness",
    "project acceptance",
    "project accepted",
    "dispatch authorization",
    "local impact decision without gate",
    "bypass impact gate",
)
LIVE_INTENT_KEYS: tuple[str, ...] = (
    "controller_call",
    "controller_request",
    "controller_action",
    "owner_path_call",
    "adapter_call",
    "transport_call",
    "route_activation",
    "runtime_invocation",
    "private_agent_invocation",
    "workpacket_execution",
    "dispatch_execution",
    "actual_dispatch",
    "lower_layer_submission",
    "submit_lower_layer_request",
    "config_mutation",
    "credential_mutation",
)
LIVE_INTENT_VALUE_KEYS: tuple[str, ...] = ("requested_action", "action", "proposed_action", "next_action")


@dataclass(frozen=True)
class ImpactControlValidationResult:
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
class ImpactControlRequest:
    request_id: str = ""
    caller_component: str = ""
    caller_workflow_ref: str = ""
    actor_authority_ref: str = ""
    proposed_action: str = ""
    target_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    suspected_impact_surfaces: tuple[str, ...] = ()
    declared_affected_scope: str = ""
    requested_timing: str = ""
    idempotency_key: str = ""
    status: str = "submitted"


@dataclass(frozen=True)
class ImpactAssessment:
    assessment_id: str = ""
    request_ref: str = ""
    impact_level: str = ""
    affected_surfaces: tuple[str, ...] = ()
    actual_impact_classification: str = ""
    risk_level: str = ""
    owner_path_outcome: str = ""
    allowed_next_action: str = ""
    required_reviews: tuple[str, ...] = ()
    evidence_requirements: tuple[str, ...] = ()
    blocked_reason: str = ""
    trace_refs: tuple[str, ...] = ()
    monitor_task_ref: str = ""
    status: str = ""


@dataclass(frozen=True)
class LayerImpactDetected:
    impact_id: str = ""
    project_id: str = ""
    workspace_id: str = ""
    assessment_ref: str = ""
    affected_layer: str = ""
    gap_type: str = ""
    risk: str = ""
    project_effect: str = ""
    source_refs: tuple[str, ...] = ()
    proposed_route: str = ""
    workaround_status: str = ""
    monitor_task_ref: str = ""
    kernel_record_ref: str = ""
    status: str = "detected"


@dataclass(frozen=True)
class ImpactReviewTaskRequest:
    review_task_id: str = ""
    assessment_ref: str = ""
    layer_impact_ref: str = ""
    review_question: str = ""
    options: tuple[str, ...] = ()
    owner_path: str = ""
    recommended_next_action: str = ""
    blocked_state_ref: str = ""
    source_refs: tuple[str, ...] = ()
    status: str = "monitor_opened"


@dataclass(frozen=True)
class LowerLayerRequestCandidate:
    candidate_id: str = ""
    assessment_ref: str = ""
    target_layer: str = ""
    target_workspace_or_owner_path: str = ""
    requested_capability_or_clarification: str = ""
    constraints: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    acceptance_test_hint: str = ""
    boundary_reason: str = ""
    monitor_decision_ref: str = ""
    owner_acceptance_ref: str = ""
    status: str = "draft"


@dataclass(frozen=True)
class LowerLayerRequestOutcome:
    outcome_id: str = ""
    request_candidate_ref: str = ""
    target_layer: str = ""
    owner_ref: str = ""
    outcome: str = ""
    accepted_scope_refs: tuple[str, ...] = ()
    rejection_or_defer_reason: str = ""
    evidence_refs: tuple[str, ...] = ()
    expected_follow_up: str = ""
    kernel_or_owner_record_ref: str = ""


@dataclass(frozen=True)
class ScopeRevisionCandidate:
    revision_id: str = ""
    impact_ref: str = ""
    project_or_packet_refs: tuple[str, ...] = ()
    scope_effect: str = ""
    no_go_effect: str = ""
    proposed_revision: str = ""
    standardization_ref: str = ""
    monitor_decision_ref: str = ""
    status: str = "draft"


@dataclass(frozen=True)
class WorkaroundDecisionRequest:
    request_id: str = ""
    impact_ref: str = ""
    workaround_option: str = ""
    risk: str = ""
    expiry: str = ""
    rollback_condition: str = ""
    evidence_requirement: str = ""
    decision_ref: str = ""
    status: str = "requested"


def validate_impact_control_request(request: ImpactControlRequest) -> ImpactControlValidationResult:
    if _has_forbidden_intent(request.__dict__):
        return _no_go("ImpactControlRequest crossed Slice 007 no-go boundary")
    missing = _missing_fields(
        request,
        (
            "request_id",
            "caller_component",
            "caller_workflow_ref",
            "actor_authority_ref",
            "proposed_action",
            "target_refs",
            "source_refs",
            "evidence_refs",
            "suspected_impact_surfaces",
            "declared_affected_scope",
            "requested_timing",
            "idempotency_key",
        ),
    )
    blocked_reasons: list[str] = []
    invalid_items = _invalid_items(request.suspected_impact_surfaces, APPROVED_AFFECTED_SURFACES)
    if request.status not in IMPACT_REQUEST_STATUSES:
        blocked_reasons.append(f"ImpactControlRequest status rejected: {request.status}")
    return _record_result(
        missing,
        blocked_reasons,
        invalid_items,
        ErrorCode.IMPACT_CONTROL_RECORD_INVALID,
        "ImpactControlRequest rejected",
    )


def validate_impact_assessment(assessment: ImpactAssessment) -> ImpactControlValidationResult:
    if _has_forbidden_intent(assessment.__dict__):
        return _no_go("ImpactAssessment cannot execute, submit, complete, or bypass review")
    missing = list(
        _missing_fields(
            assessment,
            (
                "assessment_id",
                "request_ref",
                "impact_level",
                "affected_surfaces",
                "actual_impact_classification",
                "risk_level",
                "owner_path_outcome",
                "allowed_next_action",
                "evidence_requirements",
                "trace_refs",
                "status",
            ),
        )
    )
    blocked_reasons: list[str] = []
    invalid_items = _invalid_items(assessment.affected_surfaces, APPROVED_AFFECTED_SURFACES)
    if assessment.status not in IMPACT_ASSESSMENT_STATUSES:
        blocked_reasons.append(f"ImpactAssessment status rejected: {assessment.status}")
    if assessment.allowed_next_action not in ALLOWED_NEXT_ACTIONS:
        return _no_go(f"allowed_next_action rejected: {assessment.allowed_next_action}")
    if "unclear" in assessment.affected_surfaces and (
        assessment.status != "blocked" or assessment.allowed_next_action != "block" or not assessment.blocked_reason
    ):
        return _no_go("unclear affected surfaces must fail closed as blocked")
    if assessment.status == "blocked" and not assessment.blocked_reason:
        blocked_reasons.append("blocked assessments require blocked_reason")
    if assessment.status in ("monitor_required", "lower_layer_owner_path_required") and not assessment.required_reviews:
        blocked_reasons.append(f"{assessment.status} assessments require required_reviews")
    if assessment.status in ("monitor_required", "lower_layer_owner_path_required") and not assessment.monitor_task_ref:
        missing.append("monitor_task_ref")
    if assessment.allowed_next_action == "create_lower_layer_request_candidate":
        if not assessment.owner_path_outcome:
            missing.append("owner_path_outcome")
        if not assessment.owner_path_outcome or _normalized(assessment.owner_path_outcome) in {"none", "unknown", "not_applicable"}:
            blocked_reasons.append("lower-layer request candidate requires owner_path_outcome")
        if not assessment.required_reviews:
            blocked_reasons.append("lower-layer request candidate requires Monitor/HITL review")
    if _has_baseline_affecting_surface(assessment.affected_surfaces) and assessment.allowed_next_action in (
        "proceed_local",
        "proceed_with_trace",
    ):
        return _no_go("baseline-affecting impact cannot proceed without Kernel/HITL path")
    if assessment.actual_impact_classification not in APPROVED_GAP_TYPES:
        blocked_reasons.append(f"impact classification rejected: {assessment.actual_impact_classification}")
    return _record_result(
        tuple(dict.fromkeys(missing)),
        blocked_reasons,
        invalid_items,
        ErrorCode.IMPACT_CONTROL_RECORD_INVALID,
        "ImpactAssessment rejected",
    )


def validate_layer_impact_detected(impact: LayerImpactDetected) -> ImpactControlValidationResult:
    if _has_forbidden_intent(impact.__dict__):
        return _no_go("LayerImpactDetected cannot execute, submit, or complete lower-layer work")
    missing = _missing_fields(
        impact,
        (
            "impact_id",
            "project_id",
            "workspace_id",
            "assessment_ref",
            "affected_layer",
            "gap_type",
            "risk",
            "project_effect",
            "source_refs",
            "proposed_route",
            "workaround_status",
            "monitor_task_ref",
            "kernel_record_ref",
            "status",
        ),
    )
    blocked_reasons: list[str] = []
    if impact.status not in LAYER_IMPACT_STATUSES:
        blocked_reasons.append(f"LayerImpactDetected status rejected: {impact.status}")
    if impact.affected_layer not in APPROVED_AFFECTED_LAYERS:
        blocked_reasons.append(f"affected_layer rejected: {impact.affected_layer}")
    if impact.gap_type not in APPROVED_GAP_TYPES:
        blocked_reasons.append(f"gap_type rejected: {impact.gap_type}")
    if impact.status == "workaround_approved" and not _has_human_decision_ref(
        (impact.proposed_route, impact.monitor_task_ref, impact.kernel_record_ref)
    ):
        blocked_reasons.append("workaround_approved requires HumanDecision-backed approval")
    if impact.status == "approved_request" and ("candidate" not in _normalized(impact.proposed_route) or not impact.monitor_task_ref):
        blocked_reasons.append("approved_request requires Monitor decision and candidate-only route")
    return _record_result(
        missing,
        blocked_reasons,
        (),
        ErrorCode.IMPACT_CONTROL_RECORD_INVALID,
        "LayerImpactDetected rejected",
    )


def validate_impact_review_task_request(task: ImpactReviewTaskRequest) -> ImpactControlValidationResult:
    if _has_forbidden_intent(task.__dict__) or _contains_direct_approval(task.options):
        return _no_go("ImpactReviewTaskRequest cannot record decision, approval, or execution")
    missing = _missing_fields(
        task,
        (
            "review_task_id",
            "assessment_ref",
            "layer_impact_ref",
            "review_question",
            "options",
            "owner_path",
            "recommended_next_action",
            "blocked_state_ref",
            "source_refs",
            "status",
        ),
    )
    blocked_reasons: list[str] = []
    if task.status not in REVIEW_TASK_STATUSES:
        blocked_reasons.append(f"ImpactReviewTaskRequest status rejected: {task.status}")
    if len(task.review_question.strip()) < 12:
        blocked_reasons.append("review_question is ambiguous")
    return _record_result(
        missing,
        blocked_reasons,
        (),
        ErrorCode.IMPACT_CONTROL_RECORD_INVALID,
        "ImpactReviewTaskRequest rejected",
    )


def validate_lower_layer_request_candidate(candidate: LowerLayerRequestCandidate) -> ImpactControlValidationResult:
    if _has_forbidden_intent(candidate.__dict__):
        return _no_go("LowerLayerRequestCandidate crossed candidate-only boundary")
    missing = _missing_fields(
        candidate,
        (
            "candidate_id",
            "assessment_ref",
            "target_layer",
            "target_workspace_or_owner_path",
            "requested_capability_or_clarification",
            "constraints",
            "evidence_refs",
            "acceptance_test_hint",
            "boundary_reason",
            "status",
        ),
    )
    blocked_reasons: list[str] = []
    error_code = ErrorCode.IMPACT_CONTROL_RECORD_INVALID
    if candidate.status not in LOWER_LAYER_CANDIDATE_STATUSES:
        blocked_reasons.append(f"LowerLayerRequestCandidate status rejected: {candidate.status}")
    if candidate.target_layer not in ("layer_2", "layer_3"):
        blocked_reasons.append(f"target_layer rejected: {candidate.target_layer}")
    if candidate.status in ("approved_candidate", "sent_for_owner_review", "accepted_by_owner") and not candidate.monitor_decision_ref:
        missing = tuple(dict.fromkeys((*missing, "monitor_decision_ref")))
        blocked_reasons.append("lower-layer candidate requires Monitor/HITL decision")
        error_code = ErrorCode.MISSING_HUMAN_DECISION
    if candidate.status == "accepted_by_owner" and not candidate.owner_acceptance_ref:
        blocked_reasons.append("accepted_by_owner requires owner_acceptance_ref")
    return _record_result(missing, blocked_reasons, (), error_code, "LowerLayerRequestCandidate rejected")


def validate_lower_layer_request_outcome(outcome: LowerLayerRequestOutcome) -> ImpactControlValidationResult:
    if _has_forbidden_intent(outcome.__dict__):
        return _no_go("LowerLayerRequestOutcome cannot complete project progress or authorize dispatch")
    missing = _missing_fields(
        outcome,
        (
            "outcome_id",
            "request_candidate_ref",
            "target_layer",
            "owner_ref",
            "outcome",
            "evidence_refs",
            "expected_follow_up",
            "kernel_or_owner_record_ref",
        ),
    )
    blocked_reasons: list[str] = []
    if outcome.target_layer not in ("layer_2", "layer_3"):
        blocked_reasons.append(f"target_layer rejected: {outcome.target_layer}")
    if outcome.outcome not in LOWER_LAYER_OUTCOMES:
        blocked_reasons.append(f"LowerLayerRequestOutcome outcome rejected: {outcome.outcome}")
    if outcome.outcome == "accepted" and not outcome.accepted_scope_refs:
        blocked_reasons.append("accepted lower-layer outcome requires accepted_scope_refs")
    if outcome.outcome in ("rejected", "deferred", "needs_clarification") and not outcome.rejection_or_defer_reason:
        blocked_reasons.append(f"{outcome.outcome} lower-layer outcome requires rejection_or_defer_reason")
    return _record_result(
        missing,
        blocked_reasons,
        (),
        ErrorCode.IMPACT_CONTROL_RECORD_INVALID,
        "LowerLayerRequestOutcome rejected",
    )


def validate_scope_revision_candidate(candidate: ScopeRevisionCandidate) -> ImpactControlValidationResult:
    if _has_forbidden_intent(candidate.__dict__):
        return _no_go("ScopeRevisionCandidate cannot bypass lower-layer or no-go boundaries")
    missing = _missing_fields(
        candidate,
        (
            "revision_id",
            "impact_ref",
            "project_or_packet_refs",
            "scope_effect",
            "no_go_effect",
            "proposed_revision",
            "standardization_ref",
            "status",
        ),
    )
    blocked_reasons: list[str] = []
    error_code = ErrorCode.IMPACT_CONTROL_RECORD_INVALID
    if candidate.status not in SCOPE_REVISION_STATUSES:
        blocked_reasons.append(f"ScopeRevisionCandidate status rejected: {candidate.status}")
    if candidate.status == "approved_for_standardization_review" and not candidate.monitor_decision_ref:
        missing = tuple(dict.fromkeys((*missing, "monitor_decision_ref")))
        blocked_reasons.append("scope revision requires Monitor/HITL decision")
        error_code = ErrorCode.MISSING_HUMAN_DECISION
    return _record_result(missing, blocked_reasons, (), error_code, "ScopeRevisionCandidate rejected")


def validate_workaround_decision_request(request: WorkaroundDecisionRequest) -> ImpactControlValidationResult:
    if _has_forbidden_intent(
        {
            "workaround_option": request.workaround_option,
            "risk": request.risk,
            "expiry": request.expiry,
            "rollback_condition": request.rollback_condition,
            "evidence_requirement": request.evidence_requirement,
        }
    ):
        return _no_go("WorkaroundDecisionRequest cannot bypass Monitor/HITL or execute work")
    required = ("request_id", "impact_ref", "workaround_option", "risk", "status")
    if request.status == "approved":
        required = (
            "request_id",
            "impact_ref",
            "workaround_option",
            "risk",
            "expiry",
            "rollback_condition",
            "evidence_requirement",
            "decision_ref",
            "status",
        )
    missing = _missing_fields(request, required)
    blocked_reasons: list[str] = []
    error_code = ErrorCode.IMPACT_CONTROL_RECORD_INVALID
    if request.status not in WORKAROUND_STATUSES:
        blocked_reasons.append(f"WorkaroundDecisionRequest status rejected: {request.status}")
    if request.status == "approved" and not _has_human_decision_ref((request.decision_ref,)):
        blocked_reasons.append("approved workaround requires HumanDecision-backed decision_ref")
        error_code = ErrorCode.MISSING_HUMAN_DECISION
    return _record_result(missing, blocked_reasons, (), error_code, "WorkaroundDecisionRequest rejected")


def submit_impact_control_request_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    impact_request: ImpactControlRequest,
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="SubmitImpactControlRequest",
        actor=actor,
        authority_refs=authority_refs,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        affects_state=True,
        payload={
            "expected_kernel_version": expected_version,
            "idempotency_key": idempotency_key,
            "impact_request": dict(impact_request.__dict__),
            "projection_type": "impact-control-request",
            "source_refs": authority_refs,
        },
    )


def record_impact_assessment_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    assessment: ImpactAssessment,
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="RecordImpactAssessment",
        actor=actor,
        authority_refs=authority_refs,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        affects_state=True,
        payload={
            "assessment": dict(assessment.__dict__),
            "expected_kernel_version": expected_version,
            "idempotency_key": idempotency_key,
            "projection_type": "impact-assessment",
            "source_refs": authority_refs,
        },
    )


def create_monitor_task_for_impact_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    assessment_ref: str,
    layer_impact_detected: LayerImpactDetected,
    review_question: str,
    options: tuple[str, ...],
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="CreateMonitorTaskForImpact",
        actor=actor,
        authority_refs=authority_refs,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        affects_state=True,
        payload={
            "assessment_ref": assessment_ref,
            "expected_kernel_version": expected_version,
            "idempotency_key": idempotency_key,
            "layer_impact_detected": dict(layer_impact_detected.__dict__),
            "options": options,
            "projection_type": "impact-monitor-task-request",
            "review_question": review_question,
            "source_refs": authority_refs,
        },
    )


def record_lower_layer_request_outcome_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    outcome: LowerLayerRequestOutcome,
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="RecordLowerLayerRequestOutcome",
        actor=actor,
        authority_refs=authority_refs,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        affects_state=False,
        payload={
            "expected_version": expected_version,
            "idempotency_key": idempotency_key,
            "outcome": dict(outcome.__dict__),
            "projection_type": "impact-lower-layer-outcome",
            "source_refs": authority_refs,
        },
    )


def request_workaround_decision_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    workaround_request: WorkaroundDecisionRequest,
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="RequestWorkaroundDecision",
        actor=actor,
        authority_refs=authority_refs,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        affects_state=False,
        payload={
            "expected_version": expected_version,
            "idempotency_key": idempotency_key,
            "projection_type": "impact-workaround-decision-request",
            "source_refs": authority_refs,
            "workaround_request": dict(workaround_request.__dict__),
        },
    )


def validate_impact_control_command(command: CommandEnvelope) -> ValidationResult:
    validation = validate_command_envelope(command)
    if not validation.accepted:
        return validation
    if command.command_type not in IMPACT_CONTROL_COMMAND_TYPES:
        return ValidationResult(False, ErrorCode.IMPACT_CONTROL_COMMAND_INVALID, "unknown Impact Control command")
    if _command_has_forbidden_intent(command):
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "Impact Control command crossed Slice 007 boundary")
    for field_name in _required_payload_fields(command.command_type):
        if _payload_field_missing(command.payload, field_name):
            return ValidationResult(False, ErrorCode.IMPACT_CONTROL_COMMAND_INVALID, f"{field_name} is required")
    source_refs = command.payload["source_refs"]
    if not isinstance(source_refs, (list, tuple)) or tuple(source_refs) != tuple(command.authority_refs):
        return ValidationResult(False, ErrorCode.IMPACT_CONTROL_COMMAND_INVALID, "source_refs must match authority_refs")
    version_field = "expected_kernel_version" if command.command_type in KERNEL_RECORDED_COMMANDS else "expected_version"
    if not _is_non_negative_int(command.payload[version_field]):
        return ValidationResult(False, ErrorCode.IMPACT_CONTROL_COMMAND_INVALID, f"{version_field} must be a non-negative integer")
    if not _payload_version_matches_envelope(command, version_field):
        return ValidationResult(
            False,
            ErrorCode.IMPACT_CONTROL_COMMAND_INVALID,
            f"payload {version_field} must match envelope expected_version",
        )
    if command.payload["idempotency_key"] != command.idempotency_key:
        return ValidationResult(
            False,
            ErrorCode.IMPACT_CONTROL_COMMAND_INVALID,
            "payload idempotency_key must match envelope idempotency_key",
        )
    specific = _validate_command_specific_contract(command)
    if not specific.accepted:
        return ValidationResult(False, specific.error_code, specific.message)
    return ValidationResult(True)


def _required_payload_fields(command_type: str) -> tuple[str, ...]:
    if command_type == "SubmitImpactControlRequest":
        return ("impact_request", "source_refs", "expected_kernel_version", "idempotency_key")
    if command_type == "RecordImpactAssessment":
        return ("assessment", "source_refs", "expected_kernel_version", "idempotency_key")
    if command_type == "CreateMonitorTaskForImpact":
        return (
            "assessment_ref",
            "layer_impact_detected",
            "review_question",
            "options",
            "source_refs",
            "expected_kernel_version",
            "idempotency_key",
        )
    if command_type == "RecordLowerLayerRequestOutcome":
        return ("outcome", "source_refs", "expected_version", "idempotency_key")
    if command_type == "RequestWorkaroundDecision":
        return ("workaround_request", "source_refs", "expected_version", "idempotency_key")
    return ()


def _validate_command_specific_contract(command: CommandEnvelope) -> ImpactControlValidationResult:
    if command.command_type == "SubmitImpactControlRequest":
        return validate_impact_control_request(_coerce_dataclass(command.payload["impact_request"], ImpactControlRequest))
    if command.command_type == "RecordImpactAssessment":
        return validate_impact_assessment(_coerce_dataclass(command.payload["assessment"], ImpactAssessment))
    if command.command_type == "CreateMonitorTaskForImpact":
        impact = _coerce_dataclass(command.payload["layer_impact_detected"], LayerImpactDetected)
        impact_result = validate_layer_impact_detected(impact)
        if not impact_result.accepted:
            return impact_result
        if command.payload["assessment_ref"] != impact.assessment_ref:
            return ImpactControlValidationResult(
                False,
                ErrorCode.IMPACT_CONTROL_COMMAND_INVALID,
                message="payload assessment_ref must match LayerImpactDetected assessment_ref",
            )
        review_task = ImpactReviewTaskRequest(
            review_task_id=f"impact-review:{impact.impact_id}",
            assessment_ref=command.payload["assessment_ref"],
            layer_impact_ref=f"LayerImpactDetected:{impact.impact_id}",
            review_question=command.payload["review_question"],
            options=tuple(command.payload["options"]),
            owner_path=impact.proposed_route,
            recommended_next_action="open_monitor_review",
            blocked_state_ref=impact.assessment_ref,
            source_refs=tuple(command.payload["source_refs"]),
            status="monitor_opened",
        )
        return validate_impact_review_task_request(review_task)
    if command.command_type == "RecordLowerLayerRequestOutcome":
        return validate_lower_layer_request_outcome(_coerce_dataclass(command.payload["outcome"], LowerLayerRequestOutcome))
    if command.command_type == "RequestWorkaroundDecision":
        return validate_workaround_decision_request(
            _coerce_dataclass(command.payload["workaround_request"], WorkaroundDecisionRequest)
        )
    return ImpactControlValidationResult(True)


def _record_result(
    missing: tuple[str, ...],
    blocked_reasons: list[str],
    invalid_items: tuple[str, ...],
    error_code: ErrorCode,
    message: str,
) -> ImpactControlValidationResult:
    if missing or blocked_reasons or invalid_items:
        return ImpactControlValidationResult(
            False,
            error_code,
            message=message,
            missing_fields=tuple(dict.fromkeys(missing)),
            blocked_reasons=tuple(dict.fromkeys(blocked_reasons)),
            invalid_items=tuple(dict.fromkeys(invalid_items)),
        )
    return ImpactControlValidationResult(True, message=message.replace("rejected", "accepted"))


def _no_go(message: str) -> ImpactControlValidationResult:
    return ImpactControlValidationResult(False, ErrorCode.NO_GO_BOUNDARY, message=message)


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


def _invalid_items(values: tuple[str, ...], allowed: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(value for value in values if value not in allowed)


def _is_non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _payload_version_matches_envelope(command: CommandEnvelope, version_field: str) -> bool:
    return _is_non_negative_int(command.expected_version) and command.payload[version_field] == command.expected_version


T = TypeVar("T")


def _coerce_dataclass(value: Any, cls: type[T]) -> T:
    if isinstance(value, cls):
        return value
    if isinstance(value, dict):
        return cls(**value)
    return cls()


def _command_has_forbidden_intent(command: CommandEnvelope) -> bool:
    safe_payload_keys = {
        "assessment",
        "assessment_ref",
        "expected_kernel_version",
        "expected_version",
        "idempotency_key",
        "impact_request",
        "layer_impact_detected",
        "options",
        "outcome",
        "projection_type",
        "review_question",
        "source_refs",
        "workaround_request",
    }
    extra_payload = {key: value for key, value in command.payload.items() if key not in safe_payload_keys}
    return _has_forbidden_intent(extra_payload)


def _has_forbidden_intent(payload: Any) -> bool:
    for key, value in _iter_key_values(payload):
        normalized_key = _normalized(key)
        if normalized_key in _normalized_terms(LIVE_INTENT_KEYS) and not _payload_value_empty(value):
            return True
        if normalized_key in _normalized_terms(LIVE_INTENT_VALUE_KEYS) and _text_has_forbidden_intent(value):
            return True
    return _text_has_forbidden_intent(payload)


def _text_has_forbidden_intent(value: Any) -> bool:
    normalized_terms = _normalized_terms(FORBIDDEN_INTENT_TERMS + DIRECT_APPROVAL_TRIGGERS)
    for text in _iter_normalized_text(value):
        if text in normalized_terms:
            return True
        padded_text = f" {text} "
        for term in normalized_terms:
            if f" {term} " in padded_text:
                return True
    return False


def _iter_key_values(value: Any) -> tuple[tuple[str, Any], ...]:
    found: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            found.append((str(key), item))
            found.extend(_iter_key_values(item))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            found.extend(_iter_key_values(item))
    elif hasattr(value, "__dict__"):
        found.extend(_iter_key_values(value.__dict__))
    return tuple(found)


def _iter_normalized_text(value: Any) -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(value, str):
        found.append(_normalized(value))
    elif isinstance(value, dict):
        for key, item in value.items():
            found.extend(_iter_normalized_text(key))
            found.extend(_iter_normalized_text(item))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            found.extend(_iter_normalized_text(item))
    elif hasattr(value, "__dict__"):
        found.extend(_iter_normalized_text(value.__dict__))
    return tuple(found)


def _normalized(value: object) -> str:
    text = str(value).strip().lower()
    for token in ("_", "-", "/", "\\", ":", "."):
        text = text.replace(token, " ")
    return " ".join(text.split())


def _normalized_terms(terms: tuple[str, ...]) -> set[str]:
    return {_normalized(term) for term in terms}


def _payload_value_empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value == ""
    if isinstance(value, (dict, list, set, tuple)):
        return len(value) == 0
    return False


def _has_baseline_affecting_surface(surfaces: tuple[str, ...]) -> bool:
    return any(surface in BASELINE_AFFECTING_SURFACES for surface in surfaces)


def _has_human_decision_ref(values: tuple[str, ...]) -> bool:
    return any("human decision" in _normalized(value) or "humandecision" in str(value).lower() for value in values if value)


def _contains_direct_approval(values: tuple[str, ...]) -> bool:
    return any(_normalized(value) in _normalized_terms(DIRECT_APPROVAL_TRIGGERS) for value in values)
