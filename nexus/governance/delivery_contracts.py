from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import re
from typing import Any

from .errors import ErrorCode


WORK_ITEM_STATUSES: tuple[str, ...] = (
    "draft",
    "ready",
    "assigned",
    "running",
    "blocked",
    "review",
    "uat",
    "done",
    "failed",
    "cancelled",
)
RUNTIME_AUTHORIZATION_STATES: tuple[str, ...] = (
    "not_required",
    "hold",
    "authorized_for_named_command",
    "blocked_by_policy",
)
OWNER_UAT_STATES: tuple[str, ...] = (
    "not_ready",
    "awaiting_owner",
    "accepted_by_owner",
    "rejected_by_owner",
    "not_applicable",
)
EVIDENCE_STATES: tuple[str, ...] = (
    "missing",
    "stale",
    "present",
    "failed",
    "not_run_by_scope",
)
REVIEW_EVIDENCE_STATUSES: tuple[str, ...] = ("review", "uat", "done")
FRESH_EVIDENCE_STATES: tuple[str, ...] = ("present", "failed", "not_run_by_scope")
TASK_CARD_REQUIRED_FIELDS: tuple[str, ...] = (
    "background",
    "goal",
    "scope",
    "non_goals",
    "file_boundaries",
    "acceptance_criteria",
    "validation_commands",
    "risks",
    "write_back_location",
)
INTERNAL_PR_RE = re.compile(r"^EDC-PR-\d{3}$")


@dataclass(frozen=True)
class DeliveryValidationResult:
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
class DeliveryProject:
    project_id: str = ""
    repo_root: str = ""
    default_base_branch: str = ""
    active_branch: str = ""
    worktree_path: str = ""
    validation_entrypoints: tuple[str, ...] = ()
    evidence_locations: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class TaskCard:
    background: str = ""
    goal: str = ""
    scope: tuple[str, ...] = ()
    non_goals: tuple[str, ...] = ()
    file_boundaries: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    validation_commands: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    write_back_location: str = ""


@dataclass(frozen=True)
class AgentRecord:
    agent_id: str = ""
    role: str = ""
    availability: str = ""
    current_assignment_id: str = ""
    last_report_ref: str = ""
    blockers: tuple[str, ...] = ()
    allowed_actions: tuple[str, ...] = ()


@dataclass(frozen=True)
class AssignmentRecord:
    assignment_id: str = ""
    work_item_id: str = ""
    agent_id: str = ""
    branch: str = ""
    worktree_path: str = ""
    editable_scope: tuple[str, ...] = ()
    allowed_actions: tuple[str, ...] = ()
    forbidden_actions: tuple[str, ...] = ()
    reducer_owner: str = ""


@dataclass(frozen=True)
class RunRecord:
    run_id: str = ""
    work_item_id: str = ""
    status: str = ""
    branch: str = ""
    worktree_path: str = ""
    files_touched: tuple[str, ...] = ()
    validation_commands: tuple[str, ...] = ()
    command_results: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    completion_report_ref: str = ""
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass(frozen=True)
class RuntimeAuthorization:
    state: str = ""
    named_command: str = ""
    authority_ref: str = ""
    source_ref: str = ""


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str = ""
    state: str = ""
    command: str = ""
    result_ref: str = ""
    source_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValidationEvidenceRecord:
    validation_id: str = ""
    evidence: EvidenceRecord | None = None
    validated_at: str = ""
    validator: str = ""


@dataclass(frozen=True)
class PrMapping:
    internal_id: str = ""
    github_pr_number: int | None = None
    github_pr_url: str = ""
    branch: str = ""
    status: str = ""


@dataclass(frozen=True)
class OwnerUatDecision:
    state: str = ""
    owner_ref: str = ""
    decision_ref: str = ""
    notes: str = ""


@dataclass(frozen=True)
class WorkItem:
    work_item_id: str = ""
    title: str = ""
    status: str = ""
    task_card: TaskCard | None = None
    project: DeliveryProject | None = None
    agent: AgentRecord | None = None
    assignment: AssignmentRecord | None = None
    run: RunRecord | None = None
    runtime_authorization: RuntimeAuthorization | None = None
    evidence: EvidenceRecord | None = None
    validation: ValidationEvidenceRecord | None = None
    pr_mapping: PrMapping | None = None
    owner_uat: OwnerUatDecision | None = None
    parallel_fanout_active: bool = False
    reducer_owner: str = ""
    source_refs: tuple[str, ...] = ()


