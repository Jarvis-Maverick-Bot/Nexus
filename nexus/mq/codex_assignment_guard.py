"""Codex assignment intake guard for WBS 7.19.13."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Optional

from nexus.mq.agent_registry import AgentRegistryRecord
from nexus.mq.agent_registry_events import secret_material_errors
from nexus.mq.candidate_runtime_lifecycle import evaluate_candidate_runtime_lifecycle


CODEX_ASSIGNMENT_METADATA_SCHEMA_VERSION = "4.19.codex.assignment_metadata.v1"
CODEX_ASSIGNMENT_INTAKE_SCHEMA_VERSION = "4.19.codex.assignment_intake.v1"
CODEX_ASSIGNMENT_KINDS = {
    "diagnostic_probe",
    "readiness_probe",
    "non_business_probe",
    "bounded_implementation_candidate",
    "business_task",
}


@dataclass
class CodexAssignmentAdapterMetadata:
    assignment_id: str
    run_id: str
    task_id: str
    packet_id: str
    packet_version: str
    target_agent_id: str
    target_runtime_instance_id: str
    assignment_kind: str
    business_execution_allowed: bool
    source_refs: list[str]
    source_hashes: list[str]
    workspace_ref: str
    repo_ref: str
    branch_or_worktree_policy_ref: str
    allowed_write_surfaces: list[str]
    prohibited_write_surfaces: list[str]
    allowed_tools: list[str]
    required_commands: list[str]
    evidence_requirements: list[str]
    no_go_scope: list[str]
    stop_conditions: list[str]
    timeout_policy_ref: str
    retry_policy_ref: str
    startup_packet_ref: str
    readiness_evidence_ref: str
    created_at: str
    expires_at: str
    schema_version: str = CODEX_ASSIGNMENT_METADATA_SCHEMA_VERSION
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CodexAssignmentIntake:
    intake_id: str
    idempotency_key: str
    assignment_id: str
    run_id: str
    task_id: str
    target_agent_id: str
    target_runtime_instance_id: str
    assignment_kind: str
    state: str
    accepted_at: str
    evidence_requirements: list[str]
    not_business_completion: bool = True
    schema_version: str = CODEX_ASSIGNMENT_INTAKE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CodexAssignmentIntakeDecision:
    accepted: bool
    intake: Optional[CodexAssignmentIntake] = None
    errors: list[str] = field(default_factory=list)
    duplicate_suppressed: bool = False
    not_business_completion: bool = True


def evaluate_codex_assignment_intake(
    *,
    metadata: CodexAssignmentAdapterMetadata,
    record: AgentRegistryRecord,
    now_at: str,
    prior_intakes: Optional[dict[str, str]] = None,
    allow_business_execution: bool = False,
) -> CodexAssignmentIntakeDecision:
    errors = _metadata_errors(metadata, now_at=now_at)
    errors.extend(_record_errors(metadata, record, now_at=now_at))
    if metadata.assignment_kind == "business_task" or metadata.business_execution_allowed:
        if not allow_business_execution:
            errors.append("CODEX_BUSINESS_EXECUTION_NOT_AUTHORIZED")
    if errors:
        return CodexAssignmentIntakeDecision(False, errors=_dedupe(errors))

    seed = "|".join(
        [
            metadata.assignment_id,
            metadata.run_id,
            metadata.packet_id,
            metadata.packet_version,
            metadata.target_runtime_instance_id,
        ]
    )
    digest = sha256(seed.encode("utf-8")).hexdigest()
    idempotency_key = f"codex-assignment-intake:{digest}"
    if prior_intakes and idempotency_key in prior_intakes:
        return CodexAssignmentIntakeDecision(
            True,
            intake=None,
            duplicate_suppressed=True,
            errors=["CODEX_DUPLICATE_ASSIGNMENT_SUPPRESSED"],
        )
    intake = CodexAssignmentIntake(
        intake_id=f"codex-intake-{digest[:16]}",
        idempotency_key=idempotency_key,
        assignment_id=metadata.assignment_id,
        run_id=metadata.run_id,
        task_id=metadata.task_id,
        target_agent_id=metadata.target_agent_id,
        target_runtime_instance_id=metadata.target_runtime_instance_id,
        assignment_kind=metadata.assignment_kind,
        state="accepted",
        accepted_at=now_at,
        evidence_requirements=list(metadata.evidence_requirements),
    )
    return CodexAssignmentIntakeDecision(True, intake=intake)


def _metadata_errors(metadata: CodexAssignmentAdapterMetadata, *, now_at: str) -> list[str]:
    errors: list[str] = []
    if metadata.schema_version != CODEX_ASSIGNMENT_METADATA_SCHEMA_VERSION:
        errors.append("UNSUPPORTED_CODEX_ASSIGNMENT_METADATA_SCHEMA")
    if metadata.not_business_completion is not True:
        errors.append("CODEX_ASSIGNMENT_METADATA_CANNOT_BE_BUSINESS_COMPLETION")
    for field_name in (
        "assignment_id",
        "run_id",
        "task_id",
        "packet_id",
        "packet_version",
        "target_agent_id",
        "target_runtime_instance_id",
        "assignment_kind",
        "source_refs",
        "source_hashes",
        "workspace_ref",
        "repo_ref",
        "branch_or_worktree_policy_ref",
        "allowed_tools",
        "required_commands",
        "evidence_requirements",
        "no_go_scope",
        "stop_conditions",
        "timeout_policy_ref",
        "retry_policy_ref",
        "startup_packet_ref",
        "readiness_evidence_ref",
        "created_at",
        "expires_at",
    ):
        if not getattr(metadata, field_name):
            errors.append(f"MISSING_CODEX_ASSIGNMENT_FIELD: {field_name}")
    if metadata.assignment_kind not in CODEX_ASSIGNMENT_KINDS:
        errors.append(f"UNSUPPORTED_CODEX_ASSIGNMENT_KIND: {metadata.assignment_kind}")
    if metadata.assignment_kind == "bounded_implementation_candidate" and not metadata.allowed_write_surfaces:
        errors.append("MISSING_CODEX_ASSIGNMENT_FIELD: allowed_write_surfaces")
    if set(metadata.allowed_write_surfaces).intersection(metadata.prohibited_write_surfaces):
        errors.append("CODEX_ALLOWED_WRITE_SURFACE_OVERLAPS_PROHIBITED")
    expires_dt = _parse_iso(metadata.expires_at)
    now_dt = _parse_iso(now_at)
    if expires_dt is None or now_dt is None:
        errors.append("CODEX_ASSIGNMENT_EXPIRY_INVALID")
    elif expires_dt <= now_dt:
        errors.append("CODEX_ASSIGNMENT_EXPIRED")
    errors.extend(secret_material_errors(metadata.to_dict(), path="codex_assignment_metadata"))
    return errors


def _record_errors(metadata: CodexAssignmentAdapterMetadata, record: AgentRegistryRecord, *, now_at: str) -> list[str]:
    errors: list[str] = []
    if record.runtime_provider != "codex":
        errors.append("CODEX_RUNTIME_PROVIDER_MISMATCH")
    if record.runtime_type != "coding_agent":
        errors.append("CODEX_RUNTIME_TYPE_MISMATCH")
    if metadata.target_agent_id != record.agent_id:
        errors.append("CODEX_TARGET_AGENT_MISMATCH")
    if metadata.target_runtime_instance_id != record.runtime_instance_id:
        errors.append("CODEX_TARGET_RUNTIME_MISMATCH")
    if metadata.startup_packet_ref != record.startup_packet_ref:
        errors.append("CODEX_STARTUP_PACKET_REF_MISMATCH")
    if metadata.readiness_evidence_ref != record.readiness_evidence_ref:
        errors.append("CODEX_READINESS_EVIDENCE_REF_MISMATCH")
    lifecycle = evaluate_candidate_runtime_lifecycle(record, now_at=now_at)
    errors.extend(lifecycle.errors)
    return errors


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error and error not in deduped:
            deduped.append(error)
    return deduped
