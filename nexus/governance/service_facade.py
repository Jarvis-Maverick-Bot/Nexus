from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .delivery_feedback import DELIVERY_FEEDBACK_COMMAND_TYPES
from .dispatch_contract import DISPATCH_COMMAND_TYPES
from .errors import ErrorCode
from .execution import EXECUTION_COMMAND_TYPES
from .impact_control import IMPACT_CONTROL_COMMAND_TYPES
from .kernel import GovernanceKernel
from .monitor_hitl import MONITOR_HITL_COMMAND_TYPES
from .no_go import NoGoBoundaryPolicy
from .projections import build_projection_snapshot
from .schemas import ActorRef, CommandEnvelope, ValidationResult, validate_command_envelope
from .service_contract import GovernanceServiceContract
from .source_authority import SourceAuthorityManifest, verify_source_authority
from .standardization import STANDARDIZATION_COMMAND_TYPES
from .workspace_init import WORKSPACE_INIT_COMMAND_TYPES


SERVICE_COMMAND_TYPES: tuple[str, ...] = (
    "SubmitCommandDraft",
    "RefreshProjection",
    "MediateBaselineEntry",
    "PreflightImpactSensitiveCommand",
)
KNOWN_ROUTABLE_COMMAND_TYPES: tuple[str, ...] = (
    *SERVICE_COMMAND_TYPES,
    *WORKSPACE_INIT_COMMAND_TYPES,
    *STANDARDIZATION_COMMAND_TYPES,
    *EXECUTION_COMMAND_TYPES,
    *DISPATCH_COMMAND_TYPES,
    *MONITOR_HITL_COMMAND_TYPES,
    *IMPACT_CONTROL_COMMAND_TYPES,
    *DELIVERY_FEEDBACK_COMMAND_TYPES,
)

DRAFT_STATUSES: tuple[str, ...] = ("draft", "validated", "submitted", "blocked", "superseded")
OUTCOME_STATUSES: tuple[str, ...] = ("accepted", "blocked", "rejected", "stale", "review_required", "reconcile_required")
IMPACT_SURFACES: tuple[str, ...] = (
    "scope",
    "authority",
    "artifacts",
    "gate_acceptance",
    "runtime_behavior",
    "implementation_behavior",
    "evidence_sufficiency",
    "downstream_work",
    "rollback",
)
HITL_ACTION_TERMS: tuple[str, ...] = (
    "approve baseline",
    "approval",
    "archive",
    "baseline",
    "no go",
    "no-go",
    "scope changing",
    "scope-changing",
    "conflict",
    "review required",
)
METADATA_PAYLOAD_KEYS: tuple[str, ...] = (
    "authorization_source",
    "source_refs",
    "expected_state",
    "expected_version",
    "expected_kernel_version",
    "idempotency_key",
    "projection_type",
    "target_ref",
)
FORBIDDEN_TERMS: tuple[str, ...] = (
    "complete project",
    "completion claim",
    "continuity activation",
    "continuity active",
    "final pass",
    "final_pass",
    "production ready",
    "production_ready",
    "production readiness",
    "deploy",
    "deploy to production",
    "release to production",
    "runtime invocation",
    "runtime live invocation",
    "private agent invocation",
    "private-agent invocation",
    "dispatch now",
    "dispatch execution",
    "actual dispatch",
    "execute dispatch",
    "perform dispatch",
    "controller call",
    "direct controller call",
    "controller execution",
    "owner path call",
    "adapter call",
    "transport call",
    "route activation",
    "activate route",
    "workpacket execution",
    "execute workpacket",
    "lower layer submission",
    "config mutation",
    "mutate config",
    "credential mutation",
    "package manager",
    "package-manager",
    "projection as authority",
    "projection authority",
    "cache as authority",
    "app cache",
    "source of truth",
    "direct canonical mutation",
    "kernel bypass",
    "direct state mutation",
    "ui framework selection",
    "database selection",
    "api runtime selection",
    "direct_ui_approval",
    "notification_as_decision",
    "status_card_approval",
    "chat_approval",
    "controller_approval",
)

