from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .errors import ErrorCode
from .kernel import GovernanceKernel, TransitionResult
from .schemas import ActorRef, CommandEnvelope, ValidationResult, validate_command_envelope


REQUIRED_SURFACE_FIELDS: tuple[str, ...] = (
    "readme_path",
    "charter_path",
    "stakeholder_authority_path",
    "evidence_path",
    "decision_log_path",
    "feedback_path",
    "review_evidence_path",
    "planning_scope_path",
    "planning_requirements_path",
    "planning_risk_path",
    "planning_dependency_path",
    "planning_backlog_wbs_path",
    "planning_execution_plan_path",
)

ALLOWED_OUTPUT_STATUSES: tuple[str, ...] = (
    "draft",
    "seed",
    "structural",
    "evidence_candidate",
    "baseline_submitted",
    "kernel_accepted",
    "blocked",
)

DISALLOWED_SELF_AUTHORIZING_STATUSES: tuple[str, ...] = (
    "approved",
    "accepted",
    "plan_approved",
    "baseline_approved",
    "complete",
    "final_pass",
)

ALLOWED_MANIFEST_STATUSES: tuple[str, ...] = (
    "draft",
    "validated",
    "kernel_submitted",
    "initiation_ready",
    "blocked",
    "superseded",
)

PLANNING_CONTENT_KEYS: tuple[str, ...] = (
    "scope_baseline",
    "wbs_backlog",
    "risk_register",
    "dependency_map",
    "execution_plan_candidate",
)

APPROVED_TEMPLATE_PROFILE_REFS: tuple[str, ...] = ("workspace-template:standard-init:v1",)
WORKSPACE_INIT_COMMAND_TYPES: tuple[str, ...] = (
    "CreateWorkspaceCandidate",
    "ValidateWorkspaceManifest",
    "SubmitWorkspaceInitRecord",
)


@dataclass(frozen=True)
class WorkspaceValidationResult:
    accepted: bool
    error_code: ErrorCode | None = None
    message: str = ""
    missing_paths: tuple[str, ...] = ()
    invalid_items: tuple[str, ...] = ()
    blocked_reasons: tuple[str, ...] = ()

    def to_evidence(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "blocked_reasons": list(self.blocked_reasons),
            "error_code": self.error_code.value if self.error_code else None,
            "invalid_items": list(self.invalid_items),
            "message": self.message,
            "missing_paths": list(self.missing_paths),
        }


@dataclass(frozen=True)
class WorkspaceInitOutputBase:
    item_id: str
    item_type: str
    project_id: str
    workspace_id: str
    source_authority_refs: tuple[str, ...]
    status: str
    owning_component: str
    consumer_component_refs: tuple[str, ...]
    notes: str = ""
    created_by_component: str = "Workspace Init"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    content: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TemplateProfileSelection:
    profile_id: str
    profile_version: str
    profile_source_ref: str
    trim_rules_applied: tuple[str, ...]
    required_surface_exceptions: tuple[str, ...]
    selection_reason: str


@dataclass(frozen=True)
class InitiationTemplateSet:
    template_set_ref: str
    required_templates: tuple[str, ...]
    required_surfaces: tuple[str, ...]
    trim_rules: tuple[str, ...]
    source_refs: tuple[str, ...]


@dataclass(frozen=True)
class GovernanceSurfaceIndex:
    surface_index_id: str
    workspace_root: str
    readme_path: str
    charter_path: str
    stakeholder_authority_path: str
    evidence_path: str
    decision_log_path: str
    feedback_path: str
    review_evidence_path: str
    planning_scope_path: str
    planning_requirements_path: str
    planning_risk_path: str
    planning_dependency_path: str
    planning_backlog_wbs_path: str
    planning_execution_plan_path: str

    def required_surface_names(self) -> tuple[str, ...]:
        return REQUIRED_SURFACE_FIELDS

    def required_paths(self) -> tuple[str, ...]:
        return tuple(path for path in (getattr(self, name) for name in REQUIRED_SURFACE_FIELDS) if path)


@dataclass(frozen=True)
class WorkspaceManifest:
    manifest_id: str
    workspace_id: str
    workspace_root: str
    manifest_version: int
    created_paths: tuple[str, ...]
    seed_items: tuple[WorkspaceInitOutputBase, ...]
    template_profile_ref: str
    validation_report_ref: str
    baseline_entry_command_ref: str
    kernel_record_ref: str | None
    status: str
    source_refs: tuple[str, ...]
    surface_index: GovernanceSurfaceIndex


