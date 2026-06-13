from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, TypeVar

from .errors import ErrorCode
from .schemas import ActorRef, CommandEnvelope, ValidationResult, validate_command_envelope


MONITOR_HITL_COMPONENT = "Project Monitor / HITL"
MONITOR_HITL_COMMAND_TYPES: tuple[str, ...] = (
    "CreateHumanReviewTask",
    "SubmitHumanDecision",
    "EvaluateDeliverable",
    "RecordEscalation",
    "NormalizeReviewDisposition",
)
REVIEW_TASK_STATUSES: tuple[str, ...] = ("open", "waiting", "decided", "blocked", "superseded", "closed")
HUMAN_DECISION_STATUSES: tuple[str, ...] = ("proposed", "recorded", "applied", "superseded")
HUMAN_DECISION_VERDICTS: tuple[str, ...] = (
    "approve",
    "accept",
    "revise",
    "reject",
    "defer",
    "block",
    "continue",
    "workaround_allowed",
    "supersede",
)
PROFILE_STATUSES: tuple[str, ...] = ("approved", "active")
EVALUATION_STATUSES: tuple[str, ...] = ("pending", "accepted", "revise", "rejected", "blocked", "stale", "superseded")
ESCALATION_STATUSES: tuple[str, ...] = ("opened", "routed", "decided", "closed")
BASELINE_EFFECTS: tuple[str, ...] = (
    "none",
    "blocked",
    "revise_required",
    "rejected",
    "deferred",
    "superseded",
    "decision_recorded",
)
RETURN_ACTION_TYPES: tuple[str, ...] = (
    "return_for_revision",
    "return_rejected",
    "return_blocked",
    "return_deferred",
    "return_superseded",
    "return_for_evidence",
    "return_escalated",
)
DIRECT_APPROVAL_TRIGGERS: tuple[str, ...] = (
    "direct_ui_approval",
    "notification_as_decision",
    "status_card_approval",
    "chat_approval",
    "controller_approval",
)
FORBIDDEN_EFFECT_TERMS: tuple[str, ...] = (
    "final_pass",
    "final pass",
    "delivery_complete",
    "delivery complete",
    "production_ready",
    "production ready",
    "production readiness",
    "dispatch",
    "please dispatch",
    "dispatch execution",
    "perform dispatch",
    "execute dispatch",
    "runtime dispatch",
    "runtime_dispatch",
    "live dispatch",
    "actual dispatch",
    "dispatch_execute",
    "controller call",
    "controller_call",
    "controller execution",
    "controller request",
    "controller_request",
    "controller action",
    "controller_action",
    "controller invocation",
    "controller_invocation",
    "private-agent invocation",
    "private agent invocation",
    "runtime invocation",
    "runtime_invocation",
    "adapter call",
    "adapter_call",
    "transport call",
    "transport_call",
    "route activation",
    "route_activation",
    "activate route",
    "workpacket execution",
    "workpacket_execution",
    "execute workpacket",
)


@dataclass(frozen=True)
class MonitorHitlValidationResult:
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
class DeliverableEvaluationProfileRef:
    profile_id: str = ""
    profile_version: str = ""
    status: str = ""
    checklist_refs: tuple[str, ...] = ()
    constraint_refs: tuple[str, ...] = ()
    evidence_expectation_refs: tuple[str, ...] = ()
    threshold_policy_ref: str = ""
    source_refs: tuple[str, ...] = ()
    baseline_ref: str = ""


