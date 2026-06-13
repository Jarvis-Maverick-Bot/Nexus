from __future__ import annotations

from nexus.governance.impact_control import (
    ImpactAssessment,
    ImpactControlRequest,
    ImpactReviewTaskRequest,
    LayerImpactDetected,
    LowerLayerRequestCandidate,
    LowerLayerRequestOutcome,
    ScopeRevisionCandidate,
    WorkaroundDecisionRequest,
    create_monitor_task_for_impact_command,
    record_impact_assessment_command,
    record_lower_layer_request_outcome_command,
    request_workaround_decision_command,
    submit_impact_control_request_command,
)
from nexus.governance.schemas import ActorRef, CommandEnvelope


IMPACT_SOURCE_REFS = (
    "solution-design/subtopics/4_21_LAYER_DEPENDENCY_IMPACT_CONTROL_DETAILED_DESIGN.md",
    "implementation-design/subtopics/L1_11_7_LAYER_DEPENDENCY_IMPACT_CONTROL_IMPLEMENTATION_DESIGN.md",
    "review-evidence/2026-06-13_NOVA_4_21_SLICE_007_TASK_PACKAGE_REVIEW.md",
    "SharedDocs:565ce91",
)
PROJECT_ID = "project-421"
WORKSPACE_ID = "workspace-421"
REQUEST_ID = "impact-request-421-001"
ASSESSMENT_ID = "impact-assessment-421-001"
IMPACT_ID = "layer-impact-421-001"
MONITOR_TASK_REF = "ImpactReviewTask:impact-review-421-001"
HUMAN_DECISION_REF = "HumanDecision:impact-decision-421-001"
ACTOR = ActorRef("agent:thunder", "implementation")
REVIEWER = ActorRef("nova", "reviewer")


def valid_impact_request(**overrides: object) -> ImpactControlRequest:
    values = {
        "request_id": REQUEST_ID,
        "caller_component": "Dispatch Contract",
        "caller_workflow_ref": "DispatchDecision:dispatch-421-001",
        "actor_authority_ref": "authority:alex-authorized-slice-007",
        "proposed_action": "classify blocked dispatch capability gap",
        "target_refs": ("Layer1WorkPacket:wp-421-001:v1",),
        "source_refs": IMPACT_SOURCE_REFS,
        "evidence_refs": ("dispatch:return-blocked:421",),
        "suspected_impact_surfaces": ("lower_layer_dependency", "implementation_contract"),
        "declared_affected_scope": "packet dispatch readiness",
        "requested_timing": "before caller proceeds",
        "idempotency_key": "slice007-impact-request-421-001",
        "status": "submitted",
    }
    values.update(overrides)
    return ImpactControlRequest(**values)


def valid_assessment(**overrides: object) -> ImpactAssessment:
    values = {
        "assessment_id": ASSESSMENT_ID,
        "request_ref": f"ImpactControlRequest:{REQUEST_ID}",
        "impact_level": "cross_boundary",
        "affected_surfaces": ("lower_layer_dependency", "implementation_contract"),
        "actual_impact_classification": "capability_gap_layer2",
        "risk_level": "medium",
        "owner_path_outcome": "4.19 owner path required before unblock",
        "allowed_next_action": "open_monitor_review",
        "required_reviews": ("Monitor/HITL impact review",),
        "evidence_requirements": ("dispatch blocked reason", "capability profile ref"),
        "blocked_reason": "",
        "trace_refs": ("DispatchDecision:dispatch-421-001",),
        "monitor_task_ref": MONITOR_TASK_REF,
        "status": "monitor_required",
    }
    values.update(overrides)
    return ImpactAssessment(**values)


def valid_local_assessment(**overrides: object) -> ImpactAssessment:
    values = {
        **valid_assessment().__dict__,
        "assessment_id": "impact-assessment-local-421",
        "impact_level": "local",
        "affected_surfaces": ("evidence_sufficiency",),
        "actual_impact_classification": "evidence_gap",
        "risk_level": "low",
        "owner_path_outcome": "not_applicable",
        "allowed_next_action": "proceed_local",
        "required_reviews": (),
        "blocked_reason": "",
        "monitor_task_ref": "",
        "status": "local_only",
    }
    values.update(overrides)
    return ImpactAssessment(**values)


def valid_layer_impact(**overrides: object) -> LayerImpactDetected:
    values = {
        "impact_id": IMPACT_ID,
        "project_id": PROJECT_ID,
        "workspace_id": WORKSPACE_ID,
        "assessment_ref": f"ImpactAssessment:{ASSESSMENT_ID}",
        "affected_layer": "layer_2",
        "gap_type": "capability_gap_layer2",
        "risk": "medium",
        "project_effect": "blocked packet remains waiting for Monitor decision",
        "source_refs": IMPACT_SOURCE_REFS,
        "proposed_route": "open Monitor/HITL review before request candidate",
        "workaround_status": "not_requested",
        "monitor_task_ref": MONITOR_TASK_REF,
        "kernel_record_ref": "krn-impact-000001",
        "status": "monitor_opened",
    }
    values.update(overrides)
    return LayerImpactDetected(**values)


