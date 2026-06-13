from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .errors import ErrorCode
from .projections import FreshnessState, ProjectionSnapshot
from .schemas import ActorRef, CommandEnvelope, ValidationResult
from .service_facade import CommandDraft, ServiceCommandOutcome


SERVICE_STATES: tuple[str, ...] = ("connected", "degraded", "offline")
PROJECTION_FRESHNESS_STATES: tuple[str, ...] = ("current", "stale", "rebuilding", "failed", "fresh")
SYNC_STATES: tuple[str, ...] = ("ok", "warning", "blocked")
LOCAL_APP_MODULES: tuple[str, ...] = (
    "app_start",
    "mission_control",
    "standardization",
    "monitor_hitl",
    "delivery_feedback",
    "settings_sources",
    "notes_evidence",
)
COMMAND_SURFACES: tuple[str, ...] = (
    "menu",
    "toolbar",
    "header",
    "inspector",
    "command_palette",
    "workspace_picker",
)
SERVICE_COMMAND_TYPES: tuple[str, ...] = ("", "SubmitCommandDraft", "RefreshProjection")
WORKSPACE_PICKER_TRIGGERS: tuple[str, ...] = (
    "header_workspace_dropdown",
    "file_open_workspace",
    "workspace_switch",
    "app_start_open_existing",
    "command_palette",
)
WORKSPACE_PICKER_MODES: tuple[str, ...] = (
    "temporary_overlay",
    "projection_overlay",
    "popover",
    "modal",
    "sheet",
    "temporary_subview",
)
WORKSPACE_OPEN_MODES: tuple[str, ...] = ("normal", "read_only_preview")
WORKSPACE_PICKER_ACTIONS: tuple[str, ...] = ("open", "open_read_only", "create_workspace_candidate", "cancel")
MENU_GROUPS: tuple[str, ...] = (
    "File",
    "Project",
    "Workspace",
    "View",
    "Monitor/HITL",
    "Delivery Feedback",
    "Agents",
    "Settings",
    "Help",
)
STALE_AFFORDANCES: tuple[str, ...] = ("show_stale_chip", "request_rebuild", "blocked_until_rebuild", "none")

APP_SHELL_FORBIDDEN_TERMS: tuple[str, ...] = (
    "electron selected",
    "tauri selected",
    "framework selected",
    "browser route",
    "server url",
    "server_url",
    "server selection",
    "database",
    "local database",
    "database selection",
    "api schema",
    "api schema selected",
    "api schema selection",
    "runtime transport",
    "ipc channel",
    "package dependency",
    "package manager",
    "desktop app project",
    "web frontend",
    "native shell",
    "view model authority",
    "projection authority",
    "projection is canonical authority",
    "cache authority",
    "source of truth",
    "direct canonical mutation",
    "write baseline from ui",
    "mark no go from ui",
    "approve now",
    "local app approves",
    "complete project",
    "local app completes",
    "archive workspace",
    "mark baseline",
    "no go decision",
    "no-go decision",
    "production readiness",
    "production ready",
    "mark production ready",
    "deploy",
    "deploy now",
    "continuity activation",
    "activate continuity",
    "final pass",
    "runtime invocation",
    "private agent invocation",
    "private-agent invocation",
    "dispatch execution",
    "execute dispatch",
    "route activation",
    "adapter call",
    "transport call",
    "workpacket execution",
    "persistent workspace explorer",
    "permanent left workspace rail",
    "workspace selection writes canonical state",
)


@dataclass(frozen=True)
class LocalAppViewModel:
    workspace_id: str
    read_only: bool
    workspace_picker_mode: str
    workspace_picker_creates_authority: bool
    disabled_commands: tuple[str, ...]
    freshness_chips: tuple[str, ...]
    framework: str | None = None

    def to_evidence(self) -> dict[str, Any]:
        return {
            "disabled_commands": list(self.disabled_commands),
            "framework": self.framework,
            "freshness_chips": list(self.freshness_chips),
            "read_only": self.read_only,
            "workspace_id": self.workspace_id,
            "workspace_picker_creates_authority": self.workspace_picker_creates_authority,
            "workspace_picker_mode": self.workspace_picker_mode,
        }


