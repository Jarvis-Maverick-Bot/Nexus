from __future__ import annotations

from nexus.governance.monitor_hitl import (
    ComponentReturnAction,
    DeliverableEvaluationProfileRef,
    DeliverableEvaluationResult,
    EscalationRecord,
    HumanDecision,
    HumanReviewTask,
    ReviewDisposition,
    create_human_review_task_command,
    evaluate_deliverable_command,
    normalize_review_disposition_command,
    record_escalation_command,
    submit_human_decision_command,
)
from nexus.governance.schemas import ActorRef, CommandEnvelope


MONITOR_SOURCE_REFS = (
    "solution-design/subtopics/4_21_PROJECT_MONITOR_HITL_DETAILED_DESIGN.md",
    "implementation-design/subtopics/L1_11_6_PROJECT_MONITOR_HITL_IMPLEMENTATION_DESIGN.md",
    "review-evidence/2026-06-13_NOVA_4_21_SLICE_006_TASK_PACKAGE_REVIEW.md",
    "SharedDocs:b3d3f67",
)
PROJECT_ID = "project-421"
WORKSPACE_ID = "workspace-421"
REVIEW_ID = "review-421-001"
DECISION_ID = "decision-421-001"
EVALUATION_ID = "evaluation-421-001"
ESCALATION_ID = "escalation-421-001"
KERNEL_REVIEW_RECORD_REF = "krn-monitor-review-000001"
KERNEL_DECISION_RECORD_REF = "krn-monitor-decision-000002"
ACTOR = ActorRef("agent:thunder", "implementation")
REVIEWER = ActorRef("nova", "reviewer")


def monitor_base_values(item_type: str, status: str = "open") -> dict[str, object]:
    return {
        "item_id": f"{item_type.lower()}-421",
        "item_type": item_type,
        "project_id": PROJECT_ID,
        "workspace_id": WORKSPACE_ID,
        "source_authority_refs": MONITOR_SOURCE_REFS,
        "affected_record_refs": ("dispatch:return-candidate-421",),
        "status": status,
        "owning_component": "Project Monitor / HITL",
        "consumer_component_refs": ("Governance Kernel", "Project Execution", "Dispatch Contract"),
        "reviewer_ref": "nova",
        "decision_authority_ref": "alex",
        "notes": "slice 006 fixture",
    }


def valid_review_task(**overrides: object) -> HumanReviewTask:
    values = {
        **monitor_base_values("HumanReviewTask", status="open"),
        "review_id": REVIEW_ID,
        "trigger_type": "dispatch_return_candidate",
        "review_type": "deliverable_evaluation",
        "target_refs": ("deliverable:ux-v0.2-cs-client",),
        "decision_question": "Should this deliverable be accepted under the approved evaluation profile?",
        "possible_decisions": ("accept", "revise", "reject", "block"),
        "required_authority": "reviewer:nova",
        "source_refs": MONITOR_SOURCE_REFS,
        "evidence_refs": ("evidence:render-check", "evidence:test-output"),
        "blocked_state_ref": "dispatch:return-candidate-421",
        "self_approval_check": "reviewer_not_owner",
        "due_or_cadence": "manual-review",
        "recommended_next_action": "evaluate against profile",
    }
    values.update(overrides)
    return HumanReviewTask(**values)


def valid_human_decision(**overrides: object) -> HumanDecision:
    values = {
        **monitor_base_values("HumanDecision", status="recorded"),
        "decision_id": DECISION_ID,
        "review_task_ref": f"HumanReviewTask:{REVIEW_ID}",
        "verdict": "revise",
        "reason": "render evidence has one missing required screenshot",
        "conditions": ("add missing render evidence",),
        "actor_ref": "nova",
        "actor_role": "reviewer",
        "authorized_reviewer_roles": ("reviewer", "decision_authority"),
        "owner_actor_ref": "agent:thunder",
        "timestamp": "2026-06-13T09:15:00Z",
        "affected_records": ("deliverable:ux-v0.2-cs-client",),
        "kernel_record_ref": KERNEL_DECISION_RECORD_REF,
        "authority_refs": MONITOR_SOURCE_REFS,
    }
    values.update(overrides)
    return HumanDecision(**values)


def valid_profile_ref(**overrides: object) -> DeliverableEvaluationProfileRef:
    values = {
        "profile_id": "profile:ux-v0.2-cs-client",
        "profile_version": "v1",
        "status": "approved",
        "checklist_refs": ("checklist:ux-v0.2-cs-review",),
        "constraint_refs": ("constraint:no-final-pass",),
        "evidence_expectation_refs": ("evidence-profile:render-and-test",),
        "threshold_policy_ref": "threshold:revise-block-accept",
        "source_refs": MONITOR_SOURCE_REFS,
        "baseline_ref": "standardization:profile-baseline",
    }
    values.update(overrides)
    return DeliverableEvaluationProfileRef(**values)