@dataclass(frozen=True)
class MonitorHitlOutputBase:
    item_id: str = ""
    item_type: str = ""
    project_id: str = ""
    workspace_id: str = ""
    source_authority_refs: tuple[str, ...] = ()
    affected_record_refs: tuple[str, ...] = ()
    status: str = ""
    owning_component: str = ""
    consumer_component_refs: tuple[str, ...] = ()
    reviewer_ref: str = ""
    decision_authority_ref: str = ""
    notes: str = ""
    created_by_component: str = MONITOR_HITL_COMPONENT
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass(frozen=True)
class HumanReviewTask(MonitorHitlOutputBase):
    review_id: str = ""
    trigger_type: str = ""
    review_type: str = ""
    target_refs: tuple[str, ...] = ()
    decision_question: str = ""
    possible_decisions: tuple[str, ...] = ()
    required_authority: str = ""
    source_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    blocked_state_ref: str = ""
    self_approval_check: str = ""
    due_or_cadence: str = ""
    recommended_next_action: str = ""


@dataclass(frozen=True)
class HumanDecision(MonitorHitlOutputBase):
    decision_id: str = ""
    review_task_ref: str = ""
    verdict: str = ""
    reason: str = ""
    conditions: tuple[str, ...] = ()
    actor_ref: str = ""
    actor_role: str = ""
    authorized_reviewer_roles: tuple[str, ...] = ()
    owner_actor_ref: str = ""
    timestamp: str = ""
    affected_records: tuple[str, ...] = ()
    kernel_record_ref: str = ""
    authority_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class DeliverableEvaluationResult(MonitorHitlOutputBase):
    result_id: str = ""
    deliverable_ref: str = ""
    evaluation_profile_ref: DeliverableEvaluationProfileRef | dict[str, Any] | None = None
    checklist_result: str = ""
    constraint_result: str = ""
    evidence_mapping_result: str = ""
    score_or_threshold_result: str = ""
    verdict: str = ""
    confidence: str = ""
    gaps: tuple[str, ...] = ()
    required_correction: str = ""
    decision_ref: str = ""


@dataclass(frozen=True)
class EscalationRecord(MonitorHitlOutputBase):
    escalation_id: str = ""
    source_task_ref: str = ""
    authority_gap: str = ""
    target_reviewer: str = ""
    reason: str = ""
    required_authority: str = ""
    decision_ref: str = ""


@dataclass(frozen=True)
class ReviewDisposition(MonitorHitlOutputBase):
    disposition_id: str = ""
    review_task_ref: str = ""
    decision_ref: str = ""
    target_work_item_ref: str = ""
    verdict: str = ""
    baseline_effect: str = ""
    return_action_ref: str = ""
    kernel_record_ref: str = ""


@dataclass(frozen=True)
class ComponentReturnAction:
    return_action_id: str = ""
    decision_ref: str = ""
    review_task_ref: str = ""
    target_component: str = ""
    target_work_item_ref: str = ""
    action_type: str = ""
    reason: str = ""
    required_correction: str = ""
    blocked_or_defer_condition: str = ""
    resume_condition: str = ""
    source_authority_refs: tuple[str, ...] = ()
    kernel_record_ref: str = ""


def validate_monitor_hitl_output_base(item: MonitorHitlOutputBase) -> MonitorHitlValidationResult:
    missing = _missing_fields(
        item,
        (
            "item_id",
            "item_type",
            "project_id",
            "workspace_id",
            "source_authority_refs",
            "affected_record_refs",
            "status",
            "owning_component",
            "consumer_component_refs",
            "reviewer_ref",
            "decision_authority_ref",
        ),
    )
    blocked_reasons: list[str] = []
    if item.created_by_component != MONITOR_HITL_COMPONENT:
        blocked_reasons.append("created_by_component must be Project Monitor / HITL")
    if item.owning_component != MONITOR_HITL_COMPONENT:
        blocked_reasons.append("owning_component must be Project Monitor / HITL")
    return _record_result(missing, blocked_reasons, ErrorCode.MONITOR_HITL_RECORD_INVALID, "Monitor/HITL output base rejected")


