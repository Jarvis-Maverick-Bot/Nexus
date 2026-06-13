from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, TypeVar

from .errors import ErrorCode
from .schemas import ActorRef, CommandEnvelope, ValidationResult, validate_command_envelope


DELIVERY_FEEDBACK_COMMAND_TYPES: tuple[str, ...] = (
    "RecordDelivery",
    "RecordFeedback",
    "ExtractFeedbackMetric",
    "CreateFeedbackTrend",
    "RequestFeedbackTriageDecision",
    "RecordFeedbackTriageDecision",
    "CreateCompletionContinuityPacket",
    "CreateNextCycleProposal",
)

DELIVERY_FEEDBACK_KERNEL_RECORDED_COMMANDS: tuple[str, ...] = (
    "RecordDelivery",
    "RequestFeedbackTriageDecision",
    "RecordFeedbackTriageDecision",
    "CreateCompletionContinuityPacket",
)

ACCEPTED_INCREMENT_STATUSES = ("accepted_increment", "accepted_with_limits", "superseded")
DELIVERY_STATUSES = (
    "draft",
    "ready_for_review",
    "delivered_preview",
    "delivered_release_candidate",
    "feedback_open",
    "superseded",
    "closed",
)
FEEDBACK_STATUSES = (
    "captured",
    "classified",
    "metric_extracted",
    "triage_requested",
    "triaged",
    "clarify",
    "rejected",
    "deferred",
    "superseded",
    "closed",
)
POLICY_STATUSES = ("approved", "active")
EXTRACTION_STATUSES = ("draft", "extracted", "review", "approved_signal", "rejected_signal", "clarify", "superseded")
TREND_STATUSES = ("draft", "threshold_not_met", "threshold_met", "review_required", "approved_for_triage", "rejected", "superseded")
THRESHOLD_STATUSES = ("threshold_not_met", "threshold_met", "review_required")
TRIAGE_REQUEST_STATUSES = ("proposed", "monitor_required", "impact_preflight_required", "blocked", "superseded")
TRIAGE_DECISION_STATUSES = ("approved_candidate", "rejected", "deferred", "blocked", "superseded")
TRIAGE_DECISIONS = (
    "approve_change_candidate",
    "approve_bug_candidate",
    "approve_backlog_candidate",
    "approve_success_criteria_update_candidate",
    "future_idea",
    "clarify",
    "reject",
    "defer",
    "block",
)
COMPLETION_PACKET_STATUSES = ("draft", "submitted", "monitor_required", "revise", "blocked", "superseded")
NEXT_CYCLE_ROUTES = (
    "standardization_change_candidate",
    "execution_packet_candidate",
    "bug_candidate",
    "future_idea",
    "reject",
    "clarify",
    "defer",
    "blocked",
)
NEXT_CYCLE_STATUSES = ("draft", "review", "approved_candidate", "rejected", "deferred", "blocked", "superseded")

RAW_MUTATION_TERMS = (
    "raw_feedback_direct_mutation",
    "mutate backlog",
    "mutate_backlog",
    "update backlog",
    "update_backlog",
    "update scope",
    "update_scope",
    "update success criteria",
    "update_success_criteria",
    "direct backlog mutation",
    "direct scope mutation",
    "direct success criteria mutation",
    "direct no go mutation",
    "direct no-go mutation",
    "direct priority mutation",
    "direct packet mutation",
    "update no go",
    "update no-go",
    "mutate no go",
    "mutate no-go",
    "change no go",
    "change no-go",
    "update priority",
    "mutate priority",
    "set priority",
    "update packet",
    "mutate packet",
    "create packet",
    "approve packet",
    "create requirement",
    "create_requirement",
    "approve requirement",
    "approve_requirement",
    "approve completion",
    "approve_completion",
    "production ready",
    "production_ready",
    "production readiness",
)

COMPLETION_DECISION_TERMS = (
    "complete",
    "approve completion",
    "approve_completion",
    "approved complete",
    "activate continuity",
    "activate_continuity",
    "continuity activation",
    "completion claim",
    "completion_claim",
    "complete project",
    "complete_project",
    "close project",
    "closed complete",
    "delivery complete",
    "delivery_complete",
    "delivery completed",
    "mark complete",
    "mark completed",
    "continuity active",
    "continuity_active",
)

FORBIDDEN_EFFECT_TERMS = (
    "production readiness",
    "production_ready",
    "release to production",
    "release_to_production",
    "deploy to production",
    "deploy_to_production",
    "deployed",
    "deploy",
    "final pass",
    "final_pass",
    "accepted project",
    "project accepted",
    "mark complete",
    "mark completed",
    "delivery completed",
    "dispatch now",
    "execute dispatch",
    "perform dispatch",
    "dispatch execution",
    "dispatch_execution",
    "actual dispatch",
    "actual_dispatch",
    "controller call",
    "controller_call",
    "call controller",
    "controller execution",
    "controller request",
    "controller action",
    "execute controller",
    "direct controller call",
    "direct_controller_call",
    "owner path call",
    "owner_path_call",
    "call owner path",
    "owner path request",
    "request owner path",
    "owner path execution",
    "owner path action",
    "adapter call",
    "adapter_call",
    "adapter execution",
    "transport call",
    "transport_call",
    "route activation",
    "route_activation",
    "route request",
    "activate route",
    "activate_route",
    "workpacket execution",
    "workpacket_execution",
    "work packet execution",
    "execute workpacket",
    "execute_workpacket",
    "execute work packet",
    "runtime invocation",
    "runtime_invocation",
    "runtime live invocation",
    "live invocation",
    "private agent invocation",
    "private_agent_invocation",
    "private-agent invocation",
)

