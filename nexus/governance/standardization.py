from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .errors import ErrorCode
from .schemas import ActorRef, CommandEnvelope, ValidationResult, validate_command_envelope


STANDARDIZATION_COMPONENT = "Project Standardization"
STANDARDIZATION_COMMAND_TYPES: tuple[str, ...] = (
    "SubmitStandardizationDraft",
    "CreateApprovalPacket",
    "SupersedePlanCandidate",
)
ALLOWED_STANDARDIZATION_STATUSES: tuple[str, ...] = (
    "draft",
    "review",
    "submitted",
    "approved",
    "revise",
    "revised",
    "deferred",
    "blocked",
    "superseded",
)
OPEN_AMBIGUITY_STATUSES: tuple[str, ...] = ("open", "unresolved")
SELF_APPROVAL_DECISIONS: tuple[str, ...] = (
    "approved",
    "accepted",
    "final_pass",
    "complete",
    "execute",
    "dispatch",
    "baseline_approved",
)


@dataclass(frozen=True)
class StandardizationValidationResult:
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
class ProjectStandardizationOutputBase:
    item_id: str = ""
    item_type: str = ""
    project_id: str = ""
    workspace_id: str = ""
    source_authority_refs: tuple[str, ...] = ()
    workspace_manifest_ref: str = ""
    source_refs: tuple[str, ...] = ()
    status: str = ""
    owning_component: str = ""
    consumer_component_refs: tuple[str, ...] = ()
    version: int = 1
    supersedes: tuple[str, ...] = ()
    notes: str = ""
    created_by_component: str = STANDARDIZATION_COMPONENT
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass(frozen=True)
class PlanningInputPackage(ProjectStandardizationOutputBase):
    workspace_init_refs: tuple[str, ...] = ()
    raw_input_refs: tuple[str, ...] = ()
    feedback_refs: tuple[str, ...] = ()
    constraint_refs: tuple[str, ...] = ()
    authority_refs: tuple[str, ...] = ()
    intake_summary: str = ""


@dataclass(frozen=True)
class NormalizedInputMap(ProjectStandardizationOutputBase):
    facts: tuple[str, ...] = ()
    asks: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()


@dataclass(frozen=True)
class AmbiguityItem:
    ambiguity_id: str
    severity: str
    owner: str
    required_decision: str
    status: str
    resolution_ref: str = ""


@dataclass(frozen=True)
class AmbiguityRegister(ProjectStandardizationOutputBase):
    ambiguity_items: tuple[AmbiguityItem, ...] = ()


@dataclass(frozen=True)
class ProjectVision(ProjectStandardizationOutputBase):
    problem_statement: str = ""
    target_user: str = ""
    value_statement: str = ""
    desired_outcome: str = ""
    strategic_fit: str = ""
    non_goal_summary: str = ""


@dataclass(frozen=True)
class ProjectScopeNoGo(ProjectStandardizationOutputBase):
    in_scope: tuple[str, ...] = ()
    out_of_scope: tuple[str, ...] = ()
    no_go: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    boundary_refs: tuple[str, ...] = ()
    change_trigger: str = ""


@dataclass(frozen=True)
class RequirementsSuccessCriteria(ProjectStandardizationOutputBase):
    requirements: tuple[str, ...] = ()
    success_metrics: tuple[str, ...] = ()
    acceptance_signals: tuple[str, ...] = ()
    evidence_expectations: tuple[str, ...] = ()
    measurement_method: str = ""


@dataclass(frozen=True)
class DeliverableEvaluationProfile(ProjectStandardizationOutputBase):
    deliverable_type: str = ""
    applicable_work_items: tuple[str, ...] = ()
    quality_dimensions: tuple[str, ...] = ()
    review_checklist: tuple[str, ...] = ()
    llm_review_constraints: tuple[str, ...] = ()
    required_evidence: tuple[str, ...] = ()
    measurement_method: str = ""
    pass_threshold: float | int | bool | None = None
    revise_threshold: float | int | bool | None = None
    block_conditions: tuple[str, ...] = ()
    reviewer_authority_ref: str = ""
    escalation_conditions: tuple[str, ...] = ()


@dataclass(frozen=True)
class FeedbackMetricPolicy(ProjectStandardizationOutputBase):
    categories: tuple[str, ...] = ()
    severity_scale: tuple[str, ...] = ()
    confidence_rules: tuple[str, ...] = ()
    frequency_window: str = ""
    promotion_thresholds: dict[str, int] = field(default_factory=dict)
    triage_owner: str = ""