def validate_human_review_task(task: HumanReviewTask) -> MonitorHitlValidationResult:
    if _has_forbidden_intent(task.__dict__) or _is_forbidden_effect_status(task.status):
        return _no_go("human review task cannot approve, complete, dispatch, or execute work")
    if _normalized(task.trigger_type) in DIRECT_APPROVAL_TRIGGERS:
        return _no_go("direct UI approval or notification cannot create a HumanDecision")
    base = validate_monitor_hitl_output_base(task)
    if not base.accepted:
        return base
    missing = _missing_fields(
        task,
        (
            "review_id",
            "trigger_type",
            "review_type",
            "target_refs",
            "decision_question",
            "possible_decisions",
            "required_authority",
            "source_refs",
            "evidence_refs",
            "blocked_state_ref",
            "self_approval_check",
        ),
    )
    blocked_reasons: list[str] = []
    if task.status not in REVIEW_TASK_STATUSES:
        blocked_reasons.append(f"HumanReviewTask status rejected: {task.status}")
    if len(task.decision_question.strip()) < 12:
        blocked_reasons.append("decision_question is ambiguous")
    return _record_result(missing, blocked_reasons, ErrorCode.MONITOR_HITL_RECORD_INVALID, "HumanReviewTask rejected")


def validate_human_decision(decision: HumanDecision) -> MonitorHitlValidationResult:
    if _has_forbidden_intent(decision.__dict__) or _is_forbidden_effect_status(decision.status):
        return _no_go("human decision cannot claim completion, production readiness, dispatch, or execution")
    base = validate_monitor_hitl_output_base(decision)
    if not base.accepted:
        return base
    missing = _missing_fields(
        decision,
        (
            "decision_id",
            "review_task_ref",
            "verdict",
            "reason",
            "actor_ref",
            "actor_role",
            "authorized_reviewer_roles",
            "owner_actor_ref",
            "timestamp",
            "affected_records",
            "kernel_record_ref",
            "authority_refs",
        ),
    )
    blocked_reasons: list[str] = []
    if decision.status not in HUMAN_DECISION_STATUSES:
        blocked_reasons.append(f"HumanDecision status rejected: {decision.status}")
    if decision.verdict not in HUMAN_DECISION_VERDICTS:
        blocked_reasons.append(f"HumanDecision verdict rejected: {decision.verdict}")
    if decision.actor_role and decision.actor_role not in decision.authorized_reviewer_roles:
        blocked_reasons.append("actor role is not authorized for this decision")
    if decision.actor_ref and decision.owner_actor_ref and decision.actor_ref == decision.owner_actor_ref:
        blocked_reasons.append("decision actor cannot self-approve owned work")
    error_code = ErrorCode.MISSING_HUMAN_DECISION if missing or blocked_reasons else ErrorCode.MONITOR_HITL_RECORD_INVALID
    return _record_result(missing, blocked_reasons, error_code, "HumanDecision rejected")


def validate_deliverable_evaluation_profile_ref(profile: DeliverableEvaluationProfileRef) -> MonitorHitlValidationResult:
    missing = _missing_fields(
        profile,
        (
            "profile_id",
            "profile_version",
            "status",
            "checklist_refs",
            "constraint_refs",
            "evidence_expectation_refs",
            "threshold_policy_ref",
            "source_refs",
            "baseline_ref",
        ),
    )
    blocked_reasons: list[str] = []
    if profile.status not in PROFILE_STATUSES:
        blocked_reasons.append(f"DeliverableEvaluationProfileRef status rejected: {profile.status}")
    return _record_result(
        missing,
        blocked_reasons,
        ErrorCode.MISSING_EVALUATION_PROFILE,
        "DeliverableEvaluationProfileRef rejected",
    )