IMPACT_SENSITIVE_ROUTES = ("standardization_change_candidate", "execution_packet_candidate", "bug_candidate")

T = TypeVar("T")


@dataclass(frozen=True)
class DeliveryFeedbackValidationResult:
    accepted: bool
    error_code: ErrorCode | None = None
    missing_fields: tuple[str, ...] = ()
    blocked_reasons: tuple[str, ...] = ()
    message: str = ""

    def to_evidence(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "blocked_reasons": list(self.blocked_reasons),
            "error_code": self.error_code.value if self.error_code else None,
            "message": self.message,
            "missing_fields": list(self.missing_fields),
        }


@dataclass(frozen=True)
class AcceptedIncrementRef:
    project_id: str
    packet_refs: tuple[str, ...]
    accepted_decision_ref: str
    accepted_by_actor_ref: str
    accepted_at: str
    accepted_outputs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    deliverable_evaluation_result_refs: tuple[str, ...]
    kernel_record_ref: str
    status: str


@dataclass(frozen=True)
class FeedbackMetricPolicyRef:
    policy_ref: str
    policy_version: int
    status: str
    metric_dimensions: tuple[str, ...]
    severity_bands: tuple[str, ...]
    frequency_bands: tuple[str, ...]
    confidence_rules: tuple[str, ...]
    trend_thresholds: tuple[str, ...]
    promotion_routes: tuple[str, ...]
    source_refs: tuple[str, ...]


@dataclass(frozen=True)
class DeliveryRecord:
    delivery_id: str
    project_id: str
    accepted_increment_refs: tuple[str, ...]
    accepted_decision_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    preview_or_release_scope: str
    audience: str
    limits: str
    known_limits: tuple[str, ...]
    delivery_note: str
    source_refs: tuple[str, ...]
    created_by_actor: str
    status: str


@dataclass(frozen=True)
class FeedbackRecord:
    feedback_id: str
    delivery_ref: str
    project_id: str
    source: str
    channel: str
    affected_increment_or_version: str
    raw_feedback_ref: str
    raw_summary: str
    classification: str
    triage_status: str
    privacy_class: str
    received_at: str
    source_refs: tuple[str, ...]
    created_by_actor: str
    status: str


@dataclass(frozen=True)
class FeedbackMetricExtraction:
    extraction_id: str
    feedback_refs: tuple[str, ...]
    policy_ref: str
    policy_version: int
    category: str
    severity: str
    frequency_signal: str
    affected_user_or_workflow: str
    requirement_or_deliverable_ref: str
    measurable_signal: str
    confidence: float
    source_evidence_refs: tuple[str, ...]
    proposed_promotion_route: str
    status: str


@dataclass(frozen=True)
class FeedbackMetricTrend:
    trend_id: str
    policy_ref: str
    policy_version: int
    metric_signal_refs: tuple[str, ...]
    aggregation_window: str
    metric_values: dict[str, Any]
    count_or_frequency: str
    severity_distribution: dict[str, Any]
    threshold_status: str
    affected_requirement_refs: tuple[str, ...]
    recommended_next_action: str
    candidate_route: str
    source_refs: tuple[str, ...]
    status: str


@dataclass(frozen=True)
class FeedbackTriageDecisionRequest:
    request_id: str
    feedback_refs: tuple[str, ...]
    metric_extraction_refs: tuple[str, ...]
    trend_refs: tuple[str, ...]
    decision_question: str
    options: tuple[str, ...]
    recommended_path: str
    scope_or_no_go_or_success_criteria_effect: str
    impact_assessment_ref: str
    source_refs: tuple[str, ...]
    status: str


@dataclass(frozen=True)
class FeedbackTriageDecision:
    decision_id: str
    request_ref: str
    human_decision_ref: str
    review_task_ref: str
    decision: str
    approved_route: str
    blocked_reason: str
    source_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    status: str


@dataclass(frozen=True)
class CompletionContinuityPacket:
    packet_id: str
    delivery_refs: tuple[str, ...]
    feedback_refs: tuple[str, ...]
    trend_refs: tuple[str, ...]
    done_criteria_mapping: tuple[str, ...]
    accepted_evidence_refs: tuple[str, ...]
    open_risks: tuple[str, ...]
    remaining_scope: str
    requested_decision: str
    continuity_rule_candidate: str
    owner_ref: str
    cadence: str
    review_criteria: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    impact_assessment_ref: str
    human_decision_ref: str
    status: str