@dataclass(frozen=True)
class EvidenceExpectationMap(ProjectStandardizationOutputBase):
    criteria_to_evidence_map: dict[str, tuple[str, ...]] = field(default_factory=dict)
    required_evidence_types: tuple[str, ...] = ()
    review_owner: str = ""
    acceptance_signal_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExecutionPlanCandidate(ProjectStandardizationOutputBase):
    plan_id: str = ""
    vision_ref: str = ""
    scope_ref: str = ""
    criteria_ref: str = ""
    risk_ref: str = ""
    dependency_ref: str = ""
    milestone_ref: str = ""
    backlog_wbs_ref: str = ""
    evidence_map_ref: str = ""
    approval_packet_ref: str = ""
    material_deliverable_types: tuple[str, ...] = ()
    profile_refs: tuple[str, ...] = ()
    feedback_metric_policy_ref: str = ""
    ambiguity_register_ref: str = ""


@dataclass(frozen=True)
class ApprovalPacket(ProjectStandardizationOutputBase):
    packet_id: str = ""
    plan_ref: str = ""
    requested_decision: str = ""
    open_questions: tuple[str, ...] = ()
    recommendation: str = ""
    evidence_refs: tuple[str, ...] = ()
    reviewer_refs: tuple[str, ...] = ()
    decision_result_ref: str = ""


@dataclass(frozen=True)
class PlanBaselineEntryResult(ProjectStandardizationOutputBase):
    result_id: str = ""
    kernel_record_ref: str = ""
    plan_ref: str = ""
    decision_ref: str = ""
    from_state: str = ""
    to_state: str = ""
    blocked_reason_if_any: str = ""


def validate_standardization_output_base(item: ProjectStandardizationOutputBase) -> StandardizationValidationResult:
    missing = _missing_fields(
        item,
        (
            "item_id",
            "item_type",
            "project_id",
            "workspace_id",
            "source_authority_refs",
            "workspace_manifest_ref",
            "source_refs",
            "status",
            "owning_component",
            "consumer_component_refs",
            "version",
        ),
    )
    blocked_reasons: list[str] = []
    if item.created_by_component != STANDARDIZATION_COMPONENT:
        blocked_reasons.append("created_by_component must be Project Standardization")
    if item.status and item.status not in ALLOWED_STANDARDIZATION_STATUSES:
        blocked_reasons.append(f"invalid standardization status: {item.status}")
    if not _is_positive_int(item.version):
        blocked_reasons.append("version must be a positive integer")
    if missing or blocked_reasons:
        return StandardizationValidationResult(
            False,
            ErrorCode.STANDARDIZATION_RECORD_INVALID,
            message="standardization output base rejected",
            missing_fields=missing,
            blocked_reasons=tuple(blocked_reasons),
        )
    return StandardizationValidationResult(True, message="standardization output base accepted")


def validate_scope_no_go(item: ProjectScopeNoGo) -> StandardizationValidationResult:
    base = validate_standardization_output_base(item)
    if not base.accepted:
        return base
    missing = _missing_fields(item, ("in_scope", "out_of_scope", "no_go", "constraints", "boundary_refs", "change_trigger"))
    blocked_reasons: list[str] = []
    if not item.in_scope or not item.no_go:
        blocked_reasons.append("scope and no-go must be paired")
    return _record_result(missing, blocked_reasons)


def validate_ambiguity_register(item: AmbiguityRegister) -> StandardizationValidationResult:
    base = validate_standardization_output_base(item)
    if not base.accepted:
        return base
    missing = _missing_fields(item, ("ambiguity_items",))
    blocked_reasons: list[str] = []
    for ambiguity in item.ambiguity_items:
        if (
            ambiguity.severity == "critical"
            and ambiguity.status in OPEN_AMBIGUITY_STATUSES
            and not ambiguity.resolution_ref
        ):
            blocked_reasons.append(f"critical ambiguity remains open: {ambiguity.ambiguity_id}")
    return _record_result(missing, blocked_reasons)


def validate_deliverable_evaluation_profile(item: DeliverableEvaluationProfile) -> StandardizationValidationResult:
    base = validate_standardization_output_base(item)
    if not base.accepted:
        return base
    missing = list(
        _missing_fields(
            item,
            (
                "deliverable_type",
                "applicable_work_items",
                "quality_dimensions",
                "review_checklist",
                "llm_review_constraints",
                "required_evidence",
                "measurement_method",
                "pass_threshold",
                "revise_threshold",
                "block_conditions",
                "reviewer_authority_ref",
                "escalation_conditions",
            ),
        )
    )
    for threshold_field in ("pass_threshold", "revise_threshold"):
        if threshold_field not in missing and not _is_valid_threshold(getattr(item, threshold_field)):
            missing.append(threshold_field)
    if missing:
        return StandardizationValidationResult(
            False,
            ErrorCode.MISSING_EVALUATION_PROFILE,
            message="deliverable evaluation profile rejected",
            missing_fields=tuple(missing),
        )
    return StandardizationValidationResult(True, message="deliverable evaluation profile accepted")


