"""Structured Task Handoff Controller data records for WBS 7.19."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class WorkflowConstraintSet:
    constraint_id: str
    source_refs: list[str]
    wbs_refs: list[str]
    gate_state: str
    dependency_state: str
    dod: list[str]
    no_go_scope: list[str]
    evidence_requirements: list[str]
    review_authority_refs: list[str]
    source_hash: str
    policy_hash: str
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkspaceInitializationContextPlaceholder:
    workspace_context_id: str
    workspace_refs: list[str]
    project_initialization_refs: list[str]
    active_wbs_ref: str
    source_hash: str
    policy_hash: str
    known_fields: dict[str, Any]
    tbd_fields: list[str]
    last_human_approved_change_ref: str
    placeholder_status: str
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RuntimeEligibilitySnapshot:
    snapshot_id: str
    collected_at: str
    projection_version: str
    candidate_owners: list[dict[str, Any]]
    capability_claims: dict[str, Any]
    authority_claims: dict[str, Any]
    readiness_state: dict[str, Any]
    presence_state: dict[str, Any]
    route_availability: dict[str, Any]
    freshness_result: str
    excluded_candidates: list[dict[str, Any]]
    read_only: bool = True
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourceAuthoritySet:
    authority_id: str
    input_kind: str
    source_refs: list[str]
    source_hash: str
    policy_hash: str
    status: str = "accepted_for_run"
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TaskEnvelope:
    task_id: str
    envelope_version: str
    run_id: str
    objective: str
    source_refs: list[str]
    source_hash: str
    policy_hash: str
    role_target: str
    required_capabilities: list[str]
    dependencies: list[str]
    constraints: list[str]
    no_go_scope: list[str]
    deliverables: list[str]
    stop_conditions: list[str]
    dispatch_mode: str
    idempotency_key: str
    validation_result: str = "draft_candidate"
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TaskUnit:
    task_id: str
    parent_id: Optional[str]
    title: str
    objective: str
    source_refs: list[str]
    source_hash: str
    owner: str
    verifier: str
    dependencies: list[str]
    priority: str
    status: str
    dod: list[str]
    no_go_scope: list[str]
    allowed_tools: list[str]
    allowed_write_surfaces: list[str]
    evidence_requirements: list[str]
    stop_conditions: list[str]
    escalation_conditions: list[str]
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DecompositionPlan:
    plan_id: str
    source_objective: str
    policy_ref: str
    generated_tasks: list[TaskUnit]
    dependency_graph: dict[str, list[str]]
    rejected_candidates: list[dict[str, Any]]
    ambiguity_notes: list[str]
    validation_result: str
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["generated_tasks"] = [task.to_dict() for task in self.generated_tasks]
        return data


@dataclass
class OwnerHandoffPacket:
    packet_id: str
    target_owner: str
    task_unit_ref: str
    required_context: list[str]
    exact_input_docs: list[str]
    owner_local_paths: list[str]
    no_go_boundaries: list[str]
    expected_deliverables: list[str]
    validation_commands_or_evidence: list[str]
    due_or_timeout: str
    reply_format: str
    stop_escalation_path: str
    audit_ref: str
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunLedger:
    run_id: str
    task_id: str
    envelope_version: str
    packet_id: str
    selected_role: str
    selected_runtime_id: str
    current_state: str
    state_history: list[str]
    checkpoint_refs: list[str]
    interruption_reason: Optional[str]
    timeout_at: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    last_event_at: Optional[str]
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RuntimeExecutionEvent:
    event_id: str
    run_id: str
    task_id: str
    runtime_id: str
    event_type: str
    event_time: str
    step_ref: Optional[str] = None
    progress_summary: Optional[str] = None
    touched_artifact_refs: list[str] = field(default_factory=list)
    error_code: Optional[str] = None
    checkpoint_ref: Optional[str] = None
    raw_event_ref: Optional[str] = None
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ModelCallTelemetry:
    call_id: str
    run_id: str
    task_id: str
    provider: str
    model: str
    prompt_hash: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    started_at: str
    ended_at: str
    status: str
    raw_usage_ref: str
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TaskAuditRecord:
    run_id: str
    source_refs: list[str]
    source_hash: str
    policy_hash: str
    validation_result: str
    packet_ref: Optional[str]
    secret_scan_result: str
    reviewer_refs: list[str]
    decision_refs: list[str]
    model_ref_if_used: Optional[str] = None
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EscalationRecord:
    escalation_id: str
    reason: str
    blocked_object: str
    required_decision: str
    current_owner: str
    evidence_ref: str
    status: str
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