@dataclass(frozen=True)
class NextCycleProposal:
    proposal_id: str
    feedback_or_completion_ref: str
    target_route: str
    proposed_backlog_or_change: str
    priority_candidate: str
    impact_assessment_ref: str
    triage_decision_ref: str
    approval_ref: str
    source_refs: tuple[str, ...]
    status: str


def validate_accepted_increment_ref(item: AcceptedIncrementRef) -> DeliveryFeedbackValidationResult:
    missing = _missing_fields(
        item,
        (
            "project_id",
            "packet_refs",
            "accepted_decision_ref",
            "accepted_by_actor_ref",
            "accepted_at",
            "accepted_outputs",
            "evidence_refs",
            "deliverable_evaluation_result_refs",
            "kernel_record_ref",
            "status",
        ),
    )
    blocked: list[str] = []
    error = ErrorCode.DELIVERY_FEEDBACK_RECORD_INVALID
    if item.status not in ACCEPTED_INCREMENT_STATUSES:
        blocked.append(f"AcceptedIncrementRef status rejected: {item.status}")
        error = ErrorCode.NO_GO_BOUNDARY
    return _record_result(missing, blocked, error, "AcceptedIncrementRef rejected")


def validate_feedback_metric_policy_ref(policy: FeedbackMetricPolicyRef) -> DeliveryFeedbackValidationResult:
    missing = _missing_fields(
        policy,
        (
            "policy_ref",
            "policy_version",
            "status",
            "metric_dimensions",
            "severity_bands",
            "frequency_bands",
            "confidence_rules",
            "trend_thresholds",
            "promotion_routes",
            "source_refs",
        ),
    )
    blocked: list[str] = []
    if not _is_non_negative_int(policy.policy_version):
        missing = tuple(dict.fromkeys((*missing, "policy_version")))
    if policy.status not in POLICY_STATUSES:
        blocked.append(f"FeedbackMetricPolicyRef status rejected: {policy.status}")
    return _record_result(missing, blocked, ErrorCode.DELIVERY_FEEDBACK_RECORD_INVALID, "FeedbackMetricPolicyRef rejected")


def validate_delivery_record(
    record: DeliveryRecord,
    accepted_increment_ref: AcceptedIncrementRef | dict[str, Any],
) -> DeliveryFeedbackValidationResult:
    increment = _coerce_dataclass(accepted_increment_ref, AcceptedIncrementRef)
    increment_result = validate_accepted_increment_ref(increment)
    if not increment_result.accepted:
        return increment_result
    missing = _missing_fields(
        record,
        (
            "delivery_id",
            "project_id",
            "accepted_increment_refs",
            "accepted_decision_refs",
            "evidence_refs",
            "preview_or_release_scope",
            "audience",
            "limits",
            "known_limits",
            "delivery_note",
            "source_refs",
            "created_by_actor",
            "status",
        ),
    )
    blocked: list[str] = []
    error = ErrorCode.DELIVERY_FEEDBACK_RECORD_INVALID
    if record.status not in DELIVERY_STATUSES or _has_forbidden_effect(record.status):
        blocked.append(f"DeliveryRecord status rejected: {record.status}")
        error = ErrorCode.NO_GO_BOUNDARY
    if _has_forbidden_effect((record.preview_or_release_scope, record.delivery_note)):
        blocked.append("DeliveryRecord cannot imply deploy, production readiness, completion, or final PASS")
        error = ErrorCode.NO_GO_BOUNDARY
    return _record_result(missing, blocked, error, "DeliveryRecord rejected")


def validate_feedback_record(record: FeedbackRecord) -> DeliveryFeedbackValidationResult:
    missing = _missing_fields(
        record,
        (
            "feedback_id",
            "delivery_ref",
            "project_id",
            "source",
            "channel",
            "affected_increment_or_version",
            "raw_feedback_ref",
            "raw_summary",
            "classification",
            "triage_status",
            "privacy_class",
            "received_at",
            "source_refs",
            "created_by_actor",
            "status",
        ),
    )
    blocked: list[str] = []
    error = ErrorCode.DELIVERY_FEEDBACK_RECORD_INVALID
    if record.status not in FEEDBACK_STATUSES:
        blocked.append(f"FeedbackRecord status rejected: {record.status}")
    if _has_raw_mutation(record.raw_summary):
        blocked.append("raw feedback cannot mutate backlog, scope, success criteria, requirements, or completion")
        error = ErrorCode.RAW_FEEDBACK_NO_AUTHORITY_MUTATION
    elif _has_forbidden_effect(record.raw_summary):
        blocked.append("FeedbackRecord crossed runtime, dispatch, controller, production, or final-pass boundary")
        error = ErrorCode.NO_GO_BOUNDARY
    return _record_result(missing, blocked, error, "FeedbackRecord rejected")


