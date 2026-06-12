from __future__ import annotations

from nexus.governance.dispatch_contract import (
    DispatchContext,
    DispatchControllerHandoffCandidate,
    DispatchDecision,
    DispatchReadinessReview,
    Layer2CapabilityProfileRef,
    Layer3TransportConstraintRef,
    ReturnedBlockedReason,
    ReturnedResultCandidate,
    create_dispatch_controller_handoff_candidate_command,
    evaluate_dispatch_readiness_command,
    normalize_dispatch_return_command,
)
from nexus.governance.schemas import ActorRef, CommandEnvelope

from .execution import ACTOR, APPROVED_PLAN_REF, PROJECT_ID, SOURCE_REFS, WORKSPACE_ID, valid_workpacket


DISPATCH_SOURCE_REFS = (
    "solution-design/subtopics/4_21_LAYER1_LAYER2_DISPATCH_CONTRACT_DETAILED_DESIGN.md",
    "implementation-design/subtopics/L1_11_5_LAYER1_LAYER2_DISPATCH_CONTRACT_IMPLEMENTATION_DESIGN.md",
    "PR12:2cd4a1e06dc93908d2e9bac2f493a17489344e0d",
)
PACKET_ID = "wp-421-001"
PACKET_VERSION = 1
PACKET_REF = "Layer1WorkPacket:wp-421-001:v1"
KERNEL_PACKET_RECORD_REF = "kernel-record:packet-ready-000001"
DISPATCH_DECISION_REF = "DispatchDecision:dispatch-decision-421-001"
CORRELATION_ID = "corr-dispatch-421-001"
CAUSATION_ID = "cause-packet-ready-421-001"
IDEMPOTENCY_KEY = "slice005-dispatch-421-001"


def kernel_ready_workpacket(**overrides: object):
    values = {
        "status": "ready",
        "packet_id": PACKET_ID,
        "packet_version": PACKET_VERSION,
        "authority_refs": SOURCE_REFS,
        "source_refs": SOURCE_REFS,
        "approved_plan_ref": APPROVED_PLAN_REF,
    }
    values.update(overrides)
    return valid_workpacket(**values)


def valid_capability_profile(**overrides: object) -> Layer2CapabilityProfileRef:
    values = {
        "profile_id": "capability:local-schema-test",
        "profile_version": "v1",
        "eligible_owner_roles": ("implementation-agent",),
        "eligible_runtime_classes": ("non-live-contract",),
        "capability_tags": ("local schema/test implementation", "governance-contract"),
        "readiness_constraints": ("no runtime invocation",),
        "authority_constraints": ("4.19 baseline citation only",),
        "source_refs": DISPATCH_SOURCE_REFS,
        "baseline_ref": "4.19",
        "status": "validated",
    }
    values.update(overrides)
    return Layer2CapabilityProfileRef(**values)


def valid_transport_constraint(**overrides: object) -> Layer3TransportConstraintRef:
    values = {
        "constraint_id": "transport:3.5-durable-boundary",
        "constraint_version": "v1",
        "durability_ref": "3.5 bounded closeout",
        "retry_policy_ref": "no blind retry",
        "recovery_constraint_refs": ("reconcile unknown outcomes",),
        "source_refs": DISPATCH_SOURCE_REFS,
        "baseline_ref": "3.5",
        "status": "validated",
        "ack_is_progress": False,
    }
    values.update(overrides)
    return Layer3TransportConstraintRef(**values)


def valid_dispatch_context(**overrides: object) -> DispatchContext:
    values = {
        "command_id": "cmd-dispatch-421-001",
        "correlation_id": CORRELATION_ID,
        "causation_id": CAUSATION_ID,
        "requester_role": "Project Execution",
        "request_timestamp": "2026-06-12T13:48:03Z",
        "idempotency_key": IDEMPOTENCY_KEY,
        "expected_version": 7,
    }
    values.update(overrides)
    return DispatchContext(**values)


def dispatch_base_values(item_type: str, status: str = "draft") -> dict[str, object]:
    return {
        "item_id": f"{item_type.lower()}-421",
        "item_type": item_type,
        "project_id": PROJECT_ID,
        "workspace_id": WORKSPACE_ID,
        "packet_id": PACKET_ID,
        "packet_version": PACKET_VERSION,
        "source_authority_refs": DISPATCH_SOURCE_REFS,
        "kernel_packet_record_ref": KERNEL_PACKET_RECORD_REF,
        "status": status,
        "owning_component": "Layer 1 / Layer 2 Dispatch Contract",
        "consumer_component_refs": ("Project Monitor / HITL", "Impact Control"),
        "correlation_id": CORRELATION_ID,
        "causation_id": CAUSATION_ID,
        "idempotency_key": IDEMPOTENCY_KEY,
        "notes": "slice 005 fixture",
    }


def valid_readiness_review(**overrides: object) -> DispatchReadinessReview:
    values = {
        **dispatch_base_values("DispatchReadinessReview", status="passed"),
        "review_id": "readiness-review-421-001",
        "packet_ref": PACKET_REF,
        "authority_check": "passed",
        "completeness_check": "passed",
        "owner_eligibility_check": "passed",
        "capability_check": "passed",
        "transport_constraint_check": "passed",
        "no_go_check": "passed",
        "stop_rule_check": "passed",
        "idempotency_check": "passed",
        "result": "passed",
        "blocked_reasons": (),
    }
    values.update(overrides)
    return DispatchReadinessReview(**values)