def validate_delivery_project(project: DeliveryProject) -> DeliveryValidationResult:
    missing = _missing_fields(
        project,
        (
            "project_id",
            "repo_root",
            "default_base_branch",
            "active_branch",
            "worktree_path",
            "validation_entrypoints",
            "source_refs",
        ),
    )
    invalid_items = _unsafe_paths((project.repo_root, project.worktree_path, *project.evidence_locations))
    return _result(
        missing=missing,
        invalid_items=invalid_items,
        blocked_reasons=(),
        error_code=ErrorCode.NO_GO_BOUNDARY if invalid_items else ErrorCode.EXECUTION_RECORD_INVALID,
        message="delivery project rejected",
    )


def validate_task_card(task_card: TaskCard) -> DeliveryValidationResult:
    missing = _missing_fields(task_card, TASK_CARD_REQUIRED_FIELDS)
    invalid_items = _unsafe_paths(task_card.file_boundaries)
    return _result(
        missing=missing,
        invalid_items=invalid_items,
        blocked_reasons=(),
        error_code=ErrorCode.NO_GO_BOUNDARY if invalid_items else ErrorCode.EXECUTION_WORKPACKET_INVALID,
        message="task card rejected",
    )



def validate_agent_record(agent: AgentRecord) -> DeliveryValidationResult:
    missing = _missing_fields(agent, ("agent_id", "role", "availability", "allowed_actions"))
    return _result(
        missing=missing,
        blocked_reasons=(),
        invalid_items=(),
        error_code=ErrorCode.EXECUTION_RECORD_INVALID,
        message="agent record rejected",
    )
def validate_assignment_record(assignment: AssignmentRecord) -> DeliveryValidationResult:
    missing = _missing_fields(
        assignment,
        (
            "assignment_id",
            "work_item_id",
            "agent_id",
            "branch",
            "worktree_path",
            "editable_scope",
            "allowed_actions",
            "forbidden_actions",
        ),
    )
    invalid_items = _unsafe_paths((assignment.worktree_path, *assignment.editable_scope))
    return _result(
        missing=missing,
        invalid_items=invalid_items,
        blocked_reasons=(),
        error_code=ErrorCode.NO_GO_BOUNDARY if invalid_items else ErrorCode.EXECUTION_RECORD_INVALID,
        message="assignment rejected",
    )



def validate_run_record(run: RunRecord) -> DeliveryValidationResult:
    missing = _missing_fields(
        run,
        (
            "run_id",
            "work_item_id",
            "status",
            "branch",
            "worktree_path",
            "files_touched",
            "validation_commands",
            "command_results",
            "completion_report_ref",
        ),
    )
    invalid_items = _unsafe_paths((run.worktree_path, *run.files_touched))
    return _result(
        missing=missing,
        blocked_reasons=(),
        invalid_items=invalid_items,
        error_code=ErrorCode.NO_GO_BOUNDARY if invalid_items else ErrorCode.EXECUTION_RECORD_INVALID,
        message="run record rejected",
    )
def validate_runtime_authorization(authorization: RuntimeAuthorization) -> DeliveryValidationResult:
    missing = _missing_fields(authorization, ("state", "source_ref"))
    blocked_reasons: list[str] = []
    if authorization.state and authorization.state not in RUNTIME_AUTHORIZATION_STATES:
        blocked_reasons.append(f"invalid runtime authorization state: {authorization.state}")
    if authorization.state == "authorized_for_named_command":
        missing = _merge_missing(missing, _missing_fields(authorization, ("named_command", "authority_ref", "source_ref")))
    return _result(
        missing=missing,
        blocked_reasons=tuple(blocked_reasons),
        invalid_items=(),
        error_code=ErrorCode.MISSING_HUMAN_DECISION
        if authorization.state == "authorized_for_named_command" and missing
        else ErrorCode.EXECUTION_RECORD_INVALID,
        message="runtime authorization rejected",
    )


def validate_evidence_record(evidence: EvidenceRecord) -> DeliveryValidationResult:
    missing = _missing_fields(evidence, ("evidence_id", "state", "source_refs"))
    blocked_reasons: list[str] = []
    if evidence.state and evidence.state not in EVIDENCE_STATES:
        blocked_reasons.append(f"invalid evidence state: {evidence.state}")
    if evidence.state in ("present", "failed") and not evidence.result_ref:
        missing = _merge_missing(missing, ("result_ref",))
    return _result(
        missing=missing,
        blocked_reasons=tuple(blocked_reasons),
        invalid_items=(),
        error_code=ErrorCode.EXECUTION_RECORD_INVALID,
        message="evidence record rejected",
    )



def validate_validation_evidence_record(validation: ValidationEvidenceRecord) -> DeliveryValidationResult:
    missing = _missing_fields(validation, ("validation_id", "evidence", "validated_at", "validator"))
    blocked_reasons: list[str] = []
    if validation.evidence:
        evidence_result = validate_evidence_record(validation.evidence)
        missing = _merge_missing(missing, evidence_result.missing_fields)
        blocked_reasons.extend(evidence_result.blocked_reasons)
    return _result(
        missing=missing,
        blocked_reasons=tuple(blocked_reasons),
        invalid_items=(),
        error_code=ErrorCode.EXECUTION_RECORD_INVALID,
        message="validation evidence record rejected",
    )