@dataclass(frozen=True)
class CommandAffordance:
    command_id: str
    label: str
    module_id: str
    surface: str
    creates_command_draft: bool
    service_command_type: str
    requires_human_decision: bool
    disabled: bool
    disabled_reason: str
    source_refs: tuple[str, ...]
    payload: dict[str, Any] = field(default_factory=dict)

    def to_evidence(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "creates_command_draft": self.creates_command_draft,
            "disabled": self.disabled,
            "disabled_reason": self.disabled_reason,
            "label": self.label,
            "module_id": self.module_id,
            "payload": self.payload,
            "requires_human_decision": self.requires_human_decision,
            "service_command_type": self.service_command_type,
            "source_refs": list(self.source_refs),
            "surface": self.surface,
        }


@dataclass(frozen=True)
class LocalDesktopShellViewModel:
    workspace_id: str
    workspace_display_name: str
    read_only_preview: bool
    show_archived_parked: bool
    service_state: str
    projection_freshness: str
    sync_state: str
    kernel_source_ref: str
    active_module: str
    module_navigation: tuple[str, ...]
    header_actions: tuple[CommandAffordance, ...]
    disabled_commands: tuple[str, ...]
    toolbar: tuple[CommandAffordance, ...]
    inspector: dict[str, Any]
    status_bar: dict[str, Any]
    framework: str | None = None
    persistent_workspace_explorer: bool = False
    canonical_authority: bool = False

    def to_evidence(self) -> dict[str, Any]:
        return {
            "active_module": self.active_module,
            "canonical_authority": self.canonical_authority,
            "disabled_commands": list(self.disabled_commands),
            "framework": self.framework,
            "header_actions": [item.to_evidence() for item in self.header_actions],
            "inspector": self.inspector,
            "kernel_source_ref": self.kernel_source_ref,
            "module_navigation": list(self.module_navigation),
            "persistent_workspace_explorer": self.persistent_workspace_explorer,
            "projection_freshness": self.projection_freshness,
            "read_only_preview": self.read_only_preview,
            "service_state": self.service_state,
            "show_archived_parked": self.show_archived_parked,
            "status_bar": self.status_bar,
            "sync_state": self.sync_state,
            "toolbar": [item.to_evidence() for item in self.toolbar],
            "workspace_display_name": self.workspace_display_name,
            "workspace_id": self.workspace_id,
        }


@dataclass(frozen=True)
class WorkspacePickerOverlayViewModel:
    overlay_id: str
    trigger: str
    mode: str
    open_mode: str
    show_archived_parked: bool
    current_workspace_ref: str
    recent_workspace_refs: tuple[str, ...]
    active_workspace_refs: tuple[str, ...]
    archived_or_parked_workspace_refs: tuple[str, ...]
    freshness_by_workspace: dict[str, str]
    actions: tuple[str, ...]
    creates_authority: bool
    persistent_left_rail: bool

    def to_evidence(self) -> dict[str, Any]:
        return {
            "actions": list(self.actions),
            "active_workspace_refs": list(self.active_workspace_refs),
            "archived_or_parked_workspace_refs": list(self.archived_or_parked_workspace_refs),
            "creates_authority": self.creates_authority,
            "current_workspace_ref": self.current_workspace_ref,
            "freshness_by_workspace": self.freshness_by_workspace,
            "mode": self.mode,
            "open_mode": self.open_mode,
            "overlay_id": self.overlay_id,
            "persistent_left_rail": self.persistent_left_rail,
            "recent_workspace_refs": list(self.recent_workspace_refs),
            "show_archived_parked": self.show_archived_parked,
            "trigger": self.trigger,
        }


@dataclass(frozen=True)
class MenuCommandMap:
    groups: dict[str, tuple[CommandAffordance, ...]]
    read_only_preview: bool

    def to_evidence(self) -> dict[str, Any]:
        return {
            "groups": {name: [item.to_evidence() for item in items] for name, items in self.groups.items()},
            "read_only_preview": self.read_only_preview,
        }


@dataclass(frozen=True)
class ProjectionReadSurface:
    surface_id: str
    projection_ref: str
    projection_type: str
    freshness_state: str
    read_only: bool
    stale_affordance: str
    authority_notice: str
    canonical_authority: bool = False

    def to_evidence(self) -> dict[str, Any]:
        return {
            "authority_notice": self.authority_notice,
            "canonical_authority": self.canonical_authority,
            "freshness_state": self.freshness_state,
            "projection_ref": self.projection_ref,
            "projection_type": self.projection_type,
            "read_only": self.read_only,
            "stale_affordance": self.stale_affordance,
            "surface_id": self.surface_id,
        }