def validate_template_profile(
    selection: TemplateProfileSelection, template_set: InitiationTemplateSet
) -> WorkspaceValidationResult:
    blocked_reasons: list[str] = []
    if selection.profile_source_ref not in APPROVED_TEMPLATE_PROFILE_REFS:
        blocked_reasons.append(f"unknown template profile: {selection.profile_source_ref}")
    if selection.profile_source_ref != template_set.template_set_ref:
        blocked_reasons.append("template profile and template set mismatch")
    for rule in tuple(selection.trim_rules_applied) + tuple(template_set.trim_rules):
        if rule in REQUIRED_SURFACE_FIELDS or rule in template_set.required_surfaces:
            blocked_reasons.append(f"required governance surface cannot be trimmed: {rule}")
            break
    if selection.required_surface_exceptions:
        blocked_reasons.append("required governance surface exceptions require authority-approved deferral")
    if not template_set.source_refs:
        blocked_reasons.append("template set source refs are required")
    if blocked_reasons:
        return WorkspaceValidationResult(
            False,
            ErrorCode.WORKSPACE_TEMPLATE_INVALID,
            message="workspace template profile rejected",
            blocked_reasons=tuple(blocked_reasons),
        )
    return WorkspaceValidationResult(True, message="workspace template profile accepted")


def validate_workspace_manifest(manifest: WorkspaceManifest) -> WorkspaceValidationResult:
    missing_paths: list[str] = []
    invalid_items: list[str] = []
    blocked_reasons: list[str] = []
    created_paths = {_normalize_path(path) for path in manifest.created_paths}
    workspace_root = _normalize_path(manifest.workspace_root)

    if manifest.manifest_version < 1:
        blocked_reasons.append("manifest_version must be positive")
    if not manifest.source_refs:
        blocked_reasons.append("source refs are required")
    if manifest.status not in ALLOWED_MANIFEST_STATUSES:
        blocked_reasons.append(f"invalid workspace manifest status: {manifest.status}")
    if manifest.surface_index.workspace_root != manifest.workspace_root:
        blocked_reasons.append("surface index workspace_root mismatch")

    for field_name in REQUIRED_SURFACE_FIELDS:
        path = getattr(manifest.surface_index, field_name)
        normalized = _normalize_path(path)
        if not path or normalized not in created_paths:
            missing_paths.append(field_name)
            continue
        if not _is_within_workspace(normalized, workspace_root):
            blocked_reasons.append(f"required path is outside workspace root: {field_name}")

    for item in manifest.seed_items:
        if not _has_required_base_fields(item):
            invalid_items.append(item.item_id)
            continue
        if item.status in DISALLOWED_SELF_AUTHORIZING_STATUSES or item.status not in ALLOWED_OUTPUT_STATUSES:
            invalid_items.append(item.item_id)
        if item.item_type == "PlanningSurfacePlaceholder" and any(key in item.content for key in PLANNING_CONTENT_KEYS):
            blocked_reasons.append("planning content is out of scope for Workspace Init")

    if manifest.status in ("kernel_submitted", "initiation_ready", "kernel_accepted") and not manifest.kernel_record_ref:
        blocked_reasons.append("kernel_record_ref is required after Kernel submission")

    if missing_paths or invalid_items or blocked_reasons:
        return WorkspaceValidationResult(
            False,
            ErrorCode.WORKSPACE_MANIFEST_INVALID,
            message="workspace manifest rejected",
            missing_paths=tuple(missing_paths),
            invalid_items=tuple(invalid_items),
            blocked_reasons=tuple(dict.fromkeys(blocked_reasons)),
        )
    return WorkspaceValidationResult(True, message="workspace manifest accepted")


def create_workspace_candidate_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    workspace_id: str,
    requested_project_ref: str,
    requested_root_path: str,
    template_profile_ref: str,
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="CreateWorkspaceCandidate",
        actor=actor,
        authority_refs=authority_refs,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        payload={
            "expected_version": expected_version,
            "idempotency_key": idempotency_key,
            "requested_project_ref": requested_project_ref,
            "requested_root_path": requested_root_path,
            "source_refs": authority_refs,
            "template_profile_ref": template_profile_ref,
            "workspace_id": workspace_id,
        },
    )