def valid_review_task_request(**overrides: object) -> ImpactReviewTaskRequest:
    values = {
        "review_task_id": "impact-review-421-001",
        "assessment_ref": f"ImpactAssessment:{ASSESSMENT_ID}",
        "layer_impact_ref": f"LayerImpactDetected:{IMPACT_ID}",
        "review_question": "Should Layer 1 request lower-layer owner review or revise scope?",
        "options": ("request_lower_layer_review", "revise_scope", "defer", "block"),
        "owner_path": "4.19 owner path candidate only",
        "recommended_next_action": "open_monitor_review",
        "blocked_state_ref": "DispatchDecision:dispatch-421-001",
        "source_refs": IMPACT_SOURCE_REFS,
        "status": "monitor_opened",
    }
    values.update(overrides)
    return ImpactReviewTaskRequest(**values)


def valid_lower_layer_candidate(**overrides: object) -> LowerLayerRequestCandidate:
    values = {
        "candidate_id": "lower-layer-candidate-421-001",
        "assessment_ref": f"ImpactAssessment:{ASSESSMENT_ID}",
        "target_layer": "layer_2",
        "target_workspace_or_owner_path": "4.19 owner path",
        "requested_capability_or_clarification": "clarify owner eligibility for dispatch readiness",
        "constraints": ("candidate only", "no runtime call", "no lower-layer mutation"),
        "evidence_refs": ("dispatch:return-blocked:421",),
        "acceptance_test_hint": "owner response can be normalized as outcome only",
        "boundary_reason": "Layer 1 cannot redefine Layer 2 capability ownership",
        "monitor_decision_ref": HUMAN_DECISION_REF,
        "owner_acceptance_ref": "pending-owner-response",
        "status": "approved_candidate",
    }
    values.update(overrides)
    return LowerLayerRequestCandidate(**values)


def valid_lower_layer_outcome(**overrides: object) -> LowerLayerRequestOutcome:
    values = {
        "outcome_id": "lower-layer-outcome-421-001",
        "request_candidate_ref": "LowerLayerRequestCandidate:lower-layer-candidate-421-001",
        "target_layer": "layer_2",
        "owner_ref": "4.19-owner:nova",
        "outcome": "accepted",
        "accepted_scope_refs": ("4.19:capability-review-item",),
        "rejection_or_defer_reason": "",
        "evidence_refs": ("owner-response:421",),
        "expected_follow_up": "route back to Monitor/HITL before caller resumes",
        "kernel_or_owner_record_ref": "owner-record:421",
    }
    values.update(overrides)
    return LowerLayerRequestOutcome(**values)


def valid_scope_revision(**overrides: object) -> ScopeRevisionCandidate:
    values = {
        "revision_id": "scope-revision-421-001",
        "impact_ref": f"LayerImpactDetected:{IMPACT_ID}",
        "project_or_packet_refs": ("Layer1WorkPacket:wp-421-001:v1",),
        "scope_effect": "remove blocked lower-layer capability from this packet",
        "no_go_effect": "no-go list unchanged",
        "proposed_revision": "route capability request separately after Monitor decision",
        "standardization_ref": "Standardization:plan-profile-421",
        "monitor_decision_ref": HUMAN_DECISION_REF,
        "status": "approved_for_standardization_review",
    }
    values.update(overrides)
    return ScopeRevisionCandidate(**values)


def valid_workaround_request(**overrides: object) -> WorkaroundDecisionRequest:
    values = {
        "request_id": "workaround-request-421-001",
        "impact_ref": f"LayerImpactDetected:{IMPACT_ID}",
        "workaround_option": "defer dispatch and keep packet blocked",
        "risk": "medium",
        "expiry": "2026-06-20T00:00:00Z",
        "rollback_condition": "owner path rejects capability",
        "evidence_requirement": "Monitor decision and owner response attached",
        "decision_ref": HUMAN_DECISION_REF,
        "status": "approved",
    }
    values.update(overrides)
    return WorkaroundDecisionRequest(**values)


def valid_submit_request_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": ACTOR,
        "authority_refs": IMPACT_SOURCE_REFS,
        "impact_request": valid_impact_request(),
        "expected_version": 7,
        "idempotency_key": "slice007-submit-impact-request-421-001",
    }
    values.update(overrides)
    return submit_impact_control_request_command(**values)


def valid_record_assessment_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": ACTOR,
        "authority_refs": IMPACT_SOURCE_REFS,
        "assessment": valid_assessment(),
        "expected_version": 8,
        "idempotency_key": "slice007-record-assessment-421-001",
    }
    values.update(overrides)
    return record_impact_assessment_command(**values)


def valid_create_review_task_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": ACTOR,
        "authority_refs": IMPACT_SOURCE_REFS,
        "assessment_ref": f"ImpactAssessment:{ASSESSMENT_ID}",
        "layer_impact_detected": valid_layer_impact(),
        "review_question": "Should Layer 1 request lower-layer owner review or revise scope?",
        "options": ("request_lower_layer_review", "revise_scope", "defer", "block"),
        "expected_version": 9,
        "idempotency_key": "slice007-create-impact-review-task-421-001",
    }
    values.update(overrides)
    return create_monitor_task_for_impact_command(**values)


def valid_record_outcome_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": REVIEWER,
        "authority_refs": IMPACT_SOURCE_REFS,
        "outcome": valid_lower_layer_outcome(),
        "expected_version": 10,
        "idempotency_key": "slice007-record-lower-layer-outcome-421-001",
    }
    values.update(overrides)
    return record_lower_layer_request_outcome_command(**values)


def valid_request_workaround_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": REVIEWER,
        "authority_refs": IMPACT_SOURCE_REFS,
        "workaround_request": valid_workaround_request(status="review_required", decision_ref=""),
        "expected_version": 10,
        "idempotency_key": "slice007-request-workaround-decision-421-001",
    }
    values.update(overrides)
    return request_workaround_decision_command(**values)
