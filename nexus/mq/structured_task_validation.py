"""Fail-closed validation for WBS 7.19 structured task records."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from typing import Any

from nexus.mq.agent_registry_events import secret_material_errors
from nexus.mq.structured_task_models import (
    OwnerHandoffPacket,
    TaskEnvelope,
    TaskUnit,
    WorkspaceInitializationContextPlaceholder,
    WorkflowConstraintSet,
)


@dataclass
class StructuredTaskValidationResult:
    ok: bool
    errors: list[str]


def validate_workflow_constraints(value: WorkflowConstraintSet) -> StructuredTaskValidationResult:
    errors = _required(value, [
        "constraint_id",
        "source_refs",
        "wbs_refs",
        "gate_state",
        "dependency_state",
        "dod",
        "no_go_scope",
        "evidence_requirements",
        "review_authority_refs",
        "source_hash",
        "policy_hash",
    ])
    errors.extend(_missing_list(value.source_refs, "MISSING_SOURCE_REFS"))
    errors.extend(_missing_list(value.dod, "MISSING_DOD"))
    errors.extend(_missing_list(value.no_go_scope, "MISSING_NO_GO_SCOPE"))
    errors.extend(_missing_list(value.evidence_requirements, "MISSING_EVIDENCE_REQUIREMENTS"))
    errors.extend(secret_material_errors(value.to_dict(), path="workflow_constraints"))
    return _result(errors)


def validate_workspace_placeholder(
    value: WorkspaceInitializationContextPlaceholder,
) -> StructuredTaskValidationResult:
    errors = _required(value, [
        "workspace_context_id",
        "workspace_refs",
        "project_initialization_refs",
        "active_wbs_ref",
        "source_hash",
        "policy_hash",
        "placeholder_status",
    ])
    if value.placeholder_status == "change_pending" and not value.last_human_approved_change_ref:
        errors.append("UNAPPROVED_INITIALIZATION_CHANGE")
    if "final_stage00_schema" in value.known_fields:
        errors.append("STAGE00_SCHEMA_CLAIM_ATTEMPTED")
    errors.extend(secret_material_errors(value.to_dict(), path="workspace_placeholder"))
    return _result(errors)


def validate_task_envelope(value: TaskEnvelope) -> StructuredTaskValidationResult:
    errors = _required(value, [
        "task_id",
        "envelope_version",
        "run_id",
        "objective",
        "source_refs",
        "source_hash",
        "policy_hash",
        "role_target",
        "required_capabilities",
        "no_go_scope",
        "deliverables",
        "stop_conditions",
        "dispatch_mode",
        "idempotency_key",
    ])
    errors.extend(_missing_list(value.source_refs, "MISSING_SOURCE_REFS"))
    errors.extend(_missing_list(value.no_go_scope, "MISSING_NO_GO_SCOPE"))
    errors.extend(_missing_list(value.deliverables, "MISSING_DELIVERABLES"))
    errors.extend(_missing_list(value.stop_conditions, "MISSING_STOP_CONDITIONS"))
    errors.extend(secret_material_errors(value.to_dict(), path="task_envelope"))
    return _result(errors)


def validate_task_unit(value: TaskUnit) -> StructuredTaskValidationResult:
    errors = _required(value, [
        "task_id",
        "title",
        "objective",
        "source_refs",
        "source_hash",
        "owner",
        "verifier",
        "dod",
        "no_go_scope",
        "allowed_tools",
        "allowed_write_surfaces",
        "evidence_requirements",
        "stop_conditions",
        "escalation_conditions",
    ])
    if value.owner and value.verifier and value.owner == value.verifier:
        errors.append("OWNER_EQUALS_VERIFIER")
    errors.extend(_missing_list(value.source_refs, "MISSING_SOURCE_REFS"))
    errors.extend(_missing_list(value.dod, "MISSING_DOD"))
    errors.extend(_missing_list(value.no_go_scope, "MISSING_NO_GO_SCOPE"))
    errors.extend(_missing_list(value.allowed_write_surfaces, "MISSING_ALLOWED_WRITE_SURFACES"))
    errors.extend(_missing_list(value.evidence_requirements, "MISSING_EVIDENCE_REQUIREMENTS"))
    errors.extend(secret_material_errors(value.to_dict(), path="task_unit"))
    return _result(errors)


def validate_owner_handoff_packet(value: OwnerHandoffPacket) -> StructuredTaskValidationResult:
    errors = _required(value, [
        "packet_id",
        "target_owner",
        "task_unit_ref",
        "required_context",
        "exact_input_docs",
        "no_go_boundaries",
        "expected_deliverables",
        "validation_commands_or_evidence",
        "due_or_timeout",
        "reply_format",
        "stop_escalation_path",
        "audit_ref",
    ])
    if not value.audit_ref:
        errors.append("MISSING_AUDIT_REF")
    errors.extend(secret_material_errors(value.to_dict(), path="owner_handoff_packet"))
    return _result(errors)


def _required(value: Any, names: list[str]) -> list[str]:
    errors: list[str] = []
    if not is_dataclass(value):
        return ["NOT_DATACLASS"]
    available = {field.name for field in fields(value)}
    for name in names:
        if name not in available:
            errors.append(f"MISSING_FIELD: {name}")
            continue
        item = getattr(value, name)
        if item in (None, "", [], {}):
            errors.append(f"MISSING_{name.upper()}")
    return _dedupe(errors)


def _missing_list(value: list[Any], error: str) -> list[str]:
    return [error] if not value else []


def _result(errors: list[str]) -> StructuredTaskValidationResult:
    deduped = _dedupe(errors)
    return StructuredTaskValidationResult(ok=not deduped, errors=deduped)


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error and error not in deduped:
            deduped.append(error)
    return deduped
