from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .delivery_contracts import (
    AssignmentRecord,
    RuntimeAuthorization,
    TaskCard,
    WorkItem,
    validate_assignment_record,
    validate_runtime_authorization,
    validate_task_card,
)
from .errors import ErrorCode


VALIDATION_RESULT_STATUSES: tuple[str, ...] = ("passed", "failed", "not_run")
PR_READINESS_STATES: tuple[str, ...] = ("not_ready", "ready_for_pr", "blocked")
VALIDATION_EVIDENCE_STATES: tuple[str, ...] = ("missing", "stale", "present", "failed", "not_run_by_scope")
FRESH_COMPLETION_EVIDENCE_STATES: tuple[str, ...] = ("present", "not_run_by_scope")
STALE_COMPLETION_EVIDENCE_STATES: tuple[str, ...] = ("missing", "stale")
RUNTIME_COMMAND_MARKERS: tuple[str, ...] = (
    "broker",
    "cargo",
    "controller",
    "dependency install",
    "dispatch",
    "live dispatch",
    "nats",
    "npm install",
    "npm run dev",
    "pip install",
    "pnpm",
    "runtime startup",
    "tauri",
)


@dataclass(frozen=True)
class HandoffValidationResult:
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
class PlanningExecutionHandoff:
    handoff_id: str = ""
    work_item_id: str = ""
    branch: str = ""
    worktree_path: str = ""
    task_card: TaskCard | None = None
    assignment: AssignmentRecord | None = None
    runtime_authorization: RuntimeAuthorization | None = None
    editable_scope: tuple[str, ...] = ()
    runtime_command_claims: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    write_back_location: str = ""


@dataclass(frozen=True)
class ValidationCommandResult:
    command: str = ""
    exit_code: int | None = None
    status: str = ""
    evidence_state: str = ""
    evidence_ref: str = ""
    not_run_reason: str = ""


@dataclass(frozen=True)
class ExecutionCompletionReport:
    report_id: str = ""
    handoff_id: str = ""
    work_item_id: str = ""
    branch: str = ""
    worktree_path: str = ""
    changed_files: tuple[str, ...] = ()
    validation_results: tuple[ValidationCommandResult, ...] = ()
    blockers: tuple[str, ...] = ()
    residual_risks: tuple[str, ...] = ()
    pr_readiness: str = "not_ready"
    pr_mapping_ready: bool = False
    runtime_command_claims: tuple[str, ...] = ()
    owner_uat_state: str = "not_ready"
    source_refs: tuple[str, ...] = ()
    report_ref: str = ""


def validate_handoff_packet(
    handoff: PlanningExecutionHandoff,
    *,
    work_item: WorkItem | None = None,
) -> HandoffValidationResult:
    missing = _missing_fields(
        handoff,
        (
            "handoff_id",
            "work_item_id",
            "branch",
            "worktree_path",
            "task_card",
            "assignment",
            "runtime_authorization",
            "editable_scope",
            "source_refs",
            "write_back_location",
        ),
    )
    blocked_reasons: list[str] = []
    invalid_items: list[str] = []
    error_code = ErrorCode.EXECUTION_WORKPACKET_INVALID

    if handoff.task_card is not None:
        task_card_result = validate_task_card(handoff.task_card)
        missing = _merge_unique(missing, task_card_result.missing_fields)
        blocked_reasons.extend(task_card_result.blocked_reasons)
        invalid_items.extend(task_card_result.invalid_items)
    if handoff.assignment is not None:
        assignment_result = validate_assignment_record(handoff.assignment)
        missing = _merge_unique(missing, _prefix_fields("assignment", assignment_result.missing_fields))
        blocked_reasons.extend(assignment_result.blocked_reasons)
    if handoff.runtime_authorization is not None:
        runtime_result = validate_runtime_authorization(handoff.runtime_authorization)
        missing = _merge_unique(missing, _prefix_fields("runtime_authorization", runtime_result.missing_fields))
        blocked_reasons.extend(runtime_result.blocked_reasons)

    _append_handoff_consistency_blockers(handoff, work_item, blocked_reasons)
    runtime_blockers = _runtime_command_blockers(handoff.runtime_command_claims, handoff.runtime_authorization)
    blocked_reasons.extend(runtime_blockers)
    if runtime_blockers:
        error_code = ErrorCode.NO_GO_BOUNDARY

    return _handoff_result(
        missing,
        blocked_reasons,
        invalid_items,
        error_code=error_code,
        accepted_message="handoff packet accepted",
        rejected_message="handoff packet rejected",
    )