BUILT_IN_BASELINE_CATALOG: dict[str, tuple[str, ...]] = {
    "workspace_init": ("manifest", "initiation_record", "source_authority"),
    "standardization": ("planning_candidate", "deliverable_evaluation_profile", "feedback_metric_policy"),
    "project_execution": ("packet_map", "workpacket", "readiness_decision"),
    "dispatch_contract": ("dispatch_decision", "handoff_candidate", "return_normalization"),
    "monitor_hitl": ("human_review_task", "human_decision", "deliverable_evaluation_result", "escalation_record"),
    "impact_control": ("impact_request", "impact_assessment", "layer_impact_detected"),
    "delivery_feedback": ("delivery_record", "feedback_record", "feedback_metric_trend", "triage_decision", "completion_continuity_packet"),
    "service_facade": ("command_envelope", "projection_snapshot", "baseline_entry"),
}


class ServiceOutcomeStatus(StrEnum):
    ACCEPTED = "accepted"
    BLOCKED = "blocked"
    REJECTED = "rejected"
    STALE = "stale"
    REVIEW_REQUIRED = "review_required"
    RECONCILE_REQUIRED = "reconcile_required"


@dataclass(frozen=True)
class CommandDraft:
    draft_id: str
    command_type: str
    target_ref: str
    payload: dict[str, Any]
    read_only_blocked: bool
    source_refs: tuple[str, ...]
    draft_status: str
    created_by: str


@dataclass(frozen=True)
class BaselineEntryCommand:
    component_output_ref: str
    workitem_type: str
    subtype: str
    evidence_refs: tuple[str, ...]
    decision_ref: str
    expected_state: str
    expected_version: int
    idempotency_key: str
    source_refs: tuple[str, ...]
    mediated_by_service: bool = True


@dataclass(frozen=True)
class ServiceCommandOutcome:
    command_id: str
    status: ServiceOutcomeStatus
    kernel_record_ref: str | None = None
    blocked_reason: str = ""
    projection_refresh: str = "none"
    errors: tuple[str, ...] = ()
    error_code: ErrorCode | None = None
    projection_ref: str | None = None
    evidence_refs: tuple[str, ...] = ()

    def to_evidence(self) -> dict[str, Any]:
        return {
            "blocked_reason": self.blocked_reason,
            "command_id": self.command_id,
            "error_code": self.error_code.value if self.error_code else None,
            "errors": list(self.errors),
            "evidence_refs": list(self.evidence_refs),
            "kernel_record_ref": self.kernel_record_ref,
            "projection_ref": self.projection_ref,
            "projection_refresh": self.projection_refresh,
            "status": self.status.value,
        }