def validate_feedback_metric_extraction(
    extraction: FeedbackMetricExtraction,
    metric_policy_ref: FeedbackMetricPolicyRef | dict[str, Any],
) -> DeliveryFeedbackValidationResult:
    policy = _coerce_dataclass(metric_policy_ref, FeedbackMetricPolicyRef)
    policy_result = validate_feedback_metric_policy_ref(policy)
    if not policy_result.accepted:
        return policy_result
    missing = _missing_fields(
        extraction,
        (
            "extraction_id",
            "feedback_refs",
            "policy_ref",
            "policy_version",
            "category",
            "severity",
            "frequency_signal",
            "affected_user_or_workflow",
            "requirement_or_deliverable_ref",
            "measurable_signal",
            "source_evidence_refs",
            "proposed_promotion_route",
            "status",
        ),
    )
    blocked: list[str] = []
    error = ErrorCode.DELIVERY_FEEDBACK_RECORD_INVALID
    if extraction.policy_ref != policy.policy_ref or extraction.policy_version != policy.policy_version:
        blocked.append("FeedbackMetricExtraction policy ref/version must match FeedbackMetricPolicyRef")
    if extraction.status not in EXTRACTION_STATUSES:
        blocked.append(f"FeedbackMetricExtraction status rejected: {extraction.status}")
    if not isinstance(extraction.confidence, (int, float)) or isinstance(extraction.confidence, bool) or not (0.0 <= float(extraction.confidence) <= 1.0):
        blocked.append("confidence must be between 0.0 and 1.0")
    if extraction.status == "approved_signal" and isinstance(extraction.confidence, (int, float)) and float(extraction.confidence) < 0.6:
        blocked.append("approved_signal requires confidence >= 0.60")
    if _has_raw_mutation(extraction.proposed_promotion_route):
        blocked.append("metric extraction route cannot directly mutate planning artifacts")
        error = ErrorCode.RAW_FEEDBACK_NO_AUTHORITY_MUTATION
    elif _has_forbidden_effect(extraction.proposed_promotion_route):
        blocked.append("metric extraction route crossed no-go boundary")
        error = ErrorCode.NO_GO_BOUNDARY
    return _record_result(missing, blocked, error, "FeedbackMetricExtraction rejected")


def validate_feedback_metric_trend(
    trend: FeedbackMetricTrend,
    metric_policy_ref: FeedbackMetricPolicyRef | dict[str, Any],
) -> DeliveryFeedbackValidationResult:
    policy = _coerce_dataclass(metric_policy_ref, FeedbackMetricPolicyRef)
    policy_result = validate_feedback_metric_policy_ref(policy)
    if not policy_result.accepted:
        return policy_result
    missing = _missing_fields(
        trend,
        (
            "trend_id",
            "policy_ref",
            "policy_version",
            "metric_signal_refs",
            "aggregation_window",
            "metric_values",
            "count_or_frequency",
            "severity_distribution",
            "threshold_status",
            "affected_requirement_refs",
            "recommended_next_action",
            "candidate_route",
            "source_refs",
            "status",
        ),
    )
    blocked: list[str] = []
    error = ErrorCode.DELIVERY_FEEDBACK_RECORD_INVALID
    if trend.policy_ref != policy.policy_ref or trend.policy_version != policy.policy_version:
        blocked.append("FeedbackMetricTrend policy ref/version must match FeedbackMetricPolicyRef")
    if trend.status not in TREND_STATUSES:
        blocked.append(f"FeedbackMetricTrend status rejected: {trend.status}")
    if trend.threshold_status not in THRESHOLD_STATUSES:
        blocked.append(f"threshold_status rejected: {trend.threshold_status}")
    if trend.threshold_status == "threshold_met" and trend.status not in ("review_required", "approved_for_triage"):
        blocked.append("threshold_met trends require Monitor/HITL triage route")
        error = ErrorCode.MISSING_HUMAN_DECISION
    if _has_raw_mutation((trend.recommended_next_action, trend.candidate_route)):
        blocked.append("trend cannot directly mutate planning artifacts")
        error = ErrorCode.RAW_FEEDBACK_NO_AUTHORITY_MUTATION
    elif _has_forbidden_effect((trend.recommended_next_action, trend.candidate_route)):
        blocked.append("trend crossed no-go boundary")
        error = ErrorCode.NO_GO_BOUNDARY
    return _record_result(missing, blocked, error, "FeedbackMetricTrend rejected")