def validate_feedback_metric_policy(item: FeedbackMetricPolicy) -> StandardizationValidationResult:
    base = validate_standardization_output_base(item)
    if not base.accepted:
        return base
    missing = _missing_fields(
        item,
        (
            "categories",
            "severity_scale",
            "confidence_rules",
            "frequency_window",
            "promotion_thresholds",
            "triage_owner",
        ),
    )
    return _record_result(missing, [])


def validate_execution_plan_candidate(item: ExecutionPlanCandidate) -> StandardizationValidationResult:
    base = validate_standardization_output_base(item)
    if not base.accepted:
        return base
    missing = _missing_fields(
        item,
        (
            "plan_id",
            "vision_ref",
            "scope_ref",
            "criteria_ref",
            "risk_ref",
            "dependency_ref",
            "milestone_ref",
            "backlog_wbs_ref",
            "evidence_map_ref",
            "approval_packet_ref",
            "ambiguity_register_ref",
        ),
    )
    blocked_reasons: list[str] = []
    if item.status == "approved":
        blocked_reasons.append("approved plan candidates require HumanDecision and Kernel baseline-entry evidence")
        return StandardizationValidationResult(
            False,
            ErrorCode.MISSING_HUMAN_DECISION,
            message="execution plan candidate cannot approve itself",
            missing_fields=missing,
            blocked_reasons=tuple(blocked_reasons),
        )
    return _record_result(missing, blocked_reasons)


def validate_standardization_bundle(
    *,
    plan: ExecutionPlanCandidate,
    profiles: tuple[DeliverableEvaluationProfile, ...],
    feedback_policy: FeedbackMetricPolicy | None,
    feedback_driven_change: bool = False,
) -> StandardizationValidationResult:
    plan_result = validate_execution_plan_candidate(plan)
    if not plan_result.accepted:
        return plan_result

    profile_types = {profile.deliverable_type for profile in profiles if profile.deliverable_type}
    blocked_reasons: list[str] = []
    for deliverable_type in plan.material_deliverable_types:
        if deliverable_type not in profile_types:
            blocked_reasons.append(f"material deliverable lacks evaluation profile: {deliverable_type}")
    if blocked_reasons:
        return StandardizationValidationResult(
            False,
            ErrorCode.MISSING_EVALUATION_PROFILE,
            message="standardization bundle rejected",
            blocked_reasons=tuple(blocked_reasons),
        )

    if feedback_driven_change and (feedback_policy is None or not plan.feedback_metric_policy_ref):
        return StandardizationValidationResult(
            False,
            ErrorCode.RAW_FEEDBACK_NO_AUTHORITY_MUTATION,
            message="standardization bundle rejected",
            blocked_reasons=("feedback-driven planning change requires FeedbackMetricPolicy",),
        )
    if feedback_policy is not None:
        policy_result = validate_feedback_metric_policy(feedback_policy)
        if not policy_result.accepted:
            return policy_result
    return StandardizationValidationResult(True, message="standardization bundle accepted")


def submit_standardization_draft_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    project_id: str,
    workspace_id: str,
    workspace_manifest_ref: str,
    planning_input_ref: str,
    normalized_input_ref: str,
    criteria_ref: str,
    profile_refs: tuple[str, ...],
    feedback_metric_policy_ref: str,
    ambiguity_register_ref: str,
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="SubmitStandardizationDraft",
        actor=actor,
        authority_refs=authority_refs,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        affects_state=False,
        payload={
            "ambiguity_register_ref": ambiguity_register_ref,
            "criteria_ref": criteria_ref,
            "expected_version": expected_version,
            "feedback_metric_policy_ref": feedback_metric_policy_ref,
            "idempotency_key": idempotency_key,
            "normalized_input_ref": normalized_input_ref,
            "planning_input_ref": planning_input_ref,
            "profile_refs": profile_refs,
            "project_id": project_id,
            "source_refs": authority_refs,
            "workspace_id": workspace_id,
            "workspace_manifest_ref": workspace_manifest_ref,
            "projection_type": "standardization-draft",
        },
    )


def create_approval_packet_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    project_id: str,
    workspace_id: str,
    plan_ref: str,
    requested_decision: str,
    open_questions: tuple[str, ...],
    evidence_refs: tuple[str, ...],
    reviewer_refs: tuple[str, ...],
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="CreateApprovalPacket",
        actor=actor,
        authority_refs=authority_refs,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        affects_state=False,
        payload={
            "evidence_refs": evidence_refs,
            "expected_version": expected_version,
            "idempotency_key": idempotency_key,
            "open_questions": open_questions,
            "plan_ref": plan_ref,
            "project_id": project_id,
            "projection_type": "standardization-approval-packet",
            "requested_decision": requested_decision,
            "reviewer_refs": reviewer_refs,
            "source_refs": authority_refs,
            "workspace_id": workspace_id,
        },
    )


