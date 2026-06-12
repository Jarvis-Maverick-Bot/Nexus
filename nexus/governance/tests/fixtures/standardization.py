from __future__ import annotations

from nexus.governance.schemas import ActorRef, CommandEnvelope
from nexus.governance.standardization import (
    AmbiguityItem,
    AmbiguityRegister,
    ApprovalPacket,
    DeliverableEvaluationProfile,
    EvidenceExpectationMap,
    ExecutionPlanCandidate,
    FeedbackMetricPolicy,
    PlanningInputPackage,
    ProjectScopeNoGo,
    ProjectVision,
    RequirementsSuccessCriteria,
    create_approval_packet_command,
    submit_standardization_draft_command,
    supersede_plan_candidate_command,
)


SOURCE_REFS = (
    "solution-design/subtopics/4_21_PROJECT_STANDARDIZATION_DETAILED_DESIGN.md",
    "implementation-design/subtopics/L1_11_3_PROJECT_STANDARDIZATION_IMPLEMENTATION_DESIGN.md",
    "review-evidence/2026-06-11_NOVA_L1_11_QA_FEEDBACK_METRICS_CORRECTION.md",
    "PR10:5f94c27038d4b8f84361d2336a6a826afcdea987",
)
WORKSPACE_MANIFEST_REF = "manifest-ws-421:kernel-accepted"
PROJECT_ID = "project-421"
WORKSPACE_ID = "ws-421"
ACTOR = ActorRef("agent:thunder", "implementation")


def base_values(item_type: str, status: str = "draft") -> dict[str, object]:
    return {
        "item_id": f"{item_type.lower()}-421",
        "item_type": item_type,
        "project_id": PROJECT_ID,
        "workspace_id": WORKSPACE_ID,
        "source_authority_refs": SOURCE_REFS,
        "workspace_manifest_ref": WORKSPACE_MANIFEST_REF,
        "source_refs": SOURCE_REFS,
        "status": status,
        "owning_component": "Project Standardization",
        "consumer_component_refs": ("Project Monitor / HITL", "Project Execution"),
        "version": 1,
        "notes": "slice 003 fixture",
    }


def valid_planning_input(**overrides: object) -> PlanningInputPackage:
    values = {
        **base_values("PlanningInputPackage"),
        "workspace_init_refs": ("workspace-init:manifest-ws-421",),
        "raw_input_refs": ("notes:alex-4.21",),
        "feedback_refs": ("feedback:qa-correction",),
        "constraint_refs": ("boundary:layer-1-no-runtime",),
        "authority_refs": SOURCE_REFS,
        "intake_summary": "governed standardization planning package",
    }
    values.update(overrides)
    return PlanningInputPackage(**values)


def valid_ambiguity_register(
    ambiguity_items: tuple[AmbiguityItem, ...] | None = None, **overrides: object
) -> AmbiguityRegister:
    values = {
        **base_values("AmbiguityRegister"),
        "ambiguity_items": ambiguity_items
        if ambiguity_items is not None
        else (
            AmbiguityItem(
                ambiguity_id="amb-001",
                severity="medium",
                owner="Nova",
                required_decision="confirm review cadence",
                status="answered",
                resolution_ref="decision:review-cadence",
            ),
        ),
    }
    values.update(overrides)
    return AmbiguityRegister(**values)


def valid_scope_no_go(**overrides: object) -> ProjectScopeNoGo:
    values = {
        **base_values("ProjectScopeNoGo", status="review"),
        "in_scope": ("standardization records", "planning candidate validators"),
        "out_of_scope": ("runtime dispatch", "project execution packet generation"),
        "no_go": ("no final PASS", "no Shared Docs writes"),
        "constraints": ("Layer 1 only",),
        "boundary_refs": ("slice003:approved-package",),
        "change_trigger": "Nova/Alex review decision",
    }
    values.update(overrides)
    return ProjectScopeNoGo(**values)


def valid_criteria(**overrides: object) -> RequirementsSuccessCriteria:
    values = {
        **base_values("RequirementsSuccessCriteria", status="review"),
        "requirements": ("planning candidates are field-complete",),
        "success_metrics": ("all material deliverables have QA profile refs",),
        "acceptance_signals": ("Nova review can trace each planning ref",),
        "evidence_expectations": ("pytest output", "no-go scan", "import scan"),
        "measurement_method": "review checklist plus machine evidence",
    }
    values.update(overrides)
    return RequirementsSuccessCriteria(**values)


def valid_profile(**overrides: object) -> DeliverableEvaluationProfile:
    values = {
        **base_values("DeliverableEvaluationProfile", status="review"),
        "deliverable_type": "implementation-design-package",
        "applicable_work_items": ("ExecutionPlanCandidate", "ApprovalPacket"),
        "quality_dimensions": ("source traceability", "boundary compliance", "test evidence"),
        "review_checklist": ("all required refs present", "no dispatch authority emitted"),
        "llm_review_constraints": ("do not infer acceptance from draft text",),
        "required_evidence": ("pytest", "diff-check", "import-scan"),
        "measurement_method": "checklist scoring",
        "pass_threshold": 0.9,
        "revise_threshold": 0.7,
        "block_conditions": ("missing source authority", "self approval"),
        "reviewer_authority_ref": "Nova/Alex",
        "escalation_conditions": ("critical ambiguity",),
    }
    values.update(overrides)
    return DeliverableEvaluationProfile(**values)


