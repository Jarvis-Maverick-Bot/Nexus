"""Private-agent result candidate model for WBS 7.12."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from nexus.mq.agent_registry_events import secret_material_errors
from nexus.mq.private_agent_contract import PrivateAgentContract
from nexus.mq.private_task_package import PrivateAgentTaskPackage


PRIVATE_RESULT_CANDIDATE_SCHEMA_VERSION = "4.19.private_agent_result_candidate.v1"
STATUS_CLAIMS = {"success", "partial", "failed", "blocked"}
OUTPUT_TYPES = {"patch", "report", "data", "command_log", "artifact", "diagnostic_echo"}


@dataclass(frozen=True)
class PrivateResultOutput:
    output_ref: str
    output_type: str
    hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PrivateAgentResultCandidate:
    result_id: str
    assignment_id: str
    contract_id: str
    contract_revision: int
    task_package_id: str
    task_package_hash: str
    invocation_id: str
    status_claim: str
    summary: str
    outputs: list[PrivateResultOutput]
    evidence_refs: list[str]
    self_reported_risks: list[str]
    requested_followup_context: list[str]
    claims_business_completion: bool
    produced_at: str
    schema_version: str = PRIVATE_RESULT_CANDIDATE_SCHEMA_VERSION
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PrivateResultCandidateValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    quarantine_required: bool = False
    not_business_completion: bool = True


def validate_private_result_candidate(
    candidate: PrivateAgentResultCandidate,
    *,
    package: Optional[PrivateAgentTaskPackage] = None,
    contract: Optional[PrivateAgentContract] = None,
    now_at: Optional[str] = None,
) -> PrivateResultCandidateValidationResult:
    errors: list[str] = []
    quarantine_required = False
    if candidate.schema_version != PRIVATE_RESULT_CANDIDATE_SCHEMA_VERSION:
        errors.append("UNSUPPORTED_PRIVATE_RESULT_CANDIDATE_SCHEMA")
    if candidate.not_business_completion is not True:
        errors.append("PRIVATE_RESULT_CANDIDATE_CANNOT_BE_BUSINESS_COMPLETION")
    if candidate.claims_business_completion:
        errors.append("PRIVATE_RESULT_CANDIDATE_CANNOT_CLAIM_BUSINESS_COMPLETION")
        quarantine_required = True
    for field_name in [
        "result_id",
        "assignment_id",
        "contract_id",
        "task_package_id",
        "task_package_hash",
        "invocation_id",
        "status_claim",
        "summary",
        "produced_at",
    ]:
        if not getattr(candidate, field_name):
            errors.append(f"MISSING_{field_name.upper()}")
    if candidate.contract_revision <= 0:
        errors.append("PRIVATE_RESULT_CONTRACT_REVISION_INVALID")
    if candidate.status_claim not in STATUS_CLAIMS:
        errors.append(f"PRIVATE_RESULT_STATUS_CLAIM_INVALID: {candidate.status_claim}")
    if not candidate.outputs:
        errors.append("PRIVATE_RESULT_OUTPUTS_REQUIRED")
    if not candidate.evidence_refs:
        errors.append("PRIVATE_RESULT_EVIDENCE_REQUIRED")
    for output in candidate.outputs:
        output_errors = _output_errors(output)
        errors.extend(output_errors)
    if candidate.requested_followup_context:
        errors.append("PRIVATE_FOLLOWUP_CONTEXT_REQUESTED")
        quarantine_required = True
    produced_dt = _parse_iso(candidate.produced_at)
    if produced_dt is None:
        errors.append("PRIVATE_RESULT_PRODUCED_AT_INVALID")
    if package is not None:
        errors.extend(_package_mismatch_errors(candidate, package, now_at=now_at))
    if contract is not None:
        if candidate.contract_id != contract.contract_id or candidate.contract_revision != contract.contract_revision:
            errors.append("PRIVATE_RESULT_CONTRACT_MISMATCH")
    secret_errors = secret_material_errors(candidate.to_dict(), path="private_result_candidate")
    if secret_errors:
        errors.extend(secret_errors)
        quarantine_required = True
    return PrivateResultCandidateValidationResult(
        valid=not errors,
        errors=_dedupe(errors),
        quarantine_required=quarantine_required,
    )


def _output_errors(output: PrivateResultOutput) -> list[str]:
    errors: list[str] = []
    if not output.output_ref:
        errors.append("PRIVATE_RESULT_OUTPUT_REF_REQUIRED")
    if output.output_type not in OUTPUT_TYPES:
        errors.append(f"PRIVATE_RESULT_OUTPUT_TYPE_INVALID: {output.output_type}")
    if not output.hash:
        errors.append("PRIVATE_RESULT_OUTPUT_HASH_REQUIRED")
    errors.extend(secret_material_errors(output.to_dict(), path="private_result_output"))
    return errors


def _package_mismatch_errors(
    candidate: PrivateAgentResultCandidate,
    package: PrivateAgentTaskPackage,
    *,
    now_at: Optional[str],
) -> list[str]:
    errors: list[str] = []
    if candidate.assignment_id != package.assignment_id:
        errors.append("PRIVATE_RESULT_ASSIGNMENT_MISMATCH")
    if candidate.contract_id != package.contract_id or candidate.contract_revision != package.contract_revision:
        errors.append("PRIVATE_RESULT_CONTRACT_MISMATCH")
    if candidate.task_package_id != package.task_package_id:
        errors.append("PRIVATE_RESULT_TASK_PACKAGE_MISMATCH")
    if candidate.task_package_hash != package.package_hash:
        errors.append("PRIVATE_RESULT_TASK_PACKAGE_HASH_MISMATCH")
    expires_dt = _parse_iso(package.expires_at)
    now_dt = _parse_iso(now_at) if now_at else datetime.now(timezone.utc)
    if expires_dt is None:
        errors.append("PRIVATE_TASK_PACKAGE_EXPIRES_AT_INVALID")
    elif now_dt is None or expires_dt <= now_dt:
        errors.append("PRIVATE_TASK_PACKAGE_EXPIRED")
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
        if error not in deduped:
            deduped.append(error)
    return deduped