@dataclass
class GovernanceServiceFacade:
    source_manifest: SourceAuthorityManifest
    no_go_policy: NoGoBoundaryPolicy
    kernel: GovernanceKernel

    def handle(self, command: CommandEnvelope, intent: dict[str, Any] | None = None) -> ServiceCommandOutcome:
        command_id = _command_id(command)
        source_result = verify_source_authority(self.source_manifest)
        if not source_result.accepted:
            return _outcome(
                command_id,
                ServiceOutcomeStatus.REJECTED,
                source_result.message,
                ErrorCode.STALE_SOURCE_AUTHORITY
                if source_result.error_code == ErrorCode.STALE_SOURCE_AUTHORITY.value
                else ErrorCode.NO_GO_BOUNDARY,
            )

        no_go = self.no_go_policy.evaluate(intent)
        if no_go.blocked:
            return _outcome(command_id, ServiceOutcomeStatus.BLOCKED, no_go.message, no_go.error_code)

        validation = validate_service_command_envelope(command)
        if not validation.accepted:
            return _validation_outcome(command_id, validation)

        if command.command_type == "RefreshProjection":
            projection_type = str(command.payload.get("projection_type", "unknown"))
            source_checkpoint = str(command.payload.get("source_checkpoint", "unknown"))
            snapshot = build_projection_snapshot(
                projection_type=projection_type,
                workspace_id=str(command.payload.get("workspace_id", "workspace")),
                source_checkpoint=source_checkpoint,
                payload=dict(command.payload.get("projection_payload", {})),
                authority_refs=tuple(command.authority_refs),
            )
            return ServiceCommandOutcome(
                command_id=command_id,
                status=ServiceOutcomeStatus.ACCEPTED,
                projection_ref=f"projection:{snapshot.projection_type}:{snapshot.source_checkpoint}",
                projection_refresh="rebuilt",
                evidence_refs=tuple(snapshot.authority_refs),
            )

        if command.command_type == "SubmitCommandDraft":
            if "command_draft" not in command.payload:
                return _validation_outcome(
                    command_id,
                    ValidationResult(False, ErrorCode.INVALID_TRANSITION, "SubmitCommandDraft requires command_draft payload"),
                )
            draft_result = validate_command_draft(_coerce_command_draft(command.payload.get("command_draft")))
            if not draft_result.accepted:
                return _validation_outcome(command_id, draft_result)
            return ServiceCommandOutcome(
                command_id=command_id,
                status=ServiceOutcomeStatus.ACCEPTED,
                projection_refresh="stale",
                evidence_refs=tuple(command.authority_refs),
            )

        if command.command_type == "PreflightImpactSensitiveCommand":
            return ServiceCommandOutcome(
                command_id=command_id,
                status=ServiceOutcomeStatus.ACCEPTED,
                projection_refresh="none",
                evidence_refs=(str(command.payload.get("impact_assessment_ref")),),
            )

        if command.command_type == "MediateBaselineEntry":
            baseline = _coerce_baseline(command.payload.get("baseline_entry"))
            baseline_result = validate_baseline_entry_command(baseline)
            if not baseline_result.accepted:
                return _validation_outcome(command_id, baseline_result)
            transition = self.kernel.apply(command)
            if not transition.accepted:
                return _outcome(
                    command_id,
                    _status_for_error(transition.error_code),
                    transition.message,
                    transition.error_code,
                    projection_refresh="none",
                )
            return ServiceCommandOutcome(
                command_id=command_id,
                status=ServiceOutcomeStatus.ACCEPTED,
                kernel_record_ref=transition.record.record_id if transition.record else None,
                projection_refresh="stale",
                evidence_refs=tuple(command.authority_refs),
            )

        response = GovernanceServiceContract(self.source_manifest, self.no_go_policy, self.kernel).handle(command)
        if not response.accepted:
            return _outcome(
                command_id,
                _status_for_error(response.error_code),
                response.message,
                response.error_code,
                projection_refresh="none",
            )
        return ServiceCommandOutcome(
            command_id=command_id,
            status=ServiceOutcomeStatus.ACCEPTED,
            kernel_record_ref=response.record_ref,
            projection_ref=response.projection_ref,
            projection_refresh="stale" if response.record_ref else "none",
            evidence_refs=tuple(response.evidence_refs),
        )


def validate_command_draft(draft: CommandDraft) -> ValidationResult:
    missing = _missing_fields(
        draft,
        ("draft_id", "command_type", "target_ref", "payload", "source_refs", "draft_status", "created_by"),
    )
    if missing:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, f"missing fields: {', '.join(missing)}")
    if draft.draft_status not in DRAFT_STATUSES:
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, f"CommandDraft status rejected: {draft.draft_status}")
    if draft.read_only_blocked:
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "read-only draft cannot submit state mutation")
    if _has_forbidden_intent(draft.__dict__):
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "CommandDraft crossed Slice 009 no-go boundary")
    return ValidationResult(True)