def valid_feedback_policy(**overrides: object) -> FeedbackMetricPolicy:
    values = {
        **base_values("FeedbackMetricPolicy", status="review"),
        "categories": ("quality", "scope", "evidence", "boundary"),
        "severity_scale": ("low", "medium", "high", "blocking"),
        "confidence_rules": ("source-backed only",),
        "frequency_window": "per review cycle",
        "promotion_thresholds": {"requirement": 2, "blocker": 1},
        "triage_owner": "Project Standardization",
    }
    values.update(overrides)
    return FeedbackMetricPolicy(**values)


def valid_evidence_map(**overrides: object) -> EvidenceExpectationMap:
    values = {
        **base_values("EvidenceExpectationMap", status="review"),
        "criteria_to_evidence_map": {"criteria-001": ("pytest", "diff-check")},
        "required_evidence_types": ("test-output", "scan-output"),
        "review_owner": "Nova",
        "acceptance_signal_refs": ("signal:review-ready",),
    }
    values.update(overrides)
    return EvidenceExpectationMap(**values)


def valid_vision(**overrides: object) -> ProjectVision:
    values = {
        **base_values("ProjectVision"),
        "problem_statement": "fragmented project input needs governed planning",
        "target_user": "Alex/Nova review flow",
        "value_statement": "review-ready plan candidate without dispatch authority",
        "desired_outcome": "approval packet can be reviewed by HITL",
        "strategic_fit": "Layer 1 governance execution",
        "non_goal_summary": "not runtime execution",
    }
    values.update(overrides)
    return ProjectVision(**values)


def valid_execution_plan(**overrides: object) -> ExecutionPlanCandidate:
    values = {
        **base_values("ExecutionPlanCandidate", status="review"),
        "plan_id": "plan-421-s003",
        "vision_ref": "ProjectVision:projectvision-421",
        "scope_ref": "ProjectScopeNoGo:projectscopenogo-421",
        "criteria_ref": "RequirementsSuccessCriteria:requirementssuccesscriteria-421",
        "risk_ref": "RiskRegisterCandidate:risk-421",
        "dependency_ref": "DependencyMap:dependency-421",
        "milestone_ref": "MilestonePlanCandidate:milestone-421",
        "backlog_wbs_ref": "BacklogWbsDraft:backlog-421",
        "evidence_map_ref": "EvidenceExpectationMap:evidenceexpectationmap-421",
        "approval_packet_ref": "ApprovalPacket:approvalpacket-421",
        "material_deliverable_types": ("implementation-design-package",),
        "profile_refs": ("DeliverableEvaluationProfile:deliverableevaluationprofile-421",),
        "feedback_metric_policy_ref": "FeedbackMetricPolicy:feedbackmetricpolicy-421",
        "ambiguity_register_ref": "AmbiguityRegister:ambiguityregister-421",
    }
    values.update(overrides)
    return ExecutionPlanCandidate(**values)


def valid_approval_packet(**overrides: object) -> ApprovalPacket:
    values = {
        **base_values("ApprovalPacket", status="submitted"),
        "packet_id": "approval-packet-421-s003",
        "plan_ref": "ExecutionPlanCandidate:plan-421-s003",
        "requested_decision": "human_review",
        "open_questions": ("confirm no unresolved blockers",),
        "recommendation": "review for approval readiness",
        "evidence_refs": ("verification/4.21/l1gov-slice-003/evidence-index.json",),
        "reviewer_refs": ("Nova", "Alex"),
        "decision_result_ref": "",
    }
    values.update(overrides)
    return ApprovalPacket(**values)


def valid_submit_draft_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": ACTOR,
        "authority_refs": SOURCE_REFS,
        "project_id": PROJECT_ID,
        "workspace_id": WORKSPACE_ID,
        "workspace_manifest_ref": WORKSPACE_MANIFEST_REF,
        "planning_input_ref": "PlanningInputPackage:planninginputpackage-421",
        "normalized_input_ref": "NormalizedInputMap:normalizedinputmap-421",
        "criteria_ref": "RequirementsSuccessCriteria:requirementssuccesscriteria-421",
        "profile_refs": ("DeliverableEvaluationProfile:deliverableevaluationprofile-421",),
        "feedback_metric_policy_ref": "FeedbackMetricPolicy:feedbackmetricpolicy-421",
        "ambiguity_register_ref": "AmbiguityRegister:ambiguityregister-421",
        "expected_version": 4,
        "idempotency_key": "slice003-submit-draft-plan-421",
    }
    values.update(overrides)
    return submit_standardization_draft_command(**values)


def valid_create_approval_packet_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": ACTOR,
        "authority_refs": SOURCE_REFS,
        "project_id": PROJECT_ID,
        "workspace_id": WORKSPACE_ID,
        "plan_ref": "ExecutionPlanCandidate:plan-421-s003",
        "requested_decision": "human_review",
        "open_questions": ("confirm package review disposition",),
        "evidence_refs": ("verification/4.21/l1gov-slice-003/evidence-index.json",),
        "reviewer_refs": ("Nova", "Alex"),
        "expected_version": 4,
        "idempotency_key": "slice003-create-approval-packet-421",
    }
    values.update(overrides)
    return create_approval_packet_command(**values)


def valid_supersede_plan_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": ACTOR,
        "authority_refs": SOURCE_REFS,
        "project_id": PROJECT_ID,
        "prior_plan_ref": "ExecutionPlanCandidate:plan-421-s003",
        "revised_plan_payload": {"plan_id": "plan-421-s003-r1", "status": "draft"},
        "supersede_reason": "Nova requested revision",
        "expected_version": 4,
        "idempotency_key": "slice003-supersede-plan-421",
    }
    values.update(overrides)
    return supersede_plan_candidate_command(**values)