def validate_validation_command_result(result: ValidationCommandResult) -> HandoffValidationResult:
    missing = _missing_fields(result, ("command", "status", "evidence_state"))
    blocked_reasons: list[str] = []
    if result.status and result.status not in VALIDATION_RESULT_STATUSES:
        blocked_reasons.append(f"invalid validation result status: {result.status}")
    if result.evidence_state and result.evidence_state not in VALIDATION_EVIDENCE_STATES:
        blocked_reasons.append(f"invalid validation evidence state: {result.evidence_state}")
    if result.status == "passed":
        if result.exit_code != 0:
            blocked_reasons.append("passed validation result requires exit_code 0")
        if result.evidence_state != "present":
            blocked_reasons.append("passed validation result requires present evidence")
        if not result.evidence_ref:
            missing = _merge_unique(missing, ("evidence_ref",))
    if result.status == "failed":
        if result.exit_code is None or result.exit_code == 0:
            blocked_reasons.append("failed validation result requires non-zero exit_code")
        if result.evidence_state != "failed":
            blocked_reasons.append("failed validation result requires failed evidence")
        if not result.evidence_ref:
            missing = _merge_unique(missing, ("evidence_ref",))
    if result.status == "not_run":
        if result.evidence_state != "not_run_by_scope":
            blocked_reasons.append("not_run validation result requires not_run_by_scope evidence")
        if not result.not_run_reason:
            missing = _merge_unique(missing, ("not_run_reason",))
    if result.evidence_state == "not_run_by_scope" and result.status != "not_run":
        blocked_reasons.append("not_run_by_scope evidence requires not_run status")
    return _handoff_result(
        missing,
        blocked_reasons,
        [],
        error_code=ErrorCode.EXECUTION_RECORD_INVALID,
        accepted_message="validation command result accepted",
        rejected_message="validation command result rejected",
    )


def validate_completion_report(
    report: ExecutionCompletionReport,
    *,
    handoff: PlanningExecutionHandoff | None = None,
    work_item: WorkItem | None = None,
) -> HandoffValidationResult:
    missing = _missing_fields(
        report,
        (
            "report_id",
            "handoff_id",
            "work_item_id",
            "branch",
            "worktree_path",
            "changed_files",
            "validation_results",
            "source_refs",
            "report_ref",
        ),
    )
    blocked_reasons: list[str] = []
    invalid_items: list[str] = []
    error_code = ErrorCode.EXECUTION_RECORD_INVALID

    if report.pr_readiness not in PR_READINESS_STATES:
        blocked_reasons.append(f"invalid PR readiness state: {report.pr_readiness}")
    for validation_result in report.validation_results:
        result = validate_validation_command_result(validation_result)
        missing = _merge_unique(missing, _prefix_fields("validation_results", result.missing_fields))
        blocked_reasons.extend(result.blocked_reasons)

    _append_report_consistency_blockers(report, handoff, work_item, blocked_reasons)
    invalid_items.extend(_changed_files_outside_boundaries(report.changed_files, handoff))
    invalid_items.extend(_unsafe_paths(report.changed_files))
    if invalid_items:
        error_code = ErrorCode.NO_GO_BOUNDARY

    runtime_auth = handoff.runtime_authorization if handoff else None
    runtime_blockers = _runtime_command_blockers(report.runtime_command_claims, runtime_auth)
    blocked_reasons.extend(runtime_blockers)
    if runtime_blockers:
        error_code = ErrorCode.NO_GO_BOUNDARY

    if _claims_pr_readiness(report):
        blocked_reasons.extend(_readiness_evidence_blockers(report, "PR readiness"))
    if report.pr_mapping_ready:
        blocked_reasons.extend(_readiness_evidence_blockers(report, "PR mapping readiness"))
    if report.owner_uat_state == "accepted_by_owner":
        blocked_reasons.append("completion report cannot claim owner UAT acceptance")

    return _handoff_result(
        missing,
        blocked_reasons,
        invalid_items,
        error_code=error_code,
        accepted_message="completion report accepted",
        rejected_message="completion report rejected",
    )