def validate_pr_mapping(mapping: PrMapping) -> DeliveryValidationResult:
    missing = _missing_fields(mapping, ("internal_id", "branch", "status"))
    blocked_reasons: list[str] = []
    if mapping.internal_id and not INTERNAL_PR_RE.match(mapping.internal_id):
        blocked_reasons.append("internal_id must use EDC-PR-###")
    if mapping.github_pr_number is not None:
        if not _is_positive_int(mapping.github_pr_number):
            blocked_reasons.append("github_pr_number must be a positive integer")
        if mapping.internal_id == str(mapping.github_pr_number):
            blocked_reasons.append("internal_id must not equal GitHub PR number")
        if mapping.internal_id == f"PR-{mapping.github_pr_number}":
            blocked_reasons.append("internal_id must not use GitHub PR number shape")
    return _result(
        missing=missing,
        blocked_reasons=tuple(blocked_reasons),
        invalid_items=(),
        error_code=ErrorCode.EXECUTION_RECORD_INVALID,
        message="PR mapping rejected",
    )


def validate_owner_uat_decision(decision: OwnerUatDecision) -> DeliveryValidationResult:
    missing = _missing_fields(decision, ("state", "owner_ref"))
    blocked_reasons: list[str] = []
    if decision.state and decision.state not in OWNER_UAT_STATES:
        blocked_reasons.append(f"invalid owner UAT state: {decision.state}")
    if decision.state in ("accepted_by_owner", "rejected_by_owner") and not decision.decision_ref:
        missing = _merge_missing(missing, ("decision_ref",))
    return _result(
        missing=missing,
        blocked_reasons=tuple(blocked_reasons),
        invalid_items=(),
        error_code=ErrorCode.MISSING_HUMAN_DECISION
        if decision.state in ("accepted_by_owner", "rejected_by_owner") and missing
        else ErrorCode.EXECUTION_RECORD_INVALID,
        message="owner UAT decision rejected",
    )


def validate_work_item(item: WorkItem) -> DeliveryValidationResult:
    missing = _missing_fields(
        item,
        (
            "work_item_id",
            "title",
            "status",
            "task_card",
            "project",
            "agent",
            "assignment",
            "runtime_authorization",
            "evidence",
            "validation",
            "pr_mapping",
            "owner_uat",
            "source_refs",
        ),
    )
    blocked_reasons: list[str] = []
    invalid_items: list[str] = []
    error_code = ErrorCode.EXECUTION_WORKPACKET_INVALID
    if item.status and item.status not in WORK_ITEM_STATUSES:
        blocked_reasons.append(f"invalid work item status: {item.status}")

    nested_results = _nested_validation_results(item)
    for nested in nested_results:
        if not nested.accepted:
            missing = _merge_missing(missing, nested.missing_fields)
            blocked_reasons.extend(nested.blocked_reasons)
            invalid_items.extend(nested.invalid_items)
            if nested.error_code == ErrorCode.NO_GO_BOUNDARY:
                error_code = ErrorCode.NO_GO_BOUNDARY

    aggregate_blockers = _work_item_aggregate_mismatches(item)
    if aggregate_blockers:
        blocked_reasons.extend(aggregate_blockers)
        error_code = ErrorCode.EXECUTION_RECORD_INVALID

    evidence_state = item.evidence.state if item.evidence else ""
    if item.status in REVIEW_EVIDENCE_STATUSES and evidence_state in ("missing", "stale"):
        blocked_reasons.append(f"{item.status} requires present, failed, or not_run_by_scope evidence")
        error_code = ErrorCode.EXECUTION_RECORD_INVALID

    owner_uat_state = item.owner_uat.state if item.owner_uat else ""
    if item.status == "done" and owner_uat_state not in ("accepted_by_owner", "not_applicable"):
        blocked_reasons.append("done requires owner UAT accepted_by_owner or not_applicable")
        error_code = ErrorCode.MISSING_HUMAN_DECISION

    assignment_reducer_owner = item.assignment.reducer_owner if item.assignment else ""
    if item.parallel_fanout_active and not (item.reducer_owner or assignment_reducer_owner):
        blocked_reasons.append("parallel fan-out requires reducer_owner")
        error_code = ErrorCode.EXECUTION_WORKPACKET_INVALID

    return _result(
        missing=missing,
        blocked_reasons=tuple(dict.fromkeys(blocked_reasons)),
        invalid_items=tuple(dict.fromkeys(invalid_items)),
        error_code=error_code,
        message="work item rejected",
    )


