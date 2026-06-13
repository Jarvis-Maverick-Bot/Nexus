from __future__ import annotations

from nexus.governance.delivery_feedback import (
    AcceptedIncrementRef,
    CompletionContinuityPacket,
    DeliveryRecord,
    FeedbackMetricExtraction,
    FeedbackMetricPolicyRef,
    FeedbackMetricTrend,
    FeedbackRecord,
    FeedbackTriageDecision,
    FeedbackTriageDecisionRequest,
    NextCycleProposal,
    create_completion_continuity_packet_command,
    create_feedback_trend_command,
    create_next_cycle_proposal_command,
    extract_feedback_metric_command,
    record_delivery_command,
    record_feedback_command,
    record_feedback_triage_decision_command,
    request_feedback_triage_decision_command,
)
from nexus.governance.schemas import ActorRef, CommandEnvelope


DELIVERY_SOURCE_REFS = (
    "solution-design/subtopics/4_21_DELIVERY_FEEDBACK_LOOP_DETAILED_DESIGN.md",
    "implementation-design/subtopics/L1_11_8_DELIVERY_FEEDBACK_LOOP_IMPLEMENTATION_DESIGN.md",
    "review-evidence/2026-06-13_NOVA_4_21_SLICE_008_TASK_PACKAGE_REVIEW.md",
    "SharedDocs:eddbe4f",
)
PROJECT_ID = "project-421"
DELIVERY_ID = "delivery-421-001"
FEEDBACK_ID = "feedback-421-001"
EXTRACTION_ID = "feedback-extraction-421-001"
TREND_ID = "feedback-trend-421-001"
TRIAGE_REQUEST_ID = "feedback-triage-request-421-001"
TRIAGE_DECISION_ID = "feedback-triage-decision-421-001"
COMPLETION_PACKET_ID = "completion-continuity-421-001"
NEXT_CYCLE_ID = "next-cycle-421-001"
HUMAN_DECISION_REF = "HumanDecision:feedback-triage-421-001"
IMPACT_ASSESSMENT_REF = "ImpactAssessment:delivery-feedback-421-001"
ACTOR = ActorRef("agent:thunder", "implementation")
REVIEWER = ActorRef("nova", "reviewer")


def valid_accepted_increment(**overrides: object) -> AcceptedIncrementRef:
    values = {
        "project_id": PROJECT_ID,
        "packet_refs": ("Layer1WorkPacket:wp-421-008",),
        "accepted_decision_ref": "HumanDecision:accepted-increment-421",
        "accepted_by_actor_ref": "Actor:nova",
        "accepted_at": "2026-06-13T08:00:00Z",
        "accepted_outputs": ("delivery feedback foundation accepted increment",),
        "evidence_refs": ("Evidence:monitor-review-421",),
        "deliverable_evaluation_result_refs": ("DeliverableEvaluationResult:421",),
        "kernel_record_ref": "krn-000301",
        "status": "accepted_increment",
    }
    values.update(overrides)
    return AcceptedIncrementRef(**values)


def valid_policy(**overrides: object) -> FeedbackMetricPolicyRef:
    values = {
        "policy_ref": "FeedbackMetricPolicy:421",
        "policy_version": 3,
        "status": "active",
        "metric_dimensions": ("usability", "defect", "workflow_fit"),
        "severity_bands": ("low", "medium", "high"),
        "frequency_bands": ("single", "repeated", "trend"),
        "confidence_rules": ("source_refs_required", "confidence_min_0.60"),
        "trend_thresholds": ("high>=2", "medium>=5"),
        "promotion_routes": ("standardization_change_candidate", "bug_candidate", "future_idea"),
        "source_refs": DELIVERY_SOURCE_REFS,
    }
    values.update(overrides)
    return FeedbackMetricPolicyRef(**values)


def valid_delivery_record(**overrides: object) -> DeliveryRecord:
    values = {
        "delivery_id": DELIVERY_ID,
        "project_id": PROJECT_ID,
        "accepted_increment_refs": ("AcceptedIncrementRef:421",),
        "accepted_decision_refs": ("HumanDecision:accepted-increment-421",),
        "evidence_refs": ("Evidence:monitor-review-421",),
        "preview_or_release_scope": "review preview only",
        "audience": "Nova review",
        "limits": "not production deploy",
        "known_limits": ("review-only", "no production readiness"),
        "delivery_note": "Slice 008 reviewable delivery record",
        "source_refs": DELIVERY_SOURCE_REFS,
        "created_by_actor": "agent:thunder",
        "status": "ready_for_review",
    }
    values.update(overrides)
    return DeliveryRecord(**values)