def validate_feedback_triage_decision_request(request: FeedbackTriageDecisionRequest) -> DeliveryFeedbackValidationResult:
    missing = _missing_fields(
        request,
        (
            "request_id",
            "feedback_refs",
            "metric_extraction_refs",
            "trend_refs",
            "decision_question",
            "options",
            "recommended_path",
            "scope_or_no_go_or_success_criteria_effect",
            "source_refs",
            "status",
        ),
    )
    blocked: list[str] = []
    error = ErrorCode.DELIVERY_FEEDBACK_RECORD_INVALID
    if request.status not in TRIAGE_REQUEST_STATUSES:
        blocked.append(f"FeedbackTriageDecisionRequest status rejected: {request.status}")
    if _has_forbidden_effect((request.options, request.recommended_path, request.decision_question)):
        blocked.append("triage options cannot dispatch, deploy, execute, complete, or claim final PASS")
        error = ErrorCode.NO_GO_BOUNDARY
    elif _has_raw_mutation((request.options, request.recommended_path)):
        blocked.append("triage options cannot directly mutate planning artifacts")
        error = ErrorCode.RAW_FEEDBACK_NO_AUTHORITY_MUTATION
    if _effect_requires_impact(request.scope_or_no_go_or_success_criteria_effect) and not request.impact_assessment_ref:
        blocked.append("impact_assessment_ref is required before material feedback propagation")
        error = ErrorCode.IMPACT_CONTROL_RECORD_INVALID
    return _record_result(missing, blocked, error, "FeedbackTriageDecisionRequest rejected")


def validate_feedback_triage_decision(decision: FeedbackTriageDecision) -> DeliveryFeedbackValidationResult:
    missing = _missing_fields(
        decision,
        (
            "decision_id",
            "request_ref",
            "human_decision_ref",
            "review_task_ref",
            "decision",
            "approved_route",
            "source_refs",
            "evidence_refs",
            "status",
        ),
    )
    blocked: list[str] = []
    error = ErrorCode.DELIVERY_FEEDBACK_RECORD_INVALID
    if not _has_human_decision_ref((decision.human_decision_ref,)):
        blocked.append("FeedbackTriageDecision requires HumanDecision-backed decision")
        error = ErrorCode.MISSING_HUMAN_DECISION
    if decision.status not in TRIAGE_DECISION_STATUSES:
        blocked.append(f"FeedbackTriageDecision status rejected: {decision.status}")
    if decision.decision not in TRIAGE_DECISIONS:
        blocked.append(f"FeedbackTriageDecision decision rejected: {decision.decision}")
    if decision.approved_route not in NEXT_CYCLE_ROUTES:
        if _has_raw_mutation(decision.approved_route):
            blocked.append("triage decision cannot directly mutate planning artifacts")
            error = ErrorCode.RAW_FEEDBACK_NO_AUTHORITY_MUTATION
        else:
            blocked.append(f"approved_route rejected: {decision.approved_route}")
    if _has_forbidden_effect((decision.decision, decision.approved_route, decision.blocked_reason)):
        blocked.append("triage decision crossed no-go boundary")
        error = ErrorCode.NO_GO_BOUNDARY
    return _record_result(missing, blocked, error, "FeedbackTriageDecision rejected")


def validate_completion_continuity_packet(packet: CompletionContinuityPacket) -> DeliveryFeedbackValidationResult:
    missing = _missing_fields(
        packet,
        (
            "packet_id",
            "delivery_refs",
            "feedback_refs",
            "trend_refs",
            "done_criteria_mapping",
            "accepted_evidence_refs",
            "open_risks",
            "remaining_scope",
            "requested_decision",
            "continuity_rule_candidate",
            "owner_ref",
            "cadence",
            "review_criteria",
            "stop_conditions",
            "status",
        ),
    )
    blocked: list[str] = []
    error = ErrorCode.DELIVERY_FEEDBACK_RECORD_INVALID
    if packet.status not in COMPLETION_PACKET_STATUSES or _has_forbidden_effect(packet.status):
        blocked.append(f"CompletionContinuityPacket status rejected: {packet.status}")
        error = ErrorCode.NO_GO_BOUNDARY
    if not packet.impact_assessment_ref:
        blocked.append("impact_assessment_ref is required before completion/continuity review propagation")
        error = ErrorCode.IMPACT_CONTROL_RECORD_INVALID
    if _has_completion_decision(packet.requested_decision):
        if not _has_human_decision_ref((packet.human_decision_ref,)):
            blocked.append("completion/continuity outcome requires HumanDecision")
            error = ErrorCode.MISSING_HUMAN_DECISION
        else:
            blocked.append("Slice 008 cannot accept completion decisions or continuity activation outcomes")
            error = ErrorCode.NO_GO_BOUNDARY
    if _has_forbidden_effect(packet.requested_decision):
        blocked.append("completion packet cannot claim deploy, production readiness, or final PASS")
        error = ErrorCode.NO_GO_BOUNDARY
    return _record_result(missing, blocked, error, "CompletionContinuityPacket rejected")