@dataclass(frozen=True)
class MissionControlViewModel:
    workspace_id: str
    projection_surface: ProjectionReadSurface
    project_summary: dict[str, Any]
    module_summaries: dict[str, Any]
    blocker_refs: tuple[str, ...]
    hitl_refs: tuple[str, ...]
    feedback_refs: tuple[str, ...]
    creates_authority: bool

    def to_evidence(self) -> dict[str, Any]:
        return {
            "blocker_refs": list(self.blocker_refs),
            "creates_authority": self.creates_authority,
            "feedback_refs": list(self.feedback_refs),
            "hitl_refs": list(self.hitl_refs),
            "module_summaries": self.module_summaries,
            "project_summary": self.project_summary,
            "projection_surface": self.projection_surface.to_evidence(),
            "workspace_id": self.workspace_id,
        }


@dataclass(frozen=True)
class NotesEvidenceFrameViewModel:
    frame_id: str
    source_docs_read: tuple[str, ...]
    prototype_refs: tuple[str, ...]
    figma_refs: tuple[str, ...]
    ux_only_status: str
    governance_boundaries: tuple[str, ...]
    open_questions: tuple[str, ...]
    is_app_screen: bool
    creates_authority: bool

    def to_evidence(self) -> dict[str, Any]:
        return {
            "creates_authority": self.creates_authority,
            "figma_refs": list(self.figma_refs),
            "frame_id": self.frame_id,
            "governance_boundaries": list(self.governance_boundaries),
            "is_app_screen": self.is_app_screen,
            "open_questions": list(self.open_questions),
            "prototype_refs": list(self.prototype_refs),
            "source_docs_read": list(self.source_docs_read),
            "ux_only_status": self.ux_only_status,
        }


def build_read_only_view_model(*, workspace_id: str) -> LocalAppViewModel:
    return LocalAppViewModel(
        workspace_id=workspace_id,
        read_only=True,
        workspace_picker_mode="projection_overlay",
        workspace_picker_creates_authority=False,
        disabled_commands=("approve", "complete", "archive", "baseline", "no_go", "final_pass"),
        freshness_chips=("source", "kernel", "projection"),
        framework=None,
    )


def build_read_only_desktop_shell(
    *,
    workspace_id: str,
    workspace_display_name: str,
    kernel_source_ref: str,
) -> LocalDesktopShellViewModel:
    refresh = CommandAffordance(
        command_id="cmd-refresh-projection",
        label="Refresh projection",
        module_id="mission_control",
        surface="header",
        creates_command_draft=False,
        service_command_type="RefreshProjection",
        requires_human_decision=False,
        disabled=False,
        disabled_reason="",
        source_refs=("WBS V0.6", "L1GOV-SLICE-010", "eef9c05"),
        payload={"projection_type": "mission_control"},
    )
    return LocalDesktopShellViewModel(
        workspace_id=workspace_id,
        workspace_display_name=workspace_display_name,
        read_only_preview=True,
        show_archived_parked=False,
        service_state="connected",
        projection_freshness="current",
        sync_state="ok",
        kernel_source_ref=kernel_source_ref,
        active_module="mission_control",
        module_navigation=("mission_control", "standardization", "monitor_hitl", "delivery_feedback", "notes_evidence"),
        header_actions=(refresh,),
        disabled_commands=disabled_mutation_command_ids(),
        toolbar=(refresh,),
        inspector={"mode": "read_only_projection"},
        status_bar={
            "service_state": "connected",
            "projection_freshness": "current",
            "sync_state": "ok",
            "kernel_source_ref": kernel_source_ref,
        },
        framework=None,
        persistent_workspace_explorer=False,
        canonical_authority=False,
    )


def disabled_mutation_command_ids() -> tuple[str, ...]:
    return (
        "approve",
        "complete",
        "archive",
        "baseline",
        "no_go",
        "deploy",
        "production_readiness",
        "continuity_activation",
        "final_pass",
        "direct_mutation",
        "canonical_write",
    )