def supersede_plan_candidate_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    project_id: str,
    prior_plan_ref: str,
    revised_plan_payload: dict[str, Any],
    supersede_reason: str,
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="SupersedePlanCandidate",
        actor=actor,
        authority_refs=authority_refs,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        affects_state=False,
        payload={
            "expected_version": expected_version,
            "idempotency_key": idempotency_key,
            "prior_plan_ref": prior_plan_ref,
            "project_id": project_id,
            "projection_type": "standardization-supersede-plan",
            "revised_plan_payload": revised_plan_payload,
            "source_refs": authority_refs,
            "supersede_reason": supersede_reason,
        },
    )


def validate_standardization_command(command: CommandEnvelope) -> ValidationResult:
    validation = validate_command_envelope(command)
    if not validation.accepted:
        return validation
    if command.command_type not in STANDARDIZATION_COMMAND_TYPES:
        return ValidationResult(False, ErrorCode.STANDARDIZATION_COMMAND_INVALID, "unknown Standardization command")
    for field_name in _required_payload_fields(command.command_type):
        if _payload_field_missing(command.payload, field_name):
            return ValidationResult(False, ErrorCode.STANDARDIZATION_COMMAND_INVALID, f"{field_name} is required")
    source_refs = command.payload["source_refs"]
    if not isinstance(source_refs, (list, tuple)) or tuple(source_refs) != tuple(command.authority_refs):
        return ValidationResult(
            False,
            ErrorCode.STANDARDIZATION_COMMAND_INVALID,
            "source_refs must match authority_refs",
        )
    if not _is_non_negative_int(command.payload["expected_version"]):
        return ValidationResult(
            False,
            ErrorCode.STANDARDIZATION_COMMAND_INVALID,
            "expected_version must be a non-negative integer",
        )
    if not _payload_version_matches_envelope(command):
        return ValidationResult(
            False,
            ErrorCode.STANDARDIZATION_COMMAND_INVALID,
            "payload expected_version must match envelope expected_version",
        )
    if command.payload["idempotency_key"] != command.idempotency_key:
        return ValidationResult(
            False,
            ErrorCode.STANDARDIZATION_COMMAND_INVALID,
            "payload idempotency_key must match envelope idempotency_key",
        )
    if command.command_type == "CreateApprovalPacket" and _is_self_approval(command.payload["requested_decision"]):
        return ValidationResult(False, ErrorCode.MISSING_HUMAN_DECISION, "approval packet cannot approve itself")
    if command.command_type == "CreateApprovalPacket" and command.payload.get("decision_result_ref"):
        return ValidationResult(
            False,
            ErrorCode.MISSING_HUMAN_DECISION,
            "approval packet cannot include decision_result_ref",
        )
    return ValidationResult(True)


def _required_payload_fields(command_type: str) -> tuple[str, ...]:
    if command_type == "SubmitStandardizationDraft":
        return (
            "project_id",
            "workspace_id",
            "workspace_manifest_ref",
            "planning_input_ref",
            "normalized_input_ref",
            "criteria_ref",
            "profile_refs",
            "feedback_metric_policy_ref",
            "ambiguity_register_ref",
            "source_refs",
            "expected_version",
            "idempotency_key",
        )
    if command_type == "CreateApprovalPacket":
        return (
            "project_id",
            "workspace_id",
            "plan_ref",
            "requested_decision",
            "open_questions",
            "evidence_refs",
            "reviewer_refs",
            "source_refs",
            "expected_version",
            "idempotency_key",
        )
    if command_type == "SupersedePlanCandidate":
        return (
            "project_id",
            "prior_plan_ref",
            "revised_plan_payload",
            "supersede_reason",
            "source_refs",
            "expected_version",
            "idempotency_key",
        )
    return ()


def _record_result(missing: tuple[str, ...], blocked_reasons: list[str]) -> StandardizationValidationResult:
    if missing or blocked_reasons:
        return StandardizationValidationResult(
            False,
            ErrorCode.STANDARDIZATION_RECORD_INVALID,
            message="standardization record rejected",
            missing_fields=missing,
            blocked_reasons=tuple(blocked_reasons),
        )
    return StandardizationValidationResult(True, message="standardization record accepted")


def _missing_fields(item: object, field_names: tuple[str, ...]) -> tuple[str, ...]:
    missing: list[str] = []
    for field_name in field_names:
        if _payload_field_missing(item.__dict__, field_name):
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


def _is_valid_threshold(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1


def _is_self_approval(requested_decision: object) -> bool:
    normalized = str(requested_decision).strip().lower()
    return normalized in SELF_APPROVAL_DECISIONS