def validate_service_command_envelope(command: CommandEnvelope) -> ValidationResult:
    base = validate_command_envelope(command)
    if not base.accepted:
        return base
    if command.command_type not in KNOWN_ROUTABLE_COMMAND_TYPES:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, f"unknown service command type: {command.command_type}")

    if _authority_source_forbidden(_authority_payload(command)):
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "app cache or projection cannot be source authority")
    if _has_forbidden_intent(command.payload):
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "service command crossed Slice 009 no-go boundary")

    source_refs = command.source_refs or tuple(command.payload.get("source_refs", ())) or command.authority_refs
    if tuple(source_refs) != tuple(command.authority_refs):
        return ValidationResult(False, ErrorCode.STALE_SOURCE_AUTHORITY, "source_refs must match authority_refs")

    if command.affects_state:
        if not command.command_id:
            return ValidationResult(False, ErrorCode.INVALID_TRANSITION, "state-affecting commands require command_id")
        if not (command.target_ref or command.payload.get("target_ref")):
            return ValidationResult(False, ErrorCode.INVALID_TRANSITION, "state-affecting commands require target_ref")
        if not (command.expected_state or command.payload.get("expected_state")):
            return ValidationResult(False, ErrorCode.INVALID_TRANSITION, "state-affecting commands require expected_state")
        if not _is_non_negative_int(command.expected_version):
            return ValidationResult(False, ErrorCode.STALE_EXPECTED_VERSION, "expected_version must be a non-negative integer")
        if not command.idempotency_key:
            return ValidationResult(False, ErrorCode.MISSING_IDEMPOTENCY_KEY, "state-affecting commands require idempotency_key")
        auth_source = command.authorization_source or str(command.payload.get("authorization_source", ""))
        if auth_source != "Nova-approved-baseline":
            if _has_forbidden_intent(auth_source):
                return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "authorization source cannot be cache/projection authority")
            return ValidationResult(False, ErrorCode.STALE_SOURCE_AUTHORITY, "state-affecting commands require Nova-approved-baseline")
        for version_field in ("expected_version", "expected_kernel_version"):
            if version_field in command.payload:
                if not _is_non_negative_int(command.payload[version_field]):
                    return ValidationResult(False, ErrorCode.STALE_EXPECTED_VERSION, f"{version_field} must be a non-negative integer")
                if command.payload[version_field] != command.expected_version:
                    return ValidationResult(False, ErrorCode.STALE_EXPECTED_VERSION, f"payload {version_field} must match envelope expected_version")
        if "idempotency_key" in command.payload and command.payload["idempotency_key"] != command.idempotency_key:
            return ValidationResult(False, ErrorCode.IDEMPOTENCY_KEY_REUSE, "payload idempotency_key must match envelope idempotency_key")

    impact_surfaces = tuple(command.payload.get("impact_surfaces", ()) or ())
    if any(str(surface) in IMPACT_SURFACES for surface in impact_surfaces) and not command.payload.get("impact_assessment_ref"):
        return ValidationResult(False, ErrorCode.IMPACT_CONTROL_RECORD_INVALID, "ImpactAssessment is required before propagation")

    if _requires_human_decision(command.payload) and not _has_human_decision_ref(command.payload):
        return ValidationResult(False, ErrorCode.MISSING_HUMAN_DECISION, "Monitor/HITL HumanDecision is required")

    return ValidationResult(True)


def validate_baseline_entry_command(entry: BaselineEntryCommand) -> ValidationResult:
    missing = _missing_fields(
        entry,
        (
            "component_output_ref",
            "workitem_type",
            "subtype",
            "evidence_refs",
            "expected_state",
            "source_refs",
            "idempotency_key",
        ),
    )
    if missing:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, f"missing fields: {', '.join(missing)}")
    if not entry.mediated_by_service:
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "baseline entry must be mediated by Governance Service")
    if not _is_non_negative_int(entry.expected_version):
        return ValidationResult(False, ErrorCode.STALE_EXPECTED_VERSION, "expected_version must be a non-negative integer")
    if entry.workitem_type not in BUILT_IN_BASELINE_CATALOG:
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, f"unknown baseline workitem_type: {entry.workitem_type}")
    if entry.subtype not in BUILT_IN_BASELINE_CATALOG[entry.workitem_type]:
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, f"unknown baseline subtype: {entry.subtype}")
    if not _has_human_decision_text(entry.decision_ref):
        return ValidationResult(False, ErrorCode.MISSING_HUMAN_DECISION, "baseline entry requires HumanDecision-backed decision_ref")
    if _has_forbidden_intent(entry.__dict__):
        return ValidationResult(False, ErrorCode.NO_GO_BOUNDARY, "BaselineEntryCommand crossed Slice 009 no-go boundary")
    return ValidationResult(True)


def mediate_baseline_entry_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    baseline_entry: BaselineEntryCommand,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="MediateBaselineEntry",
        actor=actor,
        authority_refs=authority_refs,
        expected_version=baseline_entry.expected_version,
        idempotency_key=baseline_entry.idempotency_key,
        payload={
            "baseline_entry": dict(baseline_entry.__dict__),
            "component_output_ref": baseline_entry.component_output_ref,
            "expected_kernel_version": baseline_entry.expected_version,
            "expected_version": baseline_entry.expected_version,
            "idempotency_key": baseline_entry.idempotency_key,
            "mediated_by_service": baseline_entry.mediated_by_service,
            "projection_type": "baseline-entry",
            "source_refs": authority_refs,
            "target_ref": "layer1-governance",
            "expected_state": baseline_entry.expected_state,
            "authorization_source": "Nova-approved-baseline",
        },
        affects_state=True,
        command_id=f"baseline:{baseline_entry.idempotency_key}",
        target_ref="layer1-governance",
        expected_state=baseline_entry.expected_state,
        source_refs=authority_refs,
        authorization_source="Nova-approved-baseline",
    )