def validate_deliverable_evaluation_result(result: DeliverableEvaluationResult) -> MonitorHitlValidationResult:
    if _has_forbidden_intent(
        {
            "checklist_result": result.checklist_result,
            "constraint_result": result.constraint_result,
            "evidence_mapping_result": result.evidence_mapping_result,
            "score_or_threshold_result": result.score_or_threshold_result,
            "verdict": result.verdict,
            "confidence": result.confidence,
            "gaps": result.gaps,
            "required_correction": result.required_correction,
            "notes": result.notes,
        }
    ):
        return _no_go("deliverable evaluation cannot claim completion, production readiness, dispatch, or execution")
    base = validate_monitor_hitl_output_base(result)
    if not base.accepted:
        return base
    missing = list(
        _missing_fields(
            result,
            (
                "result_id",
                "deliverable_ref",
                "evaluation_profile_ref",
                "checklist_result",
                "constraint_result",
                "evidence_mapping_result",
                "score_or_threshold_result",
                "verdict",
                "confidence",
                "decision_ref",
            ),
        )
    )
    blocked_reasons: list[str] = []
    if result.status not in EVALUATION_STATUSES:
        blocked_reasons.append(f"DeliverableEvaluationResult status rejected: {result.status}")
    if result.verdict not in EVALUATION_STATUSES:
        blocked_reasons.append(f"DeliverableEvaluationResult verdict rejected: {result.verdict}")
    profile_result = validate_deliverable_evaluation_profile_ref(
        _coerce_dataclass(result.evaluation_profile_ref, DeliverableEvaluationProfileRef)
    )
    if not profile_result.accepted:
        blocked_reasons.extend(profile_result.blocked_reasons or profile_result.missing_fields)
    if result.status == "accepted" or result.verdict == "accepted":
        for field_name in ("checklist_result", "constraint_result", "evidence_mapping_result", "score_or_threshold_result"):
            if _payload_field_missing(result.__dict__, field_name) and field_name not in missing:
                missing.append(field_name)
    return _record_result(
        tuple(missing),
        blocked_reasons,
        ErrorCode.MISSING_EVALUATION_PROFILE if missing or blocked_reasons else ErrorCode.MONITOR_HITL_RECORD_INVALID,
        "DeliverableEvaluationResult rejected",
    )


def validate_escalation_record(escalation: EscalationRecord) -> MonitorHitlValidationResult:
    base = validate_monitor_hitl_output_base(escalation)
    if not base.accepted:
        return base
    missing = _missing_fields(
        escalation,
        (
            "escalation_id",
            "source_task_ref",
            "authority_gap",
            "target_reviewer",
            "reason",
            "affected_record_refs",
            "required_authority",
        ),
    )
    blocked_reasons: list[str] = []
    if escalation.status not in ESCALATION_STATUSES:
        blocked_reasons.append(f"EscalationRecord status rejected: {escalation.status}")
    if escalation.status in ("decided", "closed") and not escalation.decision_ref:
        missing = tuple(dict.fromkeys((*missing, "decision_ref")))
    error_code = ErrorCode.MISSING_HUMAN_DECISION if "decision_ref" in missing else ErrorCode.MONITOR_HITL_RECORD_INVALID
    return _record_result(missing, blocked_reasons, error_code, "EscalationRecord rejected")


def validate_escalation_progress_gate(escalations: tuple[EscalationRecord, ...]) -> MonitorHitlValidationResult:
    unresolved = [item.escalation_id for item in escalations if item.status in ("opened", "routed")]
    if unresolved:
        return MonitorHitlValidationResult(
            False,
            ErrorCode.NO_GO_BOUNDARY,
            message="state progress blocked by unresolved escalation",
            blocked_reasons=("unresolved escalation blocks state progress", *tuple(unresolved)),
        )
    return MonitorHitlValidationResult(True, message="no unresolved escalation")


