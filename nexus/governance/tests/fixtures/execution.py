from __future__ import annotations

from nexus.governance.execution import (
    ApprovedExecutionPlanCandidateRef,
    Layer1WorkPacket,
    PacketDependencyGraph,
    PacketMap,
    PacketReadinessDecision,
    PacketRepairRequest,
    PacketSupersedeRecord,
    create_layer1_workpacket_command,
    create_packet_repair_request_command,
    mark_packet_ready_command,
    supersede_workpacket_command,
    validate_packet_map_command,
)
from nexus.governance.schemas import ActorRef, CommandEnvelope


SOURCE_REFS = (
    "solution-design/subtopics/4_21_PROJECT_EXECUTION_DETAILED_DESIGN.md",
    "implementation-design/subtopics/L1_11_4_PROJECT_EXECUTION_IMPLEMENTATION_DESIGN.md",
    "PR11:0fc70602cc864eb6eb8fe82f7707371f1adbba6e",
)
PROJECT_ID = "project-421"
WORKSPACE_ID = "ws-421"
WORKSPACE_MANIFEST_REF = "manifest-ws-421:kernel-accepted"
APPROVED_PLAN_REF = "ExecutionPlanCandidate:plan-421-s003:v1"
ACTOR = ActorRef("agent:thunder", "implementation")


def valid_approved_plan_ref(**overrides: object) -> ApprovedExecutionPlanCandidateRef:
    values = {
        "project_id": PROJECT_ID,
        "plan_id": "plan-421-s003",
        "plan_version": 1,
        "kernel_acceptance_record_ref": "kernel-record:plan-baseline-000001",
        "approval_decision_ref": "human-decision:nova-approved-plan-421",
        "source_refs": SOURCE_REFS,
        "planning_output_refs": (
            "ProjectScopeNoGo:scope-421",
            "RequirementsSuccessCriteria:criteria-421",
            "EvidenceExpectationMap:evidence-421",
            "BacklogWbsDraft:backlog-421",
        ),
    }
    values.update(overrides)
    return ApprovedExecutionPlanCandidateRef(**values)


def base_values(item_type: str, status: str = "draft") -> dict[str, object]:
    return {
        "item_id": f"{item_type.lower()}-421",
        "item_type": item_type,
        "project_id": PROJECT_ID,
        "workspace_id": WORKSPACE_ID,
        "source_authority_refs": SOURCE_REFS,
        "approved_plan_ref": APPROVED_PLAN_REF,
        "workspace_manifest_ref": WORKSPACE_MANIFEST_REF,
        "source_refs": SOURCE_REFS,
        "status": status,
        "owning_component": "Project Execution",
        "consumer_component_refs": ("Dispatch Contract", "Project Monitor / HITL"),
        "version": 1,
        "notes": "slice 004 fixture",
    }


def valid_packet_map(**overrides: object) -> PacketMap:
    values = {
        **base_values("PacketMap"),
        "packet_map_id": "packet-map-421",
        "plan_ref": APPROVED_PLAN_REF,
        "milestone_refs": ("milestone:foundation",),
        "packet_ids": ("wp-421-001", "wp-421-002"),
        "dependency_graph_ref": "dependency-graph-421",
        "excluded_work_refs": ("out-of-scope:runtime-dispatch",),
        "source_wbs_refs": ("WBS:L1.11.4",),
    }
    values.update(overrides)
    return PacketMap(**values)


def valid_dependency_graph(**overrides: object) -> PacketDependencyGraph:
    values = {
        **base_values("PacketDependencyGraph"),
        "graph_id": "dependency-graph-421",
        "nodes": ("wp-421-001", "wp-421-002"),
        "edges": (("wp-421-001", "wp-421-002"),),
        "prerequisites": {"wp-421-002": ("wp-421-001",)},
        "blocked_edges": (),
        "cycle_check_result": "acyclic",
        "repair_refs": (),
    }
    values.update(overrides)
    return PacketDependencyGraph(**values)


def valid_workpacket(**overrides: object) -> Layer1WorkPacket:
    values = {
        **base_values("Layer1WorkPacket", status="review"),
        "packet_id": "wp-421-001",
        "packet_version": 1,
        "authority_refs": SOURCE_REFS,
        "objective": "create packet contract foundation",
        "work_type": "governance-contract",
        "scope": ("Project Execution records", "packet validators"),
        "no_go": ("no direct 4.19 controller call", "no work-packet dispatch"),
        "owner_role": "implementation-agent",
        "reviewer_role": "Nova",
        "required_capability": "local schema/test implementation",
        "expected_outputs": ("nexus/governance/execution.py", "slice004 evidence"),
        "forbidden_outputs": ("runtime dispatch", "final completion judgement"),
        "validation_plan": ("pytest governance tests", "import/no-go scans"),
        "evidence_contract_ref": "EvidenceExpectationMap:evidence-421",
        "acceptance_criteria": ("Nova can review packet contract boundaries",),
        "blocked_return_schema": {"blocked_reason": "string", "required_fix": "string"},
        "stop_rules": ("stop on direct controller call", "stop on missing approved plan evidence"),
        "human_review_required": True,
    }
    values.update(overrides)
    return Layer1WorkPacket(**values)