def _validation_outcome(command_id: str, validation: ValidationResult) -> ServiceCommandOutcome:
    return _outcome(
        command_id,
        _status_for_error(validation.error_code),
        validation.message,
        validation.error_code,
        projection_refresh="none",
    )


def _outcome(
    command_id: str,
    status: ServiceOutcomeStatus,
    message: str,
    error_code: ErrorCode | None,
    *,
    projection_refresh: str = "none",
) -> ServiceCommandOutcome:
    return ServiceCommandOutcome(
        command_id=command_id,
        status=status,
        blocked_reason=message,
        errors=(message,) if message else (),
        error_code=error_code,
        projection_refresh=projection_refresh,
    )


def _status_for_error(error_code: ErrorCode | None) -> ServiceOutcomeStatus:
    if error_code == ErrorCode.STALE_EXPECTED_VERSION:
        return ServiceOutcomeStatus.STALE
    if error_code in (ErrorCode.MISSING_HUMAN_DECISION, ErrorCode.IMPACT_CONTROL_RECORD_INVALID):
        return ServiceOutcomeStatus.REVIEW_REQUIRED
    if error_code in (ErrorCode.NO_GO_BOUNDARY, ErrorCode.RAW_FEEDBACK_NO_AUTHORITY_MUTATION):
        return ServiceOutcomeStatus.BLOCKED
    return ServiceOutcomeStatus.REJECTED


def _command_id(command: CommandEnvelope) -> str:
    return command.command_id or command.idempotency_key or command.command_type


def _coerce_baseline(value: Any) -> BaselineEntryCommand:
    if isinstance(value, BaselineEntryCommand):
        return value
    if isinstance(value, dict):
        return BaselineEntryCommand(**value)
    return BaselineEntryCommand("", "", "", (), "", "", -1, "", ())


def _coerce_command_draft(value: Any) -> CommandDraft:
    if isinstance(value, CommandDraft):
        return value
    if isinstance(value, dict):
        return CommandDraft(
            draft_id=str(value.get("draft_id", "")),
            command_type=str(value.get("command_type", "")),
            target_ref=str(value.get("target_ref", "")),
            payload=dict(value.get("payload", {})) if isinstance(value.get("payload"), dict) else {},
            read_only_blocked=bool(value.get("read_only_blocked", False)),
            source_refs=tuple(value.get("source_refs") or ()),
            draft_status=str(value.get("draft_status", "")),
            created_by=str(value.get("created_by", "")),
        )
    return CommandDraft("", "", "", {}, False, (), "", "")


def _authority_payload(command: CommandEnvelope) -> dict[str, Any]:
    return {
        "authorization_source": command.authorization_source,
        "payload_authorization_source": command.payload.get("authorization_source"),
        "authority_source": command.payload.get("authority_source"),
        "source_authority": command.payload.get("source_authority"),
    }


def _authority_source_forbidden(payload: dict[str, Any]) -> bool:
    for value in payload.values():
        for text in _iter_normalized_text(value):
            if any(term in text for term in ("projection", "cache", "source of truth")):
                return True
    return False


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


def _semantic_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _semantic_payload(item) for key, item in value.items() if str(key) not in METADATA_PAYLOAD_KEYS}
    if isinstance(value, (list, tuple, set)):
        return tuple(_semantic_payload(item) for item in value)
    return value


def _is_non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _requires_human_decision(payload: dict[str, Any]) -> bool:
    if payload.get("review_required") is True:
        return True
    return _text_has_terms(_semantic_payload(payload), HITL_ACTION_TERMS)


def _has_human_decision_ref(payload: dict[str, Any]) -> bool:
    return _has_human_decision_text(payload)


def _has_human_decision_text(value: Any) -> bool:
    for text in _iter_normalized_text(value):
        compact = text.replace(" ", "")
        if "humandecision" in compact or "human decision" in text:
            return True
    return False


def _has_forbidden_intent(value: Any) -> bool:
    return _text_has_terms(value, FORBIDDEN_TERMS)


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