def validate_review_disposition(disposition: ReviewDisposition) -> MonitorHitlValidationResult:
    if _has_forbidden_intent(disposition.__dict__) or _normalized(disposition.baseline_effect) in _normalized_terms(FORBIDDEN_EFFECT_TERMS):
        return _no_go("review disposition cannot claim completion, production readiness, dispatch, or execution")
    base = validate_monitor_hitl_output_base(disposition)
    if not base.accepted:
        return base
    missing = _missing_fields(
        disposition,
        (
            "disposition_id",
            "review_task_ref",
            "decision_ref",
            "target_work_item_ref",
            "verdict",
            "baseline_effect",
            "return_action_ref",
            "kernel_record_ref",
        ),
    )
    blocked_reasons: list[str] = []
    if disposition.verdict not in HUMAN_DECISION_VERDICTS:
        blocked_reasons.append(f"ReviewDisposition verdict rejected: {disposition.verdict}")
    if disposition.baseline_effect not in BASELINE_EFFECTS:
        blocked_reasons.append(f"ReviewDisposition baseline_effect rejected: {disposition.baseline_effect}")
    return _record_result(missing, blocked_reasons, ErrorCode.MONITOR_HITL_RECORD_INVALID, "ReviewDisposition rejected")


def validate_component_return_action(action: ComponentReturnAction) -> MonitorHitlValidationResult:
    if _has_forbidden_intent(action.__dict__):
        return _no_go("component return action cannot call controller/runtime or claim completion")
    missing = _missing_fields(
        action,
        (
            "return_action_id",
            "decision_ref",
            "review_task_ref",
            "target_component",
            "target_work_item_ref",
            "action_type",
            "reason",
            "source_authority_refs",
            "kernel_record_ref",
        ),
    )
    blocked_reasons: list[str] = []
    if action.action_type not in RETURN_ACTION_TYPES:
        blocked_reasons.append(f"ComponentReturnAction action_type rejected: {action.action_type}")
    if action.action_type in ("return_for_revision", "return_for_evidence") and not action.required_correction:
        blocked_reasons.append("return action requires correction details")
    if action.action_type in ("return_blocked", "return_deferred") and not action.blocked_or_defer_condition:
        blocked_reasons.append("blocked/deferred return action requires condition")
    return _record_result(missing, blocked_reasons, ErrorCode.MONITOR_HITL_RECORD_INVALID, "ComponentReturnAction rejected")


def create_human_review_task_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    review_task: HumanReviewTask,
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="CreateHumanReviewTask",
        actor=actor,
        authority_refs=authority_refs,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        affects_state=True,
        payload={
            "expected_kernel_version": expected_version,
            "idempotency_key": idempotency_key,
            "projection_type": "monitor-human-review-task",
            "review_task": dict(review_task.__dict__),
            "source_refs": authority_refs,
        },
    )


def submit_human_decision_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    review_task_ref: str,
    human_decision: HumanDecision,
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="SubmitHumanDecision",
        actor=actor,
        authority_refs=authority_refs,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        affects_state=True,
        payload={
            "expected_kernel_version": expected_version,
            "human_decision": dict(human_decision.__dict__),
            "idempotency_key": idempotency_key,
            "projection_type": "monitor-human-decision",
            "review_task_ref": review_task_ref,
            "source_refs": authority_refs,
        },
    )


def evaluate_deliverable_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    deliverable_ref: str,
    evaluation_profile_ref: DeliverableEvaluationProfileRef,
    evidence_refs: tuple[str, ...],
    evaluation_result: DeliverableEvaluationResult,
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="EvaluateDeliverable",
        actor=actor,
        authority_refs=authority_refs,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        affects_state=False,
        payload={
            "deliverable_ref": deliverable_ref,
            "evaluation_profile_ref": dict(evaluation_profile_ref.__dict__),
            "evaluation_result": dict(evaluation_result.__dict__),
            "evidence_refs": evidence_refs,
            "expected_version": expected_version,
            "idempotency_key": idempotency_key,
            "projection_type": "monitor-deliverable-evaluation",
            "source_refs": authority_refs,
        },
    )


def record_escalation_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    escalation_record: EscalationRecord,
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="RecordEscalation",
        actor=actor,
        authority_refs=authority_refs,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        affects_state=True,
        payload={
            "escalation_record": dict(escalation_record.__dict__),
            "expected_kernel_version": expected_version,
            "idempotency_key": idempotency_key,
            "projection_type": "monitor-escalation",
            "source_refs": authority_refs,
        },
    )