def validate_next_cycle_proposal(proposal: NextCycleProposal) -> DeliveryFeedbackValidationResult:
    missing = _missing_fields(
        proposal,
        (
            "proposal_id",
            "feedback_or_completion_ref",
            "target_route",
            "proposed_backlog_or_change",
            "priority_candidate",
            "triage_decision_ref",
            "approval_ref",
            "source_refs",
            "status",
        ),
    )
    blocked: list[str] = []
    error = ErrorCode.DELIVERY_FEEDBACK_RECORD_INVALID
    if proposal.status not in NEXT_CYCLE_STATUSES:
        blocked.append(f"NextCycleProposal status rejected: {proposal.status}")
    if proposal.target_route not in NEXT_CYCLE_ROUTES:
        if _has_forbidden_effect(proposal.target_route):
            blocked.append("NextCycleProposal route crossed no-go boundary")
            error = ErrorCode.NO_GO_BOUNDARY
        elif _has_raw_mutation(proposal.target_route):
            blocked.append("NextCycleProposal route cannot directly mutate planning artifacts")
            error = ErrorCode.RAW_FEEDBACK_NO_AUTHORITY_MUTATION
        else:
            blocked.append(f"target_route rejected: {proposal.target_route}")
    if proposal.target_route in IMPACT_SENSITIVE_ROUTES and not proposal.impact_assessment_ref:
        blocked.append("impact_assessment_ref is required before next-cycle propagation")
        error = ErrorCode.IMPACT_CONTROL_RECORD_INVALID
    if proposal.status == "approved_candidate" and not _has_human_decision_ref((proposal.approval_ref,)):
        blocked.append("approved_candidate requires HumanDecision-backed approval_ref")
        error = ErrorCode.MISSING_HUMAN_DECISION
    if _has_raw_mutation(proposal.proposed_backlog_or_change):
        blocked.append("NextCycleProposal cannot directly mutate backlog, scope, requirements, or criteria")
        error = ErrorCode.RAW_FEEDBACK_NO_AUTHORITY_MUTATION
    if _has_forbidden_effect(proposal.proposed_backlog_or_change):
        blocked.append("NextCycleProposal crossed no-go boundary")
        error = ErrorCode.NO_GO_BOUNDARY
    return _record_result(missing, blocked, error, "NextCycleProposal rejected")


def record_delivery_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    delivery_record: DeliveryRecord,
    accepted_increment_ref: AcceptedIncrementRef,
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return _state_command(
        "RecordDelivery",
        actor,
        authority_refs,
        expected_version,
        idempotency_key,
        delivery_record=dict(delivery_record.__dict__),
        accepted_increment_ref=dict(accepted_increment_ref.__dict__),
        projection_type="delivery-record",
    )


def record_feedback_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    feedback_record: FeedbackRecord,
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return _state_command(
        "RecordFeedback",
        actor,
        authority_refs,
        expected_version,
        idempotency_key,
        version_payload_field="expected_version",
        feedback_record=dict(feedback_record.__dict__),
        projection_type="feedback-record",
    )


def extract_feedback_metric_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    feedback_metric_extraction: FeedbackMetricExtraction,
    feedback_record_ref: str,
    metric_policy_ref: FeedbackMetricPolicyRef,
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return _projection_command(
        "ExtractFeedbackMetric",
        actor,
        authority_refs,
        expected_version,
        idempotency_key,
        feedback_metric_extraction=dict(feedback_metric_extraction.__dict__),
        feedback_record_ref=feedback_record_ref,
        metric_policy_ref=dict(metric_policy_ref.__dict__),
        projection_type="feedback-metric-extraction",
    )


def create_feedback_trend_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    feedback_metric_trend: FeedbackMetricTrend,
    extraction_refs: tuple[str, ...],
    metric_policy_ref: FeedbackMetricPolicyRef,
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return _projection_command(
        "CreateFeedbackTrend",
        actor,
        authority_refs,
        expected_version,
        idempotency_key,
        feedback_metric_trend=dict(feedback_metric_trend.__dict__),
        extraction_refs=extraction_refs,
        metric_policy_ref=dict(metric_policy_ref.__dict__),
        projection_type="feedback-metric-trend",
    )


def request_feedback_triage_decision_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    triage_request: FeedbackTriageDecisionRequest,
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return _state_command(
        "RequestFeedbackTriageDecision",
        actor,
        authority_refs,
        expected_version,
        idempotency_key,
        triage_request=dict(triage_request.__dict__),
        projection_type="feedback-triage-request",
    )


def record_feedback_triage_decision_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    triage_decision: FeedbackTriageDecision,
    human_decision_ref: str,
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return _state_command(
        "RecordFeedbackTriageDecision",
        actor,
        authority_refs,
        expected_version,
        idempotency_key,
        human_decision_ref=human_decision_ref,
        triage_decision=dict(triage_decision.__dict__),
        projection_type="feedback-triage-decision",
    )


def create_completion_continuity_packet_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    completion_continuity_packet: CompletionContinuityPacket,
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return _state_command(
        "CreateCompletionContinuityPacket",
        actor,
        authority_refs,
        expected_version,
        idempotency_key,
        completion_continuity_packet=dict(completion_continuity_packet.__dict__),
        projection_type="completion-continuity-packet",
    )


def create_next_cycle_proposal_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    next_cycle_proposal: NextCycleProposal,
    triage_decision_ref: str,
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return _projection_command(
        "CreateNextCycleProposal",
        actor,
        authority_refs,
        expected_version,
        idempotency_key,
        next_cycle_proposal=dict(next_cycle_proposal.__dict__),
        triage_decision_ref=triage_decision_ref,
        projection_type="next-cycle-proposal",
    )


