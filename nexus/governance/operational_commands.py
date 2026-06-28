from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re

from .errors import ErrorCode


INTERNAL_PR_RE = re.compile(r"^EDC-PR-\d{3}$")
ALLOWED_PROVIDER_FAMILIES: tuple[str, ...] = ("codex", "local_stub", "openclaw")
ALLOWED_RUNTIME_STATUSES: tuple[str, ...] = (
    "available_for_draft",
    "inspection_only",
    "blocked",
    "offline",
)
ALLOWED_RUN_SESSION_STATES: tuple[str, ...] = ("draft_preview", "not_started", "blocked", "completed")
ALLOWED_EXECUTION_STATES: tuple[str, ...] = ("not_started", "draft_only", "blocked", "completed")
ALLOWED_COMMAND_TYPES: tuple[str, ...] = (
    "evaluate_assignment_candidate",
    "prepare_execution_handoff_draft",
    "request_owner_uat_decision_draft",
    "refresh_projection_draft",
    "record_validation_evidence_draft",
)
REJECTED_COMMAND_TYPES: tuple[str, ...] = (
    "start_runtime",
    "dispatch_live",
    "publish_nats",
    "install_dependency",
    "merge_pr",
    "accept_owner_uat",
    "promote_live_ready",
)
REQUIRED_BLOCKED_AUTHORITIES: tuple[str, ...] = (
    "live_dispatch",
    "runtime_startup",
    "dependency_install",
    "broker_nats_mutation",
    "merge_pr",
    "owner_uat_acceptance",
)


@dataclass(frozen=True)
class OperationalValidationResult:
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
class AgentDefinitionRecord:
    agent_id: str = ""
    display_name: str = ""
    role: str = ""
    capability_tags: tuple[str, ...] = ()
    authority_boundaries: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class RuntimeProviderProfile:
    provider_id: str = ""
    provider_family: str = ""
    display_name: str = ""
    capability_tags: tuple[str, ...] = ()
    executable: bool = False
    blocked_reason: str = ""
    source_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class RuntimeInstanceRecord:
    runtime_instance_id: str = ""
    provider_id: str = ""
    worktree_path: str = ""
    branch: str = ""
    status: str = ""
    readiness_state: str = ""
    startup_allowed: bool = False
    dependency_install_allowed: bool = False
    broker_mutation_allowed: bool = False
    live_dispatch_allowed: bool = False
    source_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class RunSessionRecord:
    run_session_id: str = ""
    work_item_id: str = ""
    agent_id: str = ""
    runtime_instance_id: str = ""
    session_state: str = ""
    execution_state: str = ""
    evidence_ref: str = ""
    source_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class OperationalCommandDraft:
    draft_id: str = ""
    command_type: str = ""
    work_item_id: str = ""
    github_pr_number: int | None = None
    target_agent_id: str = ""
    target_runtime_instance_id: str = ""
    run_session_id: str = ""
    draft_only: bool = True
    non_authoritative: bool = True
    required_approvals: tuple[str, ...] = ()
    blocked_authorities: tuple[str, ...] = ()
    evidence_requirements: tuple[str, ...] = ()
    handoff_preview_ref: str = ""
    write_back_location: str = ""
    source_refs: tuple[str, ...] = ()
    live_dispatch_claimed: bool = False
    runtime_startup_claimed: bool = False
    dependency_install_claimed: bool = False
    broker_mutation_claimed: bool = False
    merge_claimed: bool = False
    owner_uat_acceptance_claimed: bool = False
    production_readiness_claimed: bool = False
    live_readiness_claimed: bool = False


@dataclass(frozen=True)
class DispatchCandidateProjection:
    candidate_id: str = ""
    work_item_id: str = ""
    agent_id: str = ""
    runtime_instance_id: str = ""
    eligible: bool = False
    blocked_reasons: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class HandoffDraftPreview:
    preview_id: str = ""
    work_item_id: str = ""
    target_agent_id: str = ""
    target_runtime_instance_id: str = ""
    task_card_ref: str = ""
    write_back_location: str = ""
    validation_commands: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


def validate_agent_definition_record(agent: AgentDefinitionRecord) -> OperationalValidationResult:
    missing = _missing_fields(agent, ("agent_id", "display_name", "role", "capability_tags", "authority_boundaries", "source_refs"))
    blocked: list[str] = []
    if agent.agent_id and agent.agent_id.startswith(("runtime.", "run-session.")):
        blocked.append("agent_id must not use runtime or run session shape")
    if "owner_uat_acceptance" in agent.capability_tags:
        blocked.append("agent definition cannot claim owner UAT acceptance capability")
    return _result(missing=missing, blocked_reasons=tuple(blocked), invalid_items=(), message="agent definition rejected")