def _append_handoff_consistency_blockers(
    handoff: PlanningExecutionHandoff,
    work_item: WorkItem | None,
    blocked_reasons: list[str],
) -> None:
    assignment = handoff.assignment
    if assignment:
        if handoff.work_item_id != assignment.work_item_id:
            blocked_reasons.append("handoff.work_item_id must match assignment.work_item_id")
        if handoff.branch != assignment.branch:
            blocked_reasons.append("handoff.branch must match assignment.branch")
        if _normalize_path(handoff.worktree_path) != _normalize_path(assignment.worktree_path):
            blocked_reasons.append("handoff.worktree_path must match assignment.worktree_path")
    if not work_item:
        return
    if handoff.work_item_id != work_item.work_item_id:
        blocked_reasons.append("handoff.work_item_id must match work_item.work_item_id")
    if handoff.branch != work_item.project.active_branch:
        blocked_reasons.append("handoff.branch must match project.active_branch")
    if _normalize_path(handoff.worktree_path) != _normalize_path(work_item.project.worktree_path):
        blocked_reasons.append("handoff.worktree_path must match project.worktree_path")


def _append_report_consistency_blockers(
    report: ExecutionCompletionReport,
    handoff: PlanningExecutionHandoff | None,
    work_item: WorkItem | None,
    blocked_reasons: list[str],
) -> None:
    if handoff:
        if report.handoff_id != handoff.handoff_id:
            blocked_reasons.append("report.handoff_id must match handoff.handoff_id")
        if report.work_item_id != handoff.work_item_id:
            blocked_reasons.append("report.work_item_id must match handoff.work_item_id")
        if report.branch != handoff.branch:
            blocked_reasons.append("report.branch must match handoff.branch")
        if _normalize_path(report.worktree_path) != _normalize_path(handoff.worktree_path):
            blocked_reasons.append("report.worktree_path must match handoff.worktree_path")
    if not work_item:
        return
    if report.work_item_id != work_item.work_item_id:
        blocked_reasons.append("report.work_item_id must match work_item.work_item_id")
    if report.branch != work_item.project.active_branch:
        blocked_reasons.append("report.branch must match project.active_branch")
    if _normalize_path(report.worktree_path) != _normalize_path(work_item.project.worktree_path):
        blocked_reasons.append("report.worktree_path must match project.worktree_path")


def _runtime_command_blockers(
    commands: tuple[str, ...],
    authorization: RuntimeAuthorization | None,
) -> list[str]:
    blockers: list[str] = []
    if not commands:
        return blockers
    state = authorization.state if authorization else ""
    named_command = authorization.named_command if authorization else ""
    for command in commands:
        if not _is_runtime_command(command):
            continue
        if state != "authorized_for_named_command":
            blockers.append(f"runtime command claim requires authorized_for_named_command: {command}")
        elif command != named_command:
            blockers.append(f"runtime command claim must match authorized named command: {command}")
    return blockers


def _changed_files_outside_boundaries(
    changed_files: tuple[str, ...],
    handoff: PlanningExecutionHandoff | None,
) -> tuple[str, ...]:
    if not changed_files or handoff is None:
        return ()
    boundaries = tuple(handoff.editable_scope)
    if handoff.task_card is not None:
        boundaries = boundaries + tuple(handoff.task_card.file_boundaries)
    return tuple(path for path in changed_files if not _path_matches_any_boundary(path, boundaries))