def validate_local_desktop_shell(view_model: LocalDesktopShellViewModel) -> ValidationResult:
    missing = _missing_fields(
        view_model,
        (
            "workspace_id",
            "workspace_display_name",
            "service_state",
            "projection_freshness",
            "sync_state",
            "kernel_source_ref",
            "active_module",
            "module_navigation",
            "status_bar",
        ),
    )
    if missing:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, f"missing fields: {', '.join(missing)}")
    if view_model.framework not in (None, "not_selected"):
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "final UI framework selection is out of Slice 010 scope")
    if app_shell_forbidden_intent(
        {
            "framework": view_model.framework,
            "inspector": view_model.inspector,
            "status_bar": view_model.status_bar,
        }
    ):
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "local app shell contains out-of-scope runtime or authority fields")
    if view_model.persistent_workspace_explorer:
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "workspace selection must use a temporary overlay contract")
    if view_model.canonical_authority:
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "local app shell cannot be canonical authority")
    if view_model.service_state not in SERVICE_STATES:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, f"unknown service_state: {view_model.service_state}")
    if view_model.projection_freshness not in PROJECTION_FRESHNESS_STATES:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, f"unknown projection_freshness: {view_model.projection_freshness}")
    if view_model.sync_state not in SYNC_STATES:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, f"unknown sync_state: {view_model.sync_state}")
    if view_model.active_module not in LOCAL_APP_MODULES:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, f"unknown active_module: {view_model.active_module}")
    unknown_modules = tuple(module for module in view_model.module_navigation if module not in LOCAL_APP_MODULES)
    if unknown_modules:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, f"unknown module_navigation entries: {', '.join(unknown_modules)}")
    if view_model.read_only_preview and not set(disabled_mutation_command_ids()).issubset(set(view_model.disabled_commands)):
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "read-only preview must disable mutation affordances")
    required_status_keys = ("service_state", "projection_freshness", "sync_state", "kernel_source_ref")
    if any(not view_model.status_bar.get(key) for key in required_status_keys):
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, "status_bar must expose service, freshness, sync, and kernel refs")
    for affordance in (*view_model.header_actions, *view_model.toolbar):
        result = validate_command_affordance(affordance)
        if not result.accepted:
            return result
        if view_model.read_only_preview and affordance.creates_command_draft and not affordance.disabled:
            return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "read-only preview cannot expose enabled mutation affordances")
    return ValidationResult(True)


def validate_workspace_picker_overlay(overlay: WorkspacePickerOverlayViewModel) -> ValidationResult:
    missing = _missing_fields(
        overlay,
        ("overlay_id", "trigger", "mode", "open_mode", "current_workspace_ref", "freshness_by_workspace", "actions"),
    )
    if missing:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, f"missing fields: {', '.join(missing)}")
    if overlay.trigger not in WORKSPACE_PICKER_TRIGGERS:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, f"unknown workspace picker trigger: {overlay.trigger}")
    if overlay.mode not in WORKSPACE_PICKER_MODES:
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "workspace picker must be temporary overlay/popover/modal/sheet/subview")
    if overlay.open_mode not in WORKSPACE_OPEN_MODES:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, f"unknown workspace open_mode: {overlay.open_mode}")
    if overlay.creates_authority:
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "workspace picker cannot create authority")
    if overlay.persistent_left_rail:
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "workspace picker cannot be a persistent left rail")
    if overlay.archived_or_parked_workspace_refs and not overlay.show_archived_parked:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, "archived/parked workspaces require show_archived_parked")
    unknown_actions = tuple(action for action in overlay.actions if action not in WORKSPACE_PICKER_ACTIONS)
    if unknown_actions:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, f"unknown workspace picker actions: {', '.join(unknown_actions)}")
    unknown_freshness = tuple(
        freshness for freshness in overlay.freshness_by_workspace.values() if str(freshness) not in PROJECTION_FRESHNESS_STATES
    )
    if unknown_freshness:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, f"unknown workspace freshness states: {', '.join(unknown_freshness)}")
    return ValidationResult(True)


def validate_command_affordance(affordance: CommandAffordance) -> ValidationResult:
    missing = _missing_fields(affordance, ("command_id", "label", "module_id", "surface", "source_refs"))
    if missing:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, f"missing fields: {', '.join(missing)}")
    if affordance.module_id not in LOCAL_APP_MODULES:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, f"unknown module_id: {affordance.module_id}")
    if affordance.surface not in COMMAND_SURFACES:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, f"unknown command surface: {affordance.surface}")
    if affordance.service_command_type not in SERVICE_COMMAND_TYPES:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, f"unknown service command type: {affordance.service_command_type}")
    if affordance.disabled:
        if affordance.creates_command_draft or affordance.service_command_type == "SubmitCommandDraft":
            return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "disabled affordance cannot create command drafts")
        return ValidationResult(True)
    if app_shell_forbidden_intent({"label": affordance.label, "payload": affordance.payload}):
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "local app affordance crosses Slice 010 no-go boundary")
    if affordance.creates_command_draft and affordance.service_command_type != "SubmitCommandDraft":
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, "command draft affordance must route to SubmitCommandDraft")
    if not affordance.creates_command_draft and affordance.service_command_type == "SubmitCommandDraft":
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, "SubmitCommandDraft affordance must create a command draft")
    return ValidationResult(True)