def validate_runtime_provider_profile(provider: RuntimeProviderProfile) -> OperationalValidationResult:
    missing = _missing_fields(provider, ("provider_id", "provider_family", "display_name", "capability_tags", "blocked_reason", "source_refs"))
    blocked: list[str] = []
    if provider.provider_family and provider.provider_family not in ALLOWED_PROVIDER_FAMILIES:
        blocked.append(f"unsupported runtime provider family: {provider.provider_family}")
    if provider.provider_family == "openclaw" and provider.executable:
        blocked.append("OpenClaw provider is reference-only in EDC-PR-011")
    if provider.executable:
        blocked.append("runtime provider must remain non-executable for command drafts")
    return _result(missing=missing, blocked_reasons=tuple(blocked), invalid_items=(), message="runtime provider rejected")


def validate_runtime_instance_record(
    instance: RuntimeInstanceRecord,
    *,
    provider: RuntimeProviderProfile | None = None,
) -> OperationalValidationResult:
    missing = _missing_fields(
        instance,
        ("runtime_instance_id", "provider_id", "worktree_path", "branch", "status", "readiness_state", "source_refs"),
    )
    blocked: list[str] = []
    invalid_items = list(_unsafe_paths((instance.worktree_path,)))
    if instance.status and instance.status not in ALLOWED_RUNTIME_STATUSES:
        blocked.append(f"unsupported runtime instance status: {instance.status}")
    if provider and instance.provider_id != provider.provider_id:
        blocked.append("runtime instance provider_id must match provider.provider_id")
    if instance.startup_allowed:
        blocked.append("runtime startup must remain blocked")
    if instance.dependency_install_allowed:
        blocked.append("dependency install must remain blocked")
    if instance.broker_mutation_allowed:
        blocked.append("broker/NATS mutation must remain blocked")
    if instance.live_dispatch_allowed:
        blocked.append("live dispatch must remain blocked")
    return _result(
        missing=missing,
        blocked_reasons=tuple(blocked),
        invalid_items=tuple(invalid_items),
        error_code=ErrorCode.NO_GO_BOUNDARY if invalid_items or blocked else ErrorCode.EXECUTION_RECORD_INVALID,
        message="runtime instance rejected",
    )


def validate_run_session_record(session: RunSessionRecord) -> OperationalValidationResult:
    missing = _missing_fields(
        session,
        ("run_session_id", "work_item_id", "agent_id", "runtime_instance_id", "session_state", "execution_state", "evidence_ref", "source_refs"),
    )
    blocked: list[str] = []
    if session.work_item_id and not INTERNAL_PR_RE.match(session.work_item_id):
        blocked.append("work_item_id must use EDC-PR-###")
    if session.run_session_id and session.run_session_id == session.agent_id:
        blocked.append("run_session_id must not equal agent_id")
    if session.run_session_id and session.run_session_id == session.runtime_instance_id:
        blocked.append("run_session_id must not equal runtime_instance_id")
    if session.session_state and session.session_state not in ALLOWED_RUN_SESSION_STATES:
        blocked.append(f"unsupported run session state: {session.session_state}")
    if session.execution_state and session.execution_state not in ALLOWED_EXECUTION_STATES:
        blocked.append(f"unsupported execution state: {session.execution_state}")
    return _result(missing=missing, blocked_reasons=tuple(blocked), invalid_items=(), message="run session rejected")


def validate_operational_command_draft(draft: OperationalCommandDraft) -> OperationalValidationResult:
    missing = _missing_fields(
        draft,
        (
            "draft_id",
            "command_type",
            "work_item_id",
            "target_agent_id",
            "target_runtime_instance_id",
            "run_session_id",
            "required_approvals",
            "blocked_authorities",
            "evidence_requirements",
            "handoff_preview_ref",
            "write_back_location",
            "source_refs",
        ),
    )
    blocked: list[str] = []
    if draft.command_type and draft.command_type not in ALLOWED_COMMAND_TYPES:
        blocked.append(f"unsupported command_type: {draft.command_type}")
    if draft.command_type in REJECTED_COMMAND_TYPES:
        blocked.append(f"rejected command_type crosses no-go boundary: {draft.command_type}")
    if draft.work_item_id:
        if not INTERNAL_PR_RE.match(draft.work_item_id):
            blocked.append("work_item_id must use EDC-PR-###")
        if draft.github_pr_number is not None and draft.work_item_id == str(draft.github_pr_number):
            blocked.append("work_item_id must not equal GitHub PR number")
    if not draft.draft_only:
        blocked.append("command draft must remain draft_only")
    if not draft.non_authoritative:
        blocked.append("command draft must remain non_authoritative")
    if draft.live_dispatch_claimed:
        blocked.append("command draft cannot claim live dispatch")
    if draft.runtime_startup_claimed:
        blocked.append("command draft cannot claim runtime startup")
    if draft.dependency_install_claimed:
        blocked.append("command draft cannot claim dependency install")
    if draft.broker_mutation_claimed:
        blocked.append("command draft cannot claim broker/NATS mutation")
    if draft.merge_claimed:
        blocked.append("command draft cannot claim merge")
    if draft.owner_uat_acceptance_claimed:
        blocked.append("command draft cannot claim owner UAT acceptance")
    if draft.production_readiness_claimed:
        blocked.append("command draft cannot claim production readiness")
    if draft.live_readiness_claimed:
        blocked.append("command draft cannot claim live readiness")
    for authority in REQUIRED_BLOCKED_AUTHORITIES:
        if authority not in draft.blocked_authorities:
            blocked.append(f"blocked_authorities must include {authority}")
    return _result(
        missing=missing,
        blocked_reasons=tuple(blocked),
        invalid_items=(),
        error_code=ErrorCode.NO_GO_BOUNDARY if blocked else ErrorCode.EXECUTION_COMMAND_INVALID,
        message="operational command draft rejected",
    )