def normalize_review_disposition_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    review_disposition: ReviewDisposition,
    component_return_action: ComponentReturnAction,
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="NormalizeReviewDisposition",
        actor=actor,
        authority_refs=authority_refs,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        affects_state=False,
        payload={
            "component_return_action": dict(component_return_action.__dict__),
            "expected_version": expected_version,
            "idempotency_key": idempotency_key,
            "projection_type": "monitor-review-disposition",
            "review_disposition": dict(review_disposition.__dict__),
            "source_refs": authority_refs,
        },
    )


def validate_monitor_hitl_command(command: CommandEnvelope) -> ValidationResult:
    validation = validate_command_envelope(command)
    if not validation.accepted:
        return validation
    if command.command_type not in MONITOR_HITL_COMMAND_TYPES:
        return ValidationResult(False, ErrorCode.MONITOR_HITL_COMMAND_INVALID, "unknown Monitor/HITL command")
    if _command_payload_has_forbidden_intent(command):
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "Monitor/HITL command crossed Slice 006 boundary")
    for field_name in _required_payload_fields(command.command_type):
        if _payload_field_missing(command.payload, field_name):
            return ValidationResult(False, ErrorCode.MONITOR_HITL_COMMAND_INVALID, f"{field_name} is required")
    source_refs = command.payload["source_refs"]
    if not isinstance(source_refs, (list, tuple)) or tuple(source_refs) != tuple(command.authority_refs):
        return ValidationResult(False, ErrorCode.MONITOR_HITL_COMMAND_INVALID, "source_refs must match authority_refs")
    version_field = "expected_kernel_version" if command.command_type in _KERNEL_RECORDED_COMMANDS else "expected_version"
    if not _is_non_negative_int(command.payload[version_field]):
        return ValidationResult(False, ErrorCode.MONITOR_HITL_COMMAND_INVALID, f"{version_field} must be a non-negative integer")
    if not _payload_version_matches_envelope(command, version_field):
        return ValidationResult(
            False,
            ErrorCode.MONITOR_HITL_COMMAND_INVALID,
            f"payload {version_field} must match envelope expected_version",
        )
    if command.payload["idempotency_key"] != command.idempotency_key:
        return ValidationResult(
            False,
            ErrorCode.MONITOR_HITL_COMMAND_INVALID,
            "payload idempotency_key must match envelope idempotency_key",
        )
    specific = _validate_command_specific_contract(command)
    if not specific.accepted:
        return ValidationResult(False, specific.error_code, specific.message)
    return ValidationResult(True)


_KERNEL_RECORDED_COMMANDS: tuple[str, ...] = ("CreateHumanReviewTask", "SubmitHumanDecision", "RecordEscalation")


def _required_payload_fields(command_type: str) -> tuple[str, ...]:
    if command_type == "CreateHumanReviewTask":
        return ("review_task", "source_refs", "expected_kernel_version", "idempotency_key")
    if command_type == "SubmitHumanDecision":
        return ("review_task_ref", "human_decision", "source_refs", "expected_kernel_version", "idempotency_key")
    if command_type == "EvaluateDeliverable":
        return (
            "deliverable_ref",
            "evaluation_profile_ref",
            "evidence_refs",
            "evaluation_result",
            "source_refs",
            "expected_version",
            "idempotency_key",
        )
    if command_type == "RecordEscalation":
        return ("escalation_record", "source_refs", "expected_kernel_version", "idempotency_key")
    if command_type == "NormalizeReviewDisposition":
        return (
            "review_disposition",
            "component_return_action",
            "source_refs",
            "expected_version",
            "idempotency_key",
        )
    return ()