def validate_menu_command_map(command_map: MenuCommandMap) -> ValidationResult:
    if not command_map.groups:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, "menu command map requires groups")
    unknown_groups = tuple(group for group in command_map.groups if group not in MENU_GROUPS)
    if unknown_groups:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, f"unknown menu groups: {', '.join(unknown_groups)}")
    for affordances in command_map.groups.values():
        for affordance in affordances:
            result = validate_command_affordance(affordance)
            if not result.accepted:
                return result
            if command_map.read_only_preview and affordance.creates_command_draft and not affordance.disabled:
                return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "read-only menu cannot expose enabled mutation commands")
    return ValidationResult(True)


def build_command_draft_route(
    affordance: CommandAffordance,
    *,
    actor_id: str,
    expected_version: int,
    expected_state: str,
    idempotency_key: str,
) -> tuple[ValidationResult, CommandEnvelope | None]:
    result = validate_command_affordance(affordance)
    if not result.accepted:
        return result, None
    if affordance.disabled:
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "disabled affordance cannot create command drafts"), None
    if not affordance.creates_command_draft or affordance.service_command_type != "SubmitCommandDraft":
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, "affordance does not route to SubmitCommandDraft"), None

    target_ref = str(affordance.payload.get("target_ref", "layer1-governance"))
    draft = CommandDraft(
        draft_id=f"draft:{affordance.command_id}:{idempotency_key}",
        command_type=str(affordance.payload.get("draft_command_type", "SubmitCommandDraft")),
        target_ref=target_ref,
        payload=dict(affordance.payload),
        read_only_blocked=False,
        source_refs=tuple(affordance.source_refs),
        draft_status="draft",
        created_by=actor_id,
    )
    command = CommandEnvelope(
        command_type="SubmitCommandDraft",
        actor=ActorRef(actor_id=actor_id, role="local_app_shell"),
        authority_refs=tuple(affordance.source_refs),
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        payload={
            "authorization_source": "Nova-approved-baseline",
            "command_draft": _command_draft_payload(draft),
            "expected_kernel_version": expected_version,
            "expected_state": expected_state,
            "expected_version": expected_version,
            "idempotency_key": idempotency_key,
            "source_refs": tuple(affordance.source_refs),
            "target_ref": target_ref,
            "ui_correlation_ref": affordance.command_id,
        },
        affects_state=True,
        command_id=f"ui:{idempotency_key}",
        target_ref=target_ref,
        expected_state=expected_state,
        source_refs=tuple(affordance.source_refs),
        authorization_source="Nova-approved-baseline",
    )
    return ValidationResult(True), command


def build_projection_read_surface(surface_id: str, snapshot: ProjectionSnapshot) -> ProjectionReadSurface:
    freshness = _freshness_value(snapshot.freshness)
    stale_affordance = "request_rebuild" if freshness == "stale" else "blocked_until_rebuild" if freshness in ("rebuilding", "failed") else "none"
    return ProjectionReadSurface(
        surface_id=surface_id,
        projection_ref=snapshot.projection_id,
        projection_type=snapshot.projection_type,
        freshness_state=freshness,
        read_only=True,
        stale_affordance=stale_affordance,
        authority_notice="projection read surface is not canonical state",
        canonical_authority=False,
    )


def validate_projection_read_surface(surface: ProjectionReadSurface) -> ValidationResult:
    missing = _missing_fields(
        surface,
        ("surface_id", "projection_ref", "projection_type", "freshness_state", "stale_affordance", "authority_notice"),
    )
    if missing:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, f"missing fields: {', '.join(missing)}")
    if not surface.read_only:
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "projection surface must remain read-only")
    if surface.canonical_authority or _authority_notice_forbidden(surface.authority_notice):
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "projection/read surface cannot be authority")
    if surface.freshness_state not in PROJECTION_FRESHNESS_STATES:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, f"unknown freshness_state: {surface.freshness_state}")
    if surface.stale_affordance not in STALE_AFFORDANCES:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, f"unknown stale_affordance: {surface.stale_affordance}")
    if surface.freshness_state == "stale" and surface.stale_affordance not in ("show_stale_chip", "request_rebuild"):
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, "stale projection requires stale chip or rebuild request affordance")
    return ValidationResult(True)