def validate_dispatch_candidate_projection(candidate: DispatchCandidateProjection) -> OperationalValidationResult:
    missing = _missing_fields(candidate, ("candidate_id", "work_item_id", "agent_id", "runtime_instance_id", "blocked_reasons", "source_refs"))
    blocked: list[str] = []
    if candidate.eligible:
        blocked.append("dispatch candidate projection must remain ineligible/draft-only")
    if candidate.work_item_id and not INTERNAL_PR_RE.match(candidate.work_item_id):
        blocked.append("work_item_id must use EDC-PR-###")
    return _result(missing=missing, blocked_reasons=tuple(blocked), invalid_items=(), message="dispatch candidate rejected")


def validate_handoff_draft_preview(preview: HandoffDraftPreview) -> OperationalValidationResult:
    missing = _missing_fields(
        preview,
        (
            "preview_id",
            "work_item_id",
            "target_agent_id",
            "target_runtime_instance_id",
            "task_card_ref",
            "write_back_location",
            "validation_commands",
            "source_refs",
        ),
    )
    blocked: list[str] = []
    if preview.work_item_id and not INTERNAL_PR_RE.match(preview.work_item_id):
        blocked.append("work_item_id must use EDC-PR-###")
    return _result(missing=missing, blocked_reasons=tuple(blocked), invalid_items=(), message="handoff preview rejected")