def _path_matches_any_boundary(path: str, boundaries: tuple[str, ...]) -> bool:
    normalized = _normalize_repo_path(path)
    for boundary in boundaries:
        candidate = _normalize_repo_path(boundary)
        if candidate.endswith("/**"):
            if normalized.startswith(candidate[:-3].rstrip("/") + "/"):
                return True
        elif candidate.endswith("/*"):
            prefix = candidate[:-2].rstrip("/") + "/"
            remainder = normalized.removeprefix(prefix)
            if normalized.startswith(prefix) and "/" not in remainder:
                return True
        elif normalized == candidate:
            return True
        elif normalized.startswith(candidate.rstrip("/") + "/"):
            return True
    return False


def _unsafe_paths(paths: tuple[str, ...]) -> tuple[str, ...]:
    unsafe_markers = (
        ".edc-build",
        ".env",
        ".git/",
        "auth/",
        "cache/",
        "cookies",
        "logs/",
        "node_modules/",
        "private-session",
        "session/",
        "sqlite",
        "src-tauri/gen/",
        "token",
    )
    invalid: list[str] = []
    for path in paths:
        normalized = _normalize_repo_path(path).lower()
        if normalized == ".git" or any(marker in normalized for marker in unsafe_markers):
            invalid.append(path)
    return tuple(invalid)


def _claims_pr_readiness(report: ExecutionCompletionReport) -> bool:
    return report.pr_readiness == "ready_for_pr"


def _readiness_evidence_blockers(report: ExecutionCompletionReport, label: str) -> list[str]:
    blockers: list[str] = []
    if report.blockers:
        blockers.append(f"{label} cannot be claimed while blockers are present")
    if any(result.status == "failed" for result in report.validation_results):
        blockers.append(f"{label} requires all validation commands to pass")
    if not _has_fresh_or_scope_exempt_evidence(report):
        blockers.append(f"{label} requires fresh evidence or explicit not_run_by_scope")
    return blockers


def _has_fresh_or_scope_exempt_evidence(report: ExecutionCompletionReport) -> bool:
    if not report.validation_results:
        return False
    return all(_result_is_fresh_or_scope_exempt(result) for result in report.validation_results)


def _result_is_fresh_or_scope_exempt(result: ValidationCommandResult) -> bool:
    if result.status == "passed":
        return result.exit_code == 0 and result.evidence_state == "present" and bool(result.evidence_ref)
    if result.status == "not_run":
        return result.evidence_state == "not_run_by_scope" and bool(result.not_run_reason)
    return False


def _is_runtime_command(command: str) -> bool:
    lowered = command.lower()
    return any(marker in lowered for marker in RUNTIME_COMMAND_MARKERS)


def _handoff_result(
    missing: tuple[str, ...],
    blocked_reasons: list[str],
    invalid_items: list[str],
    *,
    error_code: ErrorCode,
    accepted_message: str,
    rejected_message: str,
) -> HandoffValidationResult:
    blocked = tuple(dict.fromkeys(blocked_reasons))
    invalid = tuple(dict.fromkeys(invalid_items))
    if missing or blocked or invalid:
        return HandoffValidationResult(
            False,
            error_code,
            message=rejected_message,
            missing_fields=missing,
            blocked_reasons=blocked,
            invalid_items=invalid,
        )
    return HandoffValidationResult(True, message=accepted_message)


def _missing_fields(item: object, field_names: tuple[str, ...]) -> tuple[str, ...]:
    missing: list[str] = []
    for field_name in field_names:
        if _field_missing(getattr(item, field_name)):
            missing.append(field_name)
    return tuple(missing)


def _field_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value == ""
    if isinstance(value, (dict, list, set, tuple)):
        return len(value) == 0
    return False


def _prefix_fields(prefix: str, fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(f"{prefix}.{field}" for field in fields)


def _merge_unique(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(left + right))


def _normalize_repo_path(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("./")


def _normalize_path(path: str) -> str:
    return path.replace("/", "\\").rstrip("\\").lower()