def build_projection_refresh_command(
    surface: ProjectionReadSurface,
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    workspace_id: str,
    source_checkpoint: str,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="RefreshProjection",
        actor=actor,
        authority_refs=tuple(authority_refs),
        expected_version=None,
        idempotency_key=f"refresh:{surface.surface_id}:{source_checkpoint}",
        payload={
            "projection_payload": {},
            "projection_type": surface.projection_type,
            "source_checkpoint": source_checkpoint,
            "source_refs": tuple(authority_refs),
            "workspace_id": workspace_id,
        },
        affects_state=False,
        command_id=f"refresh:{surface.surface_id}",
        target_ref=surface.projection_ref,
        source_refs=tuple(authority_refs),
    )


def validate_mission_control_view_model(view_model: MissionControlViewModel) -> ValidationResult:
    if view_model.creates_authority:
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "Mission Control view model cannot create authority")
    surface_result = validate_projection_read_surface(view_model.projection_surface)
    if not surface_result.accepted:
        return surface_result
    if not view_model.workspace_id:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, "workspace_id is required")
    return ValidationResult(True)


def validate_notes_evidence_frame(frame: NotesEvidenceFrameViewModel) -> ValidationResult:
    missing = _missing_fields(frame, ("frame_id", "source_docs_read", "ux_only_status", "governance_boundaries"))
    if missing:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, f"missing fields: {', '.join(missing)}")
    if frame.is_app_screen or frame.creates_authority:
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "notes evidence frame is evidence-only and cannot create authority")
    return ValidationResult(True)


def build_service_outcome_view(outcome: ServiceCommandOutcome) -> dict[str, Any]:
    return {
        "blocked_reason": outcome.blocked_reason,
        "command_id": outcome.command_id,
        "error_code": outcome.error_code.value if outcome.error_code else None,
        "locally_overridden": False,
        "projection_refresh": outcome.projection_refresh,
        "source": "GovernanceService",
        "status": outcome.status.value,
    }


def app_shell_forbidden_intent(value: Any) -> bool:
    return _text_has_terms(value, APP_SHELL_FORBIDDEN_TERMS)


def _command_draft_payload(draft: CommandDraft) -> dict[str, Any]:
    return {
        "created_by": draft.created_by,
        "draft_id": draft.draft_id,
        "draft_status": draft.draft_status,
        "command_type": draft.command_type,
        "payload": draft.payload,
        "read_only_blocked": draft.read_only_blocked,
        "source_refs": tuple(draft.source_refs),
        "target_ref": draft.target_ref,
    }


def _freshness_value(freshness: FreshnessState | str) -> str:
    value = freshness.value if isinstance(freshness, FreshnessState) else str(freshness)
    return "current" if value == "fresh" else value


def _authority_notice_forbidden(text: str) -> bool:
    normalized = _normalized(text)
    return any(
        _term_in_text(normalized, _normalized(term))
        for term in (
            "projection authority",
            "projection is canonical authority",
            "cache authority",
            "view model authority",
            "source of truth",
        )
    )


def _missing_fields(item: object, field_names: tuple[str, ...]) -> tuple[str, ...]:
    values = item if isinstance(item, dict) else item.__dict__
    missing: list[str] = []
    for field_name in field_names:
        if _payload_value_empty(values.get(field_name)):
            missing.append(field_name)
    return tuple(missing)


def _payload_value_empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value == ""
    if isinstance(value, (dict, list, set, tuple)):
        return len(value) == 0
    return False


def _text_has_terms(value: Any, terms: tuple[str, ...]) -> bool:
    normalized_terms = {_normalized(term) for term in terms}
    for text in _iter_normalized_text(value):
        for term in normalized_terms:
            if _term_in_text(text, term):
                return True
    return False


def _iter_normalized_text(value: Any) -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(value, str):
        found.append(_normalized(value))
    elif isinstance(value, dict):
        for key, item in value.items():
            found.extend(_iter_normalized_text(key))
            found.extend(_iter_normalized_text(item))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            found.extend(_iter_normalized_text(item))
    elif hasattr(value, "__dict__"):
        found.extend(_iter_normalized_text(value.__dict__))
    return tuple(found)


def _normalized(value: object) -> str:
    text = str(value).strip().lower()
    for token in ("_", "-", "/", "\\", ":", "."):
        text = text.replace(token, " ")
    return " ".join(text.split())


def _term_in_text(text: str, term: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None