def validate_agent_runtime_command_projection(
    *,
    agents: tuple[AgentDefinitionRecord, ...],
    runtime_providers: tuple[RuntimeProviderProfile, ...],
    runtime_instances: tuple[RuntimeInstanceRecord, ...],
    run_sessions: tuple[RunSessionRecord, ...],
    command_drafts: tuple[OperationalCommandDraft, ...],
    dispatch_candidates: tuple[DispatchCandidateProjection, ...],
    handoff_previews: tuple[HandoffDraftPreview, ...],
) -> OperationalValidationResult:
    missing: list[str] = []
    blocked: list[str] = []
    invalid_items: list[str] = []

    for field_name, records in (
        ("agents", agents),
        ("runtime_providers", runtime_providers),
        ("runtime_instances", runtime_instances),
        ("run_sessions", run_sessions),
        ("command_drafts", command_drafts),
        ("dispatch_candidates", dispatch_candidates),
        ("handoff_previews", handoff_previews),
    ):
        if not records:
            missing.append(field_name)

    providers_by_id = {provider.provider_id: provider for provider in runtime_providers}
    agent_ids = {agent.agent_id for agent in agents}
    runtime_ids = {runtime.runtime_instance_id for runtime in runtime_instances}
    session_ids = {session.run_session_id for session in run_sessions}
    sessions_by_id = {session.run_session_id: session for session in run_sessions}
    handoff_ids = {preview.preview_id for preview in handoff_previews}
    handoffs_by_id = {preview.preview_id: preview for preview in handoff_previews}
    command_work_item_ids = {draft.work_item_id for draft in command_drafts if draft.work_item_id}

    for agent in agents:
        _merge_result(validate_agent_definition_record(agent), missing, blocked, invalid_items)
    for provider in runtime_providers:
        _merge_result(validate_runtime_provider_profile(provider), missing, blocked, invalid_items)
    for instance in runtime_instances:
        _merge_result(validate_runtime_instance_record(instance, provider=providers_by_id.get(instance.provider_id)), missing, blocked, invalid_items)
    for session in run_sessions:
        _merge_result(validate_run_session_record(session), missing, blocked, invalid_items)
        if session.agent_id and session.agent_id not in agent_ids:
            blocked.append("run_session.agent_id must reference an agent definition")
        if session.runtime_instance_id and session.runtime_instance_id not in runtime_ids:
            blocked.append("run_session.runtime_instance_id must reference a runtime instance")
    for draft in command_drafts:
        _merge_result(validate_operational_command_draft(draft), missing, blocked, invalid_items)
        if draft.target_agent_id and draft.target_agent_id not in agent_ids:
            blocked.append("command draft target_agent_id must reference an agent definition")
        if draft.target_runtime_instance_id and draft.target_runtime_instance_id not in runtime_ids:
            blocked.append("command draft target_runtime_instance_id must reference a runtime instance")
        if draft.run_session_id and draft.run_session_id not in session_ids:
            blocked.append("command draft run_session_id must reference a run session")
        if draft.run_session_id in sessions_by_id and draft.work_item_id != sessions_by_id[draft.run_session_id].work_item_id:
            blocked.append("command draft work_item_id must match referenced run session")
        if draft.handoff_preview_ref and draft.handoff_preview_ref not in handoff_ids:
            blocked.append("command draft handoff_preview_ref must reference a handoff preview")
        if draft.handoff_preview_ref in handoffs_by_id and draft.work_item_id != handoffs_by_id[draft.handoff_preview_ref].work_item_id:
            blocked.append("command draft work_item_id must match referenced handoff preview")
    for candidate in dispatch_candidates:
        _merge_result(validate_dispatch_candidate_projection(candidate), missing, blocked, invalid_items)
        if candidate.work_item_id and command_work_item_ids and candidate.work_item_id not in command_work_item_ids:
            blocked.append("dispatch candidate work_item_id must match command draft work item")
        if candidate.agent_id and candidate.agent_id not in agent_ids:
            blocked.append("dispatch candidate agent_id must reference an agent definition")
        if candidate.runtime_instance_id and candidate.runtime_instance_id not in runtime_ids:
            blocked.append("dispatch candidate runtime_instance_id must reference a runtime instance")
    for preview in handoff_previews:
        _merge_result(validate_handoff_draft_preview(preview), missing, blocked, invalid_items)
        if preview.target_agent_id and preview.target_agent_id not in agent_ids:
            blocked.append("handoff preview target_agent_id must reference an agent definition")
        if preview.target_runtime_instance_id and preview.target_runtime_instance_id not in runtime_ids:
            blocked.append("handoff preview target_runtime_instance_id must reference a runtime instance")

    identity_overlaps = (
        (agent_ids & runtime_ids, "agent_id must not equal runtime_instance_id"),
        (agent_ids & session_ids, "run_session_id must not equal agent_id"),
        (runtime_ids & session_ids, "run_session_id must not equal runtime_instance_id"),
    )
    for overlap, message in identity_overlaps:
        if overlap:
            blocked.append(message)

    return _result(
        missing=tuple(missing),
        blocked_reasons=tuple(blocked),
        invalid_items=tuple(invalid_items),
        error_code=ErrorCode.NO_GO_BOUNDARY if blocked or invalid_items else ErrorCode.EXECUTION_RECORD_INVALID,
        message="agent runtime command projection rejected",
    )


def _merge_result(result: OperationalValidationResult, missing: list[str], blocked: list[str], invalid_items: list[str]) -> None:
    if result.accepted:
        return
    missing.extend(result.missing_fields)
    blocked.extend(result.blocked_reasons)
    invalid_items.extend(result.invalid_items)


def _result(
    *,
    missing: tuple[str, ...],
    blocked_reasons: tuple[str, ...],
    invalid_items: tuple[str, ...],
    message: str,
    error_code: ErrorCode = ErrorCode.EXECUTION_RECORD_INVALID,
) -> OperationalValidationResult:
    missing = tuple(dict.fromkeys(missing))
    blocked_reasons = tuple(dict.fromkeys(blocked_reasons))
    invalid_items = tuple(dict.fromkeys(invalid_items))
    if missing or blocked_reasons or invalid_items:
        return OperationalValidationResult(
            accepted=False,
            error_code=error_code,
            message=message,
            missing_fields=missing,
            blocked_reasons=blocked_reasons,
            invalid_items=invalid_items,
        )
    return OperationalValidationResult(True, message="operational command projection accepted")


def _missing_fields(item: object, field_names: tuple[str, ...]) -> tuple[str, ...]:
    values = item.__dict__
    missing: list[str] = []
    for field_name in field_names:
        if _field_missing(values.get(field_name)):
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


def _unsafe_paths(paths: tuple[str, ...]) -> tuple[str, ...]:
    invalid: list[str] = []
    for path in paths:
        normalized = path.replace("\\", "/").strip().lower()
        if not normalized:
            continue
        if any(part in normalized for part in (".git/", ".env", "node_modules", "src-tauri/gen", ".edc-build", "private", "session/auth", "token", "cache/", "logs/")):
            invalid.append(path)
        if normalized.endswith((".sqlite", ".sqlite3", ".db", ".log")):
            invalid.append(path)
    return tuple(dict.fromkeys(invalid))