def valid_feedback_record(**overrides: object) -> FeedbackRecord:
    values = {
        "feedback_id": FEEDBACK_ID,
        "delivery_ref": f"DeliveryRecord:{DELIVERY_ID}",
        "project_id": PROJECT_ID,
        "source": "Nova reviewer",
        "channel": "PR review",
        "affected_increment_or_version": "AcceptedIncrementRef:421",
        "raw_feedback_ref": "FeedbackRaw:421",
        "raw_summary": "Reviewer notes repeated workflow confusion",
        "classification": "workflow_fit",
        "triage_status": "captured",
        "privacy_class": "internal",
        "received_at": "2026-06-13T08:30:00Z",
        "source_refs": DELIVERY_SOURCE_REFS,
        "created_by_actor": "agent:thunder",
        "status": "captured",
    }
    values.update(overrides)
    return FeedbackRecord(**values)


def valid_extraction(**overrides: object) -> FeedbackMetricExtraction:
    values = {
        "extraction_id": EXTRACTION_ID,
        "feedback_refs": (f"FeedbackRecord:{FEEDBACK_ID}",),
        "policy_ref": "FeedbackMetricPolicy:421",
        "policy_version": 3,
        "category": "workflow_fit",
        "severity": "medium",
        "frequency_signal": "repeated",
        "affected_user_or_workflow": "Nova review workflow",
        "requirement_or_deliverable_ref": "SuccessCriteria:workflow-review",
        "measurable_signal": "two reviewers ask for clearer review packet routing",
        "confidence": 0.82,
        "source_evidence_refs": ("FeedbackRaw:421",),
        "proposed_promotion_route": "standardization_change_candidate",
        "status": "extracted",
    }
    values.update(overrides)
    return FeedbackMetricExtraction(**values)


def valid_trend(**overrides: object) -> FeedbackMetricTrend:
    values = {
        "trend_id": TREND_ID,
        "policy_ref": "FeedbackMetricPolicy:421",
        "policy_version": 3,
        "metric_signal_refs": (f"FeedbackMetricExtraction:{EXTRACTION_ID}",),
        "aggregation_window": "2026-W24",
        "metric_values": {"workflow_fit.medium": 2},
        "count_or_frequency": "2 repeated medium signals",
        "severity_distribution": {"medium": 2},
        "threshold_status": "threshold_met",
        "affected_requirement_refs": ("SuccessCriteria:workflow-review",),
        "recommended_next_action": "open Monitor/HITL triage decision",
        "candidate_route": "standardization_change_candidate",
        "source_refs": DELIVERY_SOURCE_REFS,
        "status": "review_required",
    }
    values.update(overrides)
    return FeedbackMetricTrend(**values)


def valid_triage_request(**overrides: object) -> FeedbackTriageDecisionRequest:
    values = {
        "request_id": TRIAGE_REQUEST_ID,
        "feedback_refs": (f"FeedbackRecord:{FEEDBACK_ID}",),
        "metric_extraction_refs": (f"FeedbackMetricExtraction:{EXTRACTION_ID}",),
        "trend_refs": (f"FeedbackMetricTrend:{TREND_ID}",),
        "decision_question": "Should this feedback become a standardization change candidate?",
        "options": ("approve_change_candidate", "future_idea", "clarify", "reject"),
        "recommended_path": "approve_change_candidate",
        "scope_or_no_go_or_success_criteria_effect": "success_criteria_candidate",
        "impact_assessment_ref": IMPACT_ASSESSMENT_REF,
        "source_refs": DELIVERY_SOURCE_REFS,
        "status": "monitor_required",
    }
    values.update(overrides)
    return FeedbackTriageDecisionRequest(**values)


def valid_triage_decision(**overrides: object) -> FeedbackTriageDecision:
    values = {
        "decision_id": TRIAGE_DECISION_ID,
        "request_ref": f"FeedbackTriageDecisionRequest:{TRIAGE_REQUEST_ID}",
        "human_decision_ref": HUMAN_DECISION_REF,
        "review_task_ref": "HumanReviewTask:feedback-triage-421",
        "decision": "approve_change_candidate",
        "approved_route": "standardization_change_candidate",
        "blocked_reason": "",
        "source_refs": DELIVERY_SOURCE_REFS,
        "evidence_refs": ("Evidence:feedback-triage-421",),
        "status": "approved_candidate",
    }
    values.update(overrides)
    return FeedbackTriageDecision(**values)