def _nested_validation_results(item: WorkItem) -> tuple[DeliveryValidationResult, ...]:
    results: list[DeliveryValidationResult] = []
    if item.task_card:
        results.append(validate_task_card(item.task_card))
    if item.project:
        results.append(validate_delivery_project(item.project))
    if item.agent:
        results.append(validate_agent_record(item.agent))
    if item.assignment:
        results.append(validate_assignment_record(item.assignment))
    if item.run:
        results.append(validate_run_record(item.run))
    if item.runtime_authorization:
        results.append(validate_runtime_authorization(item.runtime_authorization))
    if item.evidence:
        results.append(validate_evidence_record(item.evidence))
    if item.validation:
        results.append(validate_validation_evidence_record(item.validation))
    if item.pr_mapping:
        results.append(validate_pr_mapping(item.pr_mapping))
    if item.owner_uat:
        results.append(validate_owner_uat_decision(item.owner_uat))
    return tuple(results)


def _work_item_aggregate_mismatches(item: WorkItem) -> tuple[str, ...]:
    blocked_reasons: list[str] = []
    if item.assignment:
        if item.assignment.work_item_id and item.assignment.work_item_id != item.work_item_id:
            blocked_reasons.append("assignment.work_item_id must match work_item.work_item_id")
        if item.agent and item.assignment.agent_id and item.assignment.agent_id != item.agent.agent_id:
            blocked_reasons.append("assignment.agent_id must match agent.agent_id")
        if item.project:
            if item.assignment.branch and item.assignment.branch != item.project.active_branch:
                blocked_reasons.append("assignment.branch must match project.active_branch")
            if item.assignment.worktree_path and item.assignment.worktree_path != item.project.worktree_path:
                blocked_reasons.append("assignment.worktree_path must match project.worktree_path")
    if item.agent and item.assignment and item.agent.current_assignment_id:
        if item.agent.current_assignment_id != item.assignment.assignment_id:
            blocked_reasons.append("agent.current_assignment_id must match assignment.assignment_id")
    if item.pr_mapping and item.pr_mapping.internal_id and item.pr_mapping.internal_id != item.work_item_id:
        blocked_reasons.append("pr_mapping.internal_id must match work_item.work_item_id")
    if item.run:
        if item.run.work_item_id and item.run.work_item_id != item.work_item_id:
            blocked_reasons.append("run.work_item_id must match work_item.work_item_id")
        if item.project:
            if item.run.branch and item.run.branch != item.project.active_branch:
                blocked_reasons.append("run.branch must match project.active_branch")
            if item.run.worktree_path and item.run.worktree_path != item.project.worktree_path:
                blocked_reasons.append("run.worktree_path must match project.worktree_path")
    if item.validation and item.validation.evidence and item.evidence:
        if item.validation.evidence.evidence_id != item.evidence.evidence_id:
            blocked_reasons.append("validation.evidence.evidence_id must match work_item.evidence.evidence_id")
    return tuple(blocked_reasons)


def _result(
    *,
    missing: tuple[str, ...],
    blocked_reasons: tuple[str, ...],
    invalid_items: tuple[str, ...],
    error_code: ErrorCode,
    message: str,
) -> DeliveryValidationResult:
    if missing or blocked_reasons or invalid_items:
        return DeliveryValidationResult(
            False,
            error_code=error_code,
            message=message,
            missing_fields=missing,
            blocked_reasons=blocked_reasons,
            invalid_items=invalid_items,
        )
    return DeliveryValidationResult(True, message="delivery contract accepted")


def _missing_fields(item: object, field_names: tuple[str, ...]) -> tuple[str, ...]:
    missing: list[str] = []
    values = item.__dict__
    for field_name in field_names:
        if _field_missing(values, field_name):
            missing.append(field_name)
    return tuple(missing)


def _field_missing(values: dict[str, Any], field_name: str) -> bool:
    if field_name not in values:
        return True
    value = values[field_name]
    if value is None:
        return True
    if isinstance(value, str):
        return value == ""
    if isinstance(value, (dict, list, set, tuple)):
        return len(value) == 0
    return False


def _merge_missing(existing: tuple[str, ...], extra: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*existing, *extra)))


def _unsafe_paths(paths: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(path for path in paths if _is_unsafe_path(path))


def _is_unsafe_path(path: str) -> bool:
    normalized = path.replace("\\", "/").strip().lower()
    parts = tuple(part for part in normalized.split("/") if part)
    if not normalized:
        return False
    if any(part in (".git", "node_modules", ".edc-build") for part in parts):
        return True
    if "src-tauri/gen" in normalized:
        return True
    if any(part == ".env" or part.startswith(".env.") for part in parts):
        return True
    if any(part in ("private", "session", "sessions", "auth", "token", "tokens", "cache", "logs") for part in parts):
        return True
    if normalized.endswith((".sqlite", ".sqlite3", ".db", ".db3", ".log")):
        return True
    return False


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0