def _validate_command_specific_contract(command: CommandEnvelope) -> MonitorHitlValidationResult:
    if command.command_type == "CreateHumanReviewTask":
        return validate_human_review_task(_coerce_dataclass(command.payload["review_task"], HumanReviewTask))
    if command.command_type == "SubmitHumanDecision":
        decision = _coerce_dataclass(command.payload["human_decision"], HumanDecision)
        if command.payload["review_task_ref"] != decision.review_task_ref:
            return MonitorHitlValidationResult(
                False,
                ErrorCode.MONITOR_HITL_COMMAND_INVALID,
                message="payload review_task_ref must match HumanDecision review_task_ref",
            )
        return validate_human_decision(decision)
    if command.command_type == "EvaluateDeliverable":
        profile = _coerce_dataclass(command.payload["evaluation_profile_ref"], DeliverableEvaluationProfileRef)
        profile_result = validate_deliverable_evaluation_profile_ref(profile)
        if not profile_result.accepted:
            return profile_result
        result = _coerce_dataclass(command.payload["evaluation_result"], DeliverableEvaluationResult)
        if command.payload["deliverable_ref"] != result.deliverable_ref:
            return MonitorHitlValidationResult(
                False,
                ErrorCode.MONITOR_HITL_COMMAND_INVALID,
                message="payload deliverable_ref must match DeliverableEvaluationResult deliverable_ref",
            )
        return validate_deliverable_evaluation_result(result)
    if command.command_type == "RecordEscalation":
        return validate_escalation_record(_coerce_dataclass(command.payload["escalation_record"], EscalationRecord))
    if command.command_type == "NormalizeReviewDisposition":
        disposition = validate_review_disposition(_coerce_dataclass(command.payload["review_disposition"], ReviewDisposition))
        if not disposition.accepted:
            return disposition
        return validate_component_return_action(_coerce_dataclass(command.payload["component_return_action"], ComponentReturnAction))
    return MonitorHitlValidationResult(True)


def _command_payload_has_forbidden_intent(command: CommandEnvelope) -> bool:
    safe_payload_keys = {
        "review_task",
        "review_task_ref",
        "human_decision",
        "deliverable_ref",
        "evaluation_profile_ref",
        "evidence_refs",
        "evaluation_result",
        "escalation_record",
        "review_disposition",
        "component_return_action",
        "source_refs",
        "expected_version",
        "expected_kernel_version",
        "idempotency_key",
        "projection_type",
    }
    extra_payload = {key: value for key, value in command.payload.items() if key not in safe_payload_keys}
    return _has_forbidden_intent(extra_payload)


def _record_result(
    missing: tuple[str, ...],
    blocked_reasons: list[str],
    error_code: ErrorCode,
    message: str,
) -> MonitorHitlValidationResult:
    if missing or blocked_reasons:
        return MonitorHitlValidationResult(
            False,
            error_code,
            message=message,
            missing_fields=missing,
            blocked_reasons=tuple(dict.fromkeys(blocked_reasons)),
        )
    return MonitorHitlValidationResult(True, message=message.replace("rejected", "accepted"))


def _no_go(message: str) -> MonitorHitlValidationResult:
    return MonitorHitlValidationResult(False, ErrorCode.NO_GO_BOUNDARY, message=message)


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


def _has_forbidden_intent(payload: Any) -> bool:
    normalized_terms = _normalized_terms(FORBIDDEN_EFFECT_TERMS + DIRECT_APPROVAL_TRIGGERS)
    for text in _iter_normalized_text(payload):
        if text in normalized_terms:
            return True
        padded_text = f"_{text}_"
        for term in normalized_terms:
            if "_" not in term:
                continue
            if f"_{term}_" in padded_text:
                return True
    return False


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
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def _normalized_terms(terms: tuple[str, ...]) -> set[str]:
    return {_normalized(term) for term in terms}


def _is_forbidden_effect_status(status: str) -> bool:
    return _normalized(status) in _normalized_terms(
        (
            "approved",
            "accepted",
            "complete",
            "final_pass",
            "production_ready",
            "delivery_complete",
            "dispatch_execute",
        )
    )