def validate_delivery_feedback_command(command: CommandEnvelope) -> ValidationResult:
    validation = validate_command_envelope(command)
    if not validation.accepted:
        return validation
    if command.command_type not in DELIVERY_FEEDBACK_COMMAND_TYPES:
        return ValidationResult(False, ErrorCode.DELIVERY_FEEDBACK_COMMAND_INVALID, "unknown Delivery Feedback command")
    if _command_has_forbidden_intent(command):
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "Delivery Feedback command crossed Slice 008 boundary")
    for field_name in _required_payload_fields(command.command_type):
        if _payload_field_missing(command.payload, field_name):
            return ValidationResult(False, ErrorCode.DELIVERY_FEEDBACK_COMMAND_INVALID, f"{field_name} is required")
    source_refs = command.payload["source_refs"]
    if not isinstance(source_refs, (list, tuple)) or tuple(source_refs) != tuple(command.authority_refs):
        return ValidationResult(False, ErrorCode.DELIVERY_FEEDBACK_COMMAND_INVALID, "source_refs must match authority_refs")
    version_field = "expected_kernel_version" if command.command_type in DELIVERY_FEEDBACK_KERNEL_RECORDED_COMMANDS else "expected_version"
    if not _is_non_negative_int(command.payload[version_field]):
        return ValidationResult(False, ErrorCode.DELIVERY_FEEDBACK_COMMAND_INVALID, f"{version_field} must be a non-negative integer")
    if not _payload_version_matches_envelope(command, version_field):
        return ValidationResult(
            False,
            ErrorCode.DELIVERY_FEEDBACK_COMMAND_INVALID,
            f"payload {version_field} must match envelope expected_version",
        )
    if command.payload["idempotency_key"] != command.idempotency_key:
        return ValidationResult(False, ErrorCode.DELIVERY_FEEDBACK_COMMAND_INVALID, "payload idempotency_key must match envelope idempotency_key")
    specific = _validate_command_specific_contract(command)
    if not specific.accepted:
        return ValidationResult(False, specific.error_code, specific.message)
    return ValidationResult(True)


def _state_command(
    command_type: str,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    expected_version: int,
    idempotency_key: str,
    version_payload_field: str = "expected_kernel_version",
    **payload: Any,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type=command_type,
        actor=actor,
        authority_refs=authority_refs,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        affects_state=True,
        payload={
            **payload,
            version_payload_field: expected_version,
            "idempotency_key": idempotency_key,
            "source_refs": authority_refs,
        },
    )


def _projection_command(
    command_type: str,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    expected_version: int,
    idempotency_key: str,
    **payload: Any,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type=command_type,
        actor=actor,
        authority_refs=authority_refs,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        affects_state=False,
        payload={
            **payload,
            "expected_version": expected_version,
            "idempotency_key": idempotency_key,
            "source_refs": authority_refs,
        },
    )


def _required_payload_fields(command_type: str) -> tuple[str, ...]:
    if command_type == "RecordDelivery":
        return ("delivery_record", "accepted_increment_ref", "source_refs", "expected_kernel_version", "idempotency_key")
    if command_type == "RecordFeedback":
        return ("feedback_record", "source_refs", "expected_version", "idempotency_key")
    if command_type == "ExtractFeedbackMetric":
        return ("feedback_metric_extraction", "feedback_record_ref", "metric_policy_ref", "source_refs", "expected_version", "idempotency_key")
    if command_type == "CreateFeedbackTrend":
        return ("feedback_metric_trend", "extraction_refs", "metric_policy_ref", "source_refs", "expected_version", "idempotency_key")
    if command_type == "RequestFeedbackTriageDecision":
        return ("triage_request", "source_refs", "expected_kernel_version", "idempotency_key")
    if command_type == "RecordFeedbackTriageDecision":
        return ("triage_decision", "human_decision_ref", "source_refs", "expected_kernel_version", "idempotency_key")
    if command_type == "CreateCompletionContinuityPacket":
        return ("completion_continuity_packet", "source_refs", "expected_kernel_version", "idempotency_key")
    if command_type == "CreateNextCycleProposal":
        return ("next_cycle_proposal", "triage_decision_ref", "source_refs", "expected_version", "idempotency_key")
    return ()