def valid_completion_packet(**overrides: object) -> CompletionContinuityPacket:
    values = {
        "packet_id": COMPLETION_PACKET_ID,
        "delivery_refs": (f"DeliveryRecord:{DELIVERY_ID}",),
        "feedback_refs": (f"FeedbackRecord:{FEEDBACK_ID}",),
        "trend_refs": (f"FeedbackMetricTrend:{TREND_ID}",),
        "done_criteria_mapping": ("DoneCriteria:all accepted increments reviewed",),
        "accepted_evidence_refs": ("Evidence:monitor-review-421",),
        "open_risks": ("workflow feedback requires triage",),
        "remaining_scope": "none claimed; review required",
        "requested_decision": "review completion or continuity",
        "continuity_rule_candidate": "weekly review cadence if approved",
        "owner_ref": "Owner:Nova",
        "cadence": "weekly",
        "review_criteria": ("feedback trend reviewed", "open risks resolved"),
        "stop_conditions": ("Monitor/HITL rejects continuity",),
        "impact_assessment_ref": IMPACT_ASSESSMENT_REF,
        "human_decision_ref": "",
        "status": "monitor_required",
    }
    values.update(overrides)
    return CompletionContinuityPacket(**values)


def valid_next_cycle_proposal(**overrides: object) -> NextCycleProposal:
    values = {
        "proposal_id": NEXT_CYCLE_ID,
        "feedback_or_completion_ref": f"FeedbackTriageDecision:{TRIAGE_DECISION_ID}",
        "target_route": "standardization_change_candidate",
        "proposed_backlog_or_change": "candidate: clarify review packet routing",
        "priority_candidate": "medium",
        "impact_assessment_ref": IMPACT_ASSESSMENT_REF,
        "triage_decision_ref": f"FeedbackTriageDecision:{TRIAGE_DECISION_ID}",
        "approval_ref": HUMAN_DECISION_REF,
        "source_refs": DELIVERY_SOURCE_REFS,
        "status": "approved_candidate",
    }
    values.update(overrides)
    return NextCycleProposal(**values)


def valid_record_delivery_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": ACTOR,
        "authority_refs": DELIVERY_SOURCE_REFS,
        "delivery_record": valid_delivery_record(),
        "accepted_increment_ref": valid_accepted_increment(),
        "expected_version": 8,
        "idempotency_key": "slice008-record-delivery-421",
    }
    values.update(overrides)
    return record_delivery_command(**values)


def valid_record_feedback_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": ACTOR,
        "authority_refs": DELIVERY_SOURCE_REFS,
        "feedback_record": valid_feedback_record(),
        "expected_version": 9,
        "idempotency_key": "slice008-record-feedback-421",
    }
    values.update(overrides)
    return record_feedback_command(**values)


def valid_extract_metric_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": ACTOR,
        "authority_refs": DELIVERY_SOURCE_REFS,
        "feedback_metric_extraction": valid_extraction(),
        "feedback_record_ref": f"FeedbackRecord:{FEEDBACK_ID}",
        "metric_policy_ref": valid_policy(),
        "expected_version": 10,
        "idempotency_key": "slice008-extract-metric-421",
    }
    values.update(overrides)
    return extract_feedback_metric_command(**values)


def valid_create_trend_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": ACTOR,
        "authority_refs": DELIVERY_SOURCE_REFS,
        "feedback_metric_trend": valid_trend(),
        "extraction_refs": (f"FeedbackMetricExtraction:{EXTRACTION_ID}",),
        "metric_policy_ref": valid_policy(),
        "expected_version": 11,
        "idempotency_key": "slice008-create-trend-421",
    }
    values.update(overrides)
    return create_feedback_trend_command(**values)


def valid_triage_request_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": ACTOR,
        "authority_refs": DELIVERY_SOURCE_REFS,
        "triage_request": valid_triage_request(),
        "expected_version": 12,
        "idempotency_key": "slice008-triage-request-421",
    }
    values.update(overrides)
    return request_feedback_triage_decision_command(**values)


def valid_triage_decision_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": REVIEWER,
        "authority_refs": DELIVERY_SOURCE_REFS,
        "triage_decision": valid_triage_decision(),
        "human_decision_ref": HUMAN_DECISION_REF,
        "expected_version": 13,
        "idempotency_key": "slice008-triage-decision-421",
    }
    values.update(overrides)
    return record_feedback_triage_decision_command(**values)


def valid_completion_packet_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": ACTOR,
        "authority_refs": DELIVERY_SOURCE_REFS,
        "completion_continuity_packet": valid_completion_packet(),
        "expected_version": 14,
        "idempotency_key": "slice008-completion-packet-421",
    }
    values.update(overrides)
    return create_completion_continuity_packet_command(**values)


def valid_next_cycle_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": ACTOR,
        "authority_refs": DELIVERY_SOURCE_REFS,
        "next_cycle_proposal": valid_next_cycle_proposal(),
        "triage_decision_ref": f"FeedbackTriageDecision:{TRIAGE_DECISION_ID}",
        "expected_version": 15,
        "idempotency_key": "slice008-next-cycle-421",
    }
    values.update(overrides)
    return create_next_cycle_proposal_command(**values)