def valid_dispatch_decision(**overrides: object) -> DispatchDecision:
    values = {
        **dispatch_base_values("DispatchDecision", status="accepted_for_dispatch"),
        "decision_id": "dispatch-decision-421-001",
        "packet_ref": PACKET_REF,
        "readiness_review_ref": "DispatchReadinessReview:readiness-review-421-001",
        "route_basis": "4.19 baseline capability citation",
        "capability_basis": "capability:local-schema-test",
        "reason": "packet is eligible for future handoff review",
        "blocked_reason": "",
        "result_refs": (),
        "reviewer_or_authority_refs": ("human-decision:nova-slice005-package",),
        "kernel_record_ref": "",
    }
    values.update(overrides)
    return DispatchDecision(**values)


def valid_handoff_candidate(**overrides: object) -> DispatchControllerHandoffCandidate:
    values = {
        **dispatch_base_values("DispatchControllerHandoffCandidate", status="candidate"),
        "handoff_candidate_id": "handoff-candidate-421-001",
        "dispatch_decision_ref": DISPATCH_DECISION_REF,
        "packet_ref": PACKET_REF,
        "route_basis": "future adapter contract only",
        "required_capability": "local schema/test implementation",
        "owner_role": "implementation-agent",
        "no_go_refs": ("no runtime invocation", "no direct 4.19 controller call"),
        "evidence_contract_ref": "EvidenceExpectationMap:evidence-421",
        "expected_outputs": ("dispatch boundary contract",),
        "forbidden_outputs": ("runtime dispatch", "final PASS"),
        "stop_rules": ("stop on controller call",),
        "blocked_return_schema": {"category": "string", "required_decision_or_action": "string"},
        "controller_baseline_ref": "4.19",
    }
    values.update(overrides)
    return DispatchControllerHandoffCandidate(**values)


def valid_result_candidate(**overrides: object) -> ReturnedResultCandidate:
    values = {
        **dispatch_base_values("ReturnedResultCandidate", status="returned_result_candidate"),
        "result_candidate_id": "result-candidate-421-001",
        "dispatch_decision_ref": DISPATCH_DECISION_REF,
        "packet_ref": PACKET_REF,
        "result_refs": ("result:artifact-001",),
        "evidence_refs": ("evidence:run-log-001",),
        "owner_notes": "owner returned a result candidate",
        "validation_candidate": "pending monitor review",
        "monitor_task_ref": "monitor-task:review-result-001",
    }
    values.update(overrides)
    return ReturnedResultCandidate(**values)


def valid_blocked_reason(**overrides: object) -> ReturnedBlockedReason:
    values = {
        **dispatch_base_values("ReturnedBlockedReason", status="returned_blocked"),
        "blocked_id": "returned-blocked-421-001",
        "dispatch_decision_ref": DISPATCH_DECISION_REF,
        "packet_ref": PACKET_REF,
        "category": "blocked_missing_capability",
        "affected_layer": "Layer 2",
        "required_decision_or_action": "route to Impact Control",
        "source_refs": DISPATCH_SOURCE_REFS,
        "repair_hint": "add approved capability or revise packet",
        "impact_candidate_ref": "impact-candidate:421-001",
    }
    values.update(overrides)
    return ReturnedBlockedReason(**values)


def valid_evaluate_dispatch_readiness_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": ACTOR,
        "authority_refs": DISPATCH_SOURCE_REFS,
        "packet_ref": PACKET_REF,
        "packet_version": PACKET_VERSION,
        "kernel_packet_record_ref": KERNEL_PACKET_RECORD_REF,
        "readiness_review_id": "readiness-review-421-001",
        "capability_ref": "capability:local-schema-test",
        "transport_constraint_refs": ("transport:3.5-durable-boundary",),
        "dispatch_context": valid_dispatch_context().__dict__,
        "expected_version": 7,
        "idempotency_key": IDEMPOTENCY_KEY,
    }
    values.update(overrides)
    return evaluate_dispatch_readiness_command(**values)


def valid_handoff_candidate_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": ACTOR,
        "authority_refs": DISPATCH_SOURCE_REFS,
        "dispatch_decision_ref": DISPATCH_DECISION_REF,
        "packet_ref": PACKET_REF,
        "packet_version": PACKET_VERSION,
        "kernel_packet_record_ref": KERNEL_PACKET_RECORD_REF,
        "route_basis": "future adapter contract only",
        "required_capability": "local schema/test implementation",
        "owner_role": "implementation-agent",
        "correlation_id": CORRELATION_ID,
        "causation_id": CAUSATION_ID,
        "idempotency_key": "slice005-handoff-421-001",
        "no_go_refs": ("no runtime invocation",),
        "evidence_contract_ref": "EvidenceExpectationMap:evidence-421",
        "expected_outputs": ("dispatch boundary contract",),
        "forbidden_outputs": ("runtime dispatch",),
        "stop_rules": ("stop on controller call",),
        "blocked_return_schema": {"category": "string"},
        "controller_baseline_ref": "4.19",
        "expected_version": 7,
    }
    values.update(overrides)
    return create_dispatch_controller_handoff_candidate_command(**values)


def valid_normalize_return_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": ActorRef("agent:thunder", "implementation"),
        "authority_refs": DISPATCH_SOURCE_REFS,
        "dispatch_decision_ref": DISPATCH_DECISION_REF,
        "correlation_id": CORRELATION_ID,
        "return_kind": "result_candidate",
        "result_refs": ("result:artifact-001",),
        "evidence_refs": ("evidence:run-log-001",),
        "blocked_reason": "",
        "owner_notes": "owner returned a result candidate",
        "source_refs": DISPATCH_SOURCE_REFS,
        "expected_version": 7,
        "idempotency_key": "slice005-return-421-001",
    }
    values.update(overrides)
    return normalize_dispatch_return_command(**values)