def valid_evaluation_result(**overrides: object) -> DeliverableEvaluationResult:
    values = {
        **monitor_base_values("DeliverableEvaluationResult", status="accepted"),
        "result_id": EVALUATION_ID,
        "deliverable_ref": "deliverable:ux-v0.2-cs-client",
        "evaluation_profile_ref": valid_profile_ref().__dict__,
        "checklist_result": "passed",
        "constraint_result": "passed",
        "evidence_mapping_result": "mapped",
        "score_or_threshold_result": "above_accept_threshold",
        "verdict": "accepted",
        "confidence": "high",
        "gaps": (),
        "required_correction": "",
        "decision_ref": f"HumanDecision:{DECISION_ID}",
    }
    values.update(overrides)
    return DeliverableEvaluationResult(**values)


def valid_escalation(**overrides: object) -> EscalationRecord:
    values = {
        **monitor_base_values("EscalationRecord", status="opened"),
        "escalation_id": ESCALATION_ID,
        "source_task_ref": f"HumanReviewTask:{REVIEW_ID}",
        "authority_gap": "reviewer is also proposed owner",
        "target_reviewer": "alex",
        "reason": "self-approval risk",
        "required_authority": "decision_authority:alex",
        "decision_ref": "",
    }
    values.update(overrides)
    return EscalationRecord(**values)


def valid_return_action(**overrides: object) -> ComponentReturnAction:
    values = {
        "return_action_id": "return-action-421-001",
        "decision_ref": f"HumanDecision:{DECISION_ID}",
        "review_task_ref": f"HumanReviewTask:{REVIEW_ID}",
        "target_component": "Project Execution",
        "target_work_item_ref": "workpacket:421-001",
        "action_type": "return_for_revision",
        "reason": "evidence missing",
        "required_correction": "add render evidence",
        "blocked_or_defer_condition": "",
        "resume_condition": "evidence package complete",
        "source_authority_refs": MONITOR_SOURCE_REFS,
        "kernel_record_ref": KERNEL_DECISION_RECORD_REF,
    }
    values.update(overrides)
    return ComponentReturnAction(**values)


def valid_review_disposition(**overrides: object) -> ReviewDisposition:
    values = {
        **monitor_base_values("ReviewDisposition", status="blocked"),
        "disposition_id": "review-disposition-421-001",
        "review_task_ref": f"HumanReviewTask:{REVIEW_ID}",
        "decision_ref": f"HumanDecision:{DECISION_ID}",
        "target_work_item_ref": "workpacket:421-001",
        "verdict": "revise",
        "baseline_effect": "revise_required",
        "return_action_ref": "ComponentReturnAction:return-action-421-001",
        "kernel_record_ref": KERNEL_DECISION_RECORD_REF,
    }
    values.update(overrides)
    return ReviewDisposition(**values)


def valid_create_review_task_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": ACTOR,
        "authority_refs": MONITOR_SOURCE_REFS,
        "review_task": valid_review_task(),
        "expected_version": 7,
        "idempotency_key": "slice006-review-task-421-001",
    }
    values.update(overrides)
    return create_human_review_task_command(**values)


def valid_submit_decision_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": REVIEWER,
        "authority_refs": MONITOR_SOURCE_REFS,
        "review_task_ref": f"HumanReviewTask:{REVIEW_ID}",
        "human_decision": valid_human_decision(),
        "expected_version": 8,
        "idempotency_key": "slice006-human-decision-421-001",
    }
    values.update(overrides)
    return submit_human_decision_command(**values)


def valid_evaluate_deliverable_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": REVIEWER,
        "authority_refs": MONITOR_SOURCE_REFS,
        "deliverable_ref": "deliverable:ux-v0.2-cs-client",
        "evaluation_profile_ref": valid_profile_ref(),
        "evidence_refs": ("evidence:render-check", "evidence:test-output"),
        "evaluation_result": valid_evaluation_result(),
        "expected_version": 8,
        "idempotency_key": "slice006-evaluate-deliverable-421-001",
    }
    values.update(overrides)
    return evaluate_deliverable_command(**values)


def valid_record_escalation_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": REVIEWER,
        "authority_refs": MONITOR_SOURCE_REFS,
        "escalation_record": valid_escalation(),
        "expected_version": 8,
        "idempotency_key": "slice006-escalation-421-001",
    }
    values.update(overrides)
    return record_escalation_command(**values)


def valid_normalize_disposition_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": REVIEWER,
        "authority_refs": MONITOR_SOURCE_REFS,
        "review_disposition": valid_review_disposition(),
        "component_return_action": valid_return_action(),
        "expected_version": 8,
        "idempotency_key": "slice006-return-action-421-001",
    }
    values.update(overrides)
    return normalize_review_disposition_command(**values)