def valid_readiness_decision(**overrides: object) -> PacketReadinessDecision:
    values = {
        **base_values("PacketReadinessDecision", status="ready"),
        "decision_id": "readiness-wp-421-001",
        "packet_ref": "Layer1WorkPacket:wp-421-001:v1",
        "readiness_status": "ready",
        "readiness_check_result": "packet contract complete",
        "blocked_reason": "",
        "reviewer_ref": "Nova",
        "kernel_record_ref": "kernel-record:packet-ready-000001",
    }
    values.update(overrides)
    return PacketReadinessDecision(**values)


def valid_repair_request(**overrides: object) -> PacketRepairRequest:
    values = {
        **base_values("PacketRepairRequest", status="revise"),
        "request_id": "repair-wp-421-001",
        "packet_ref": "Layer1WorkPacket:wp-421-001:v1",
        "failing_fields": ("stop_rules",),
        "reason": "stop rules are incomplete",
        "required_correction": "add explicit stop rules",
        "owner": "Project Execution",
    }
    values.update(overrides)
    return PacketRepairRequest(**values)


def valid_supersede_record(**overrides: object) -> PacketSupersedeRecord:
    values = {
        **base_values("PacketSupersedeRecord", status="superseded"),
        "supersede_id": "supersede-wp-421-001",
        "old_packet_ref": "Layer1WorkPacket:wp-421-001:v1",
        "new_packet_ref": "Layer1WorkPacket:wp-421-001:v2",
        "reason": "repair request incorporated",
        "authority_ref": "human-decision:nova-repair-421",
        "kernel_record_ref": "kernel-record:packet-supersede-000001",
    }
    values.update(overrides)
    return PacketSupersedeRecord(**values)


def valid_create_workpacket_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": ACTOR,
        "authority_refs": SOURCE_REFS,
        "project_id": PROJECT_ID,
        "workspace_id": WORKSPACE_ID,
        "approved_plan_ref": APPROVED_PLAN_REF,
        "approval_decision_ref": "human-decision:nova-approved-plan-421",
        "kernel_acceptance_record_ref": "kernel-record:plan-baseline-000001",
        "workspace_manifest_ref": WORKSPACE_MANIFEST_REF,
        "packet_id": "wp-421-001",
        "packet_version": 1,
        "objective": "create packet contract foundation",
        "work_type": "governance-contract",
        "scope": ("Project Execution records",),
        "no_go": ("no direct 4.19 controller call",),
        "owner_role": "implementation-agent",
        "reviewer_role": "Nova",
        "required_capability": "local schema/test implementation",
        "expected_outputs": ("nexus/governance/execution.py",),
        "forbidden_outputs": ("runtime dispatch",),
        "validation_plan": ("pytest governance tests",),
        "evidence_contract_ref": "EvidenceExpectationMap:evidence-421",
        "acceptance_criteria": ("review-ready packet contract",),
        "blocked_return_schema": {"blocked_reason": "string"},
        "stop_rules": ("stop on direct controller call",),
        "human_review_required": True,
        "expected_version": 5,
        "idempotency_key": "slice004-create-workpacket-421",
    }
    values.update(overrides)
    return create_layer1_workpacket_command(**values)


def valid_validate_packet_map_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": ACTOR,
        "authority_refs": SOURCE_REFS,
        "project_id": PROJECT_ID,
        "workspace_id": WORKSPACE_ID,
        "approved_plan_ref": APPROVED_PLAN_REF,
        "packet_map_ref": "PacketMap:packet-map-421",
        "packet_ids": ("wp-421-001", "wp-421-002"),
        "dependency_graph_ref": "PacketDependencyGraph:dependency-graph-421",
        "expected_version": 5,
    }
    values.update(overrides)
    return validate_packet_map_command(**values)


def valid_mark_packet_ready_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": ACTOR,
        "authority_refs": SOURCE_REFS,
        "packet_ref": "Layer1WorkPacket:wp-421-001:v1",
        "packet_version": 1,
        "readiness_check_result_ref": "readiness-check:wp-421-001",
        "expected_version": 5,
        "idempotency_key": "slice004-mark-ready-wp-421-001",
    }
    values.update(overrides)
    return mark_packet_ready_command(**values)


def valid_repair_request_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": ACTOR,
        "authority_refs": SOURCE_REFS,
        "packet_ref": "Layer1WorkPacket:wp-421-001:v1",
        "failing_fields": ("stop_rules",),
        "reason": "stop rules missing",
        "required_correction": "add stop rules",
        "expected_version": 5,
        "idempotency_key": "slice004-repair-wp-421-001",
    }
    values.update(overrides)
    return create_packet_repair_request_command(**values)


def valid_supersede_command(**overrides: object) -> CommandEnvelope:
    values = {
        "actor": ACTOR,
        "authority_refs": SOURCE_REFS,
        "old_packet_ref": "Layer1WorkPacket:wp-421-001:v1",
        "new_packet_payload": {"packet_id": "wp-421-001", "packet_version": 2, "status": "review"},
        "supersede_reason": "repair request incorporated",
        "authority_ref": "human-decision:nova-repair-421",
        "expected_version": 5,
        "idempotency_key": "slice004-supersede-wp-421-001",
    }
    values.update(overrides)
    return supersede_workpacket_command(**values)