def validate_workspace_init_command(command: CommandEnvelope) -> ValidationResult:
    validation = validate_command_envelope(command)
    if not validation.accepted:
        return validation
    if command.command_type not in WORKSPACE_INIT_COMMAND_TYPES:
        return ValidationResult(False, ErrorCode.WORKSPACE_COMMAND_INVALID, "unknown Workspace Init command")
    required_fields = _required_payload_fields(command.command_type)
    for field_name in required_fields:
        if _payload_field_missing(command.payload, field_name):
            return ValidationResult(False, ErrorCode.WORKSPACE_COMMAND_INVALID, f"{field_name} is required")
    if "source_refs" in required_fields:
        source_refs = command.payload["source_refs"]
        if not isinstance(source_refs, (list, tuple)) or tuple(source_refs) != tuple(command.authority_refs):
            return ValidationResult(
                False,
                ErrorCode.WORKSPACE_COMMAND_INVALID,
                "source_refs must match authority_refs",
            )
    if "expected_version" in required_fields and not _is_non_negative_int(command.payload["expected_version"]):
        return ValidationResult(
            False,
            ErrorCode.WORKSPACE_COMMAND_INVALID,
            "expected_version must be a non-negative integer",
        )
    if "expected_version" in required_fields and not _payload_version_matches_envelope(command, "expected_version"):
        return ValidationResult(
            False,
            ErrorCode.WORKSPACE_COMMAND_INVALID,
            "payload expected_version must match envelope expected_version",
        )
    if "expected_kernel_version" in required_fields and not _is_non_negative_int(
        command.payload["expected_kernel_version"]
    ):
        return ValidationResult(
            False,
            ErrorCode.WORKSPACE_COMMAND_INVALID,
            "expected_kernel_version must be a non-negative integer",
        )
    if "expected_kernel_version" in required_fields and not _payload_version_matches_envelope(
        command, "expected_kernel_version"
    ):
        return ValidationResult(
            False,
            ErrorCode.WORKSPACE_COMMAND_INVALID,
            "payload expected_kernel_version must match envelope expected_version",
        )
    if "idempotency_key" in required_fields and command.payload["idempotency_key"] != command.idempotency_key:
        return ValidationResult(
            False,
            ErrorCode.WORKSPACE_COMMAND_INVALID,
            "payload idempotency_key must match envelope idempotency_key",
        )
    return ValidationResult(True)


def submit_workspace_init_record(
    kernel: GovernanceKernel,
    manifest: WorkspaceManifest,
    validation: WorkspaceValidationResult,
    actor: ActorRef,
    expected_version: int,
    authority_refs: tuple[str, ...],
    idempotency_key: str,
) -> TransitionResult:
    if not validation.accepted:
        return TransitionResult(
            False,
            kernel.state,
            error_code=validation.error_code or ErrorCode.WORKSPACE_MANIFEST_INVALID,
            message=validation.message,
        )
    command = CommandEnvelope(
        command_type="SubmitWorkspaceInitRecord",
        actor=actor,
        authority_refs=authority_refs,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        payload={
            "expected_kernel_version": expected_version,
            "manifest_ref": manifest.manifest_id,
            "source_refs": authority_refs,
            "validation_report_ref": manifest.validation_report_ref,
            "workspace_id": manifest.workspace_id,
        },
    )
    return kernel.apply(command)


def _required_payload_fields(command_type: str) -> tuple[str, ...]:
    if command_type == "CreateWorkspaceCandidate":
        return (
            "workspace_id",
            "requested_project_ref",
            "requested_root_path",
            "template_profile_ref",
            "source_refs",
            "expected_version",
            "idempotency_key",
        )
    if command_type == "ValidateWorkspaceManifest":
        return (
            "workspace_id",
            "manifest_id",
            "manifest_version",
            "required_surfaces",
            "source_refs",
            "expected_version",
        )
    if command_type == "SubmitWorkspaceInitRecord":
        return ("workspace_id", "manifest_ref", "validation_report_ref", "source_refs", "expected_kernel_version")
    return ()


def _payload_field_missing(payload: dict[str, Any], field_name: str) -> bool:
    if field_name not in payload:
        return True
    value = payload[field_name]
    if value is None:
        return True
    if isinstance(value, str):
        return value == ""
    if isinstance(value, (dict, list, set, tuple)):
        return len(value) == 0
    return False


def _is_non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _payload_version_matches_envelope(command: CommandEnvelope, payload_field: str) -> bool:
    return _is_non_negative_int(command.expected_version) and command.payload[payload_field] == command.expected_version


def _has_required_base_fields(item: WorkspaceInitOutputBase) -> bool:
    return all(
        (
            item.item_id,
            item.item_type,
            item.project_id,
            item.workspace_id,
            item.source_authority_refs,
            item.created_by_component == "Workspace Init",
            item.status,
            item.owning_component,
            item.consumer_component_refs,
        )
    )


def _normalize_path(path: str) -> str:
    return path.strip().replace("\\", "/").rstrip("/")


def _is_within_workspace(path: str, workspace_root: str) -> bool:
    return path == workspace_root or path.startswith(f"{workspace_root}/")