def _validate_command_specific_contract(command: CommandEnvelope) -> DeliveryFeedbackValidationResult:
    if command.command_type == "RecordDelivery":
        return validate_delivery_record(
            _coerce_dataclass(command.payload["delivery_record"], DeliveryRecord),
            _coerce_dataclass(command.payload["accepted_increment_ref"], AcceptedIncrementRef),
        )
    if command.command_type == "RecordFeedback":
        return validate_feedback_record(_coerce_dataclass(command.payload["feedback_record"], FeedbackRecord))
    if command.command_type == "ExtractFeedbackMetric":
        return validate_feedback_metric_extraction(
            _coerce_dataclass(command.payload["feedback_metric_extraction"], FeedbackMetricExtraction),
            _coerce_dataclass(command.payload["metric_policy_ref"], FeedbackMetricPolicyRef),
        )
    if command.command_type == "CreateFeedbackTrend":
        return validate_feedback_metric_trend(
            _coerce_dataclass(command.payload["feedback_metric_trend"], FeedbackMetricTrend),
            _coerce_dataclass(command.payload["metric_policy_ref"], FeedbackMetricPolicyRef),
        )
    if command.command_type == "RequestFeedbackTriageDecision":
        return validate_feedback_triage_decision_request(_coerce_dataclass(command.payload["triage_request"], FeedbackTriageDecisionRequest))
    if command.command_type == "RecordFeedbackTriageDecision":
        decision = _coerce_dataclass(command.payload["triage_decision"], FeedbackTriageDecision)
        if command.payload["human_decision_ref"] != decision.human_decision_ref:
            return DeliveryFeedbackValidationResult(
                False,
                ErrorCode.DELIVERY_FEEDBACK_COMMAND_INVALID,
                message="payload human_decision_ref must match FeedbackTriageDecision human_decision_ref",
            )
        return validate_feedback_triage_decision(decision)
    if command.command_type == "CreateCompletionContinuityPacket":
        return validate_completion_continuity_packet(_coerce_dataclass(command.payload["completion_continuity_packet"], CompletionContinuityPacket))
    if command.command_type == "CreateNextCycleProposal":
        proposal = _coerce_dataclass(command.payload["next_cycle_proposal"], NextCycleProposal)
        if command.payload["triage_decision_ref"] != proposal.triage_decision_ref:
            return DeliveryFeedbackValidationResult(
                False,
                ErrorCode.DELIVERY_FEEDBACK_COMMAND_INVALID,
                message="payload triage_decision_ref must match NextCycleProposal triage_decision_ref",
            )
        return validate_next_cycle_proposal(proposal)
    return DeliveryFeedbackValidationResult(True)


def _record_result(
    missing: tuple[str, ...],
    blocked_reasons: list[str],
    error_code: ErrorCode,
    message: str,
) -> DeliveryFeedbackValidationResult:
    if missing or blocked_reasons:
        return DeliveryFeedbackValidationResult(False, error_code, missing, tuple(blocked_reasons), message)
    return DeliveryFeedbackValidationResult(True)


def _missing_fields(item: object, field_names: tuple[str, ...]) -> tuple[str, ...]:
    missing: list[str] = []
    for field_name in field_names:
        value = getattr(item, field_name)
        if _payload_value_empty(value):
            missing.append(field_name)
    return tuple(missing)


def _payload_field_missing(payload: dict[str, Any], field_name: str) -> bool:
    return field_name not in payload or _payload_value_empty(payload[field_name])


def _is_non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _payload_version_matches_envelope(command: CommandEnvelope, version_field: str) -> bool:
    return command.payload[version_field] == command.expected_version


def _coerce_dataclass(value: Any, cls: type[T]) -> T:
    if isinstance(value, cls):
        return value
    if isinstance(value, dict):
        return cls(**value)
    return value


def _command_has_forbidden_intent(command: CommandEnvelope) -> bool:
    return _has_forbidden_effect(command.payload) or _has_raw_mutation(command.payload)


def _effect_requires_impact(effect: str) -> bool:
    normalized = _normalized(effect)
    return any(term in normalized for term in ("scope", "no go", "success criteria", "requirement", "backlog", "packet"))


def _has_human_decision_ref(values: tuple[str, ...]) -> bool:
    return any("humandecision:" in str(value).lower() or "human decision" in _normalized(value) for value in values if value)


def _has_raw_mutation(value: Any) -> bool:
    return _text_has_terms(value, RAW_MUTATION_TERMS)


def _has_completion_decision(value: Any) -> bool:
    return _text_has_terms(value, COMPLETION_DECISION_TERMS)


def _has_forbidden_effect(value: Any) -> bool:
    return _text_has_terms(value, FORBIDDEN_EFFECT_TERMS)


def _text_has_terms(value: Any, terms: tuple[str, ...]) -> bool:
    normalized_terms = {_normalized(term) for term in terms}
    for text in _iter_normalized_text(value):
        for term in normalized_terms:
            if _term_in_text(text, term) and not _is_negated_limit(text, term):
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
    text = str(value).strip().lower().replace("_", " ").replace("-", " ")
    return " ".join(text.split())


def _term_in_text(text: str, term: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
    return re.search(pattern, text) is not None


def _is_negated_limit(text: str, term: str) -> bool:
    if term in {"deploy", "deploy to production", "production readiness", "production ready", "production"}:
        return any(phrase in text for phrase in ("not production", "no production", "not deploy", "no deploy", "not a deploy"))
    return False


def _payload_value_empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value == "":
        return True
    if isinstance(value, (tuple, list, set, dict)) and not value:
        return True
    return False
