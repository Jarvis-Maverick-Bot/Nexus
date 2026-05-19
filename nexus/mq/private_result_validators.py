"""Layered validators for private-agent result candidates."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from nexus.mq.agent_registry_events import secret_material_errors
from nexus.mq.private_result_candidate import PrivateAgentResultCandidate, validate_private_result_candidate
from nexus.mq.private_task_package import PrivateAgentTaskPackage


@dataclass(frozen=True)
class PrivateValidationStageResult:
    stage: str
    status: str
    accepted: bool
    errors: list[str] = field(default_factory=list)
    quarantine_required: bool = False
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PrivateValidationDecision:
    evidence: PrivateValidationStageResult
    safety: PrivateValidationStageResult
    governed: PrivateValidationStageResult
    business_state_committed: bool = False
    result_state: str = "result_candidate"
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_evidence_validator(
    candidate: PrivateAgentResultCandidate,
    package: PrivateAgentTaskPackage,
) -> PrivateValidationStageResult:
    validation = validate_private_result_candidate(candidate, package=package, now_at=candidate.produced_at)
    errors = list(validation.errors)
    missing = [item for item in package.evidence_required if item not in candidate.evidence_refs]
    if missing:
        errors.append("PRIVATE_RESULT_REQUIRED_EVIDENCE_MISSING")
    return PrivateValidationStageResult(
        stage="evidence",
        status="evidence_valid" if not errors else "evidence_rejected",
        accepted=not errors,
        errors=_dedupe(errors),
        quarantine_required=validation.quarantine_required,
    )


def run_safety_validator(
    candidate: PrivateAgentResultCandidate,
    package: PrivateAgentTaskPackage,
    *,
    evidence: PrivateValidationStageResult,
) -> PrivateValidationStageResult:
    errors: list[str] = []
    quarantine_required = False
    if not evidence.accepted:
        errors.append("PRIVATE_SAFETY_REQUIRES_EVIDENCE_VALID")
    if candidate.requested_followup_context:
        errors.append("PRIVATE_FOLLOWUP_CONTEXT_REQUESTED")
        quarantine_required = True
    if candidate.claims_business_completion:
        errors.append("PRIVATE_RESULT_CANDIDATE_CANNOT_CLAIM_BUSINESS_COMPLETION")
        quarantine_required = True
    secret_errors = secret_material_errors(candidate.to_dict(), path="private_result_candidate")
    if secret_errors:
        errors.extend(secret_errors)
        quarantine_required = True
    if package.task_kind != "diagnostic":
        errors.append("PRIVATE_DIAGNOSTIC_ONLY")
    return PrivateValidationStageResult(
        stage="safety",
        status="safety_passed" if not errors else "safety_rejected",
        accepted=not errors,
        errors=_dedupe(errors),
        quarantine_required=quarantine_required,
    )


def run_governed_validator(
    candidate: PrivateAgentResultCandidate,
    package: PrivateAgentTaskPackage,
    *,
    evidence: PrivateValidationStageResult,
    safety: PrivateValidationStageResult,
    governed_authority_approved: bool = False,
    business_commit_authorized: bool = False,
) -> PrivateValidationStageResult:
    errors: list[str] = []
    if not evidence.accepted:
        errors.append("PRIVATE_GOVERNED_REQUIRES_EVIDENCE_VALID")
    if not safety.accepted:
        errors.append("PRIVATE_GOVERNED_REQUIRES_SAFETY_PASSED")
    if not governed_authority_approved:
        errors.append("PRIVATE_GOVERNED_AUTHORITY_REQUIRED")
    if not business_commit_authorized:
        errors.append("PRIVATE_BUSINESS_COMMIT_NOT_AUTHORIZED")
    if candidate.claims_business_completion:
        errors.append("PRIVATE_RESULT_CANDIDATE_CANNOT_CLAIM_BUSINESS_COMPLETION")
    if package.task_kind == "diagnostic":
        errors.append("PRIVATE_DIAGNOSTIC_RESULT_NOT_BUSINESS_COMPLETION")
    return PrivateValidationStageResult(
        stage="governed",
        status="governed_accepted" if not errors else "governed_rejected",
        accepted=not errors,
        errors=_dedupe(errors),
        quarantine_required=safety.quarantine_required,
    )


def validate_private_result_candidate_chain(
    candidate: PrivateAgentResultCandidate,
    package: PrivateAgentTaskPackage,
    *,
    governed_authority_approved: bool = False,
    business_commit_authorized: bool = False,
) -> PrivateValidationDecision:
    evidence = run_evidence_validator(candidate, package)
    safety = run_safety_validator(candidate, package, evidence=evidence)
    governed = run_governed_validator(
        candidate,
        package,
        evidence=evidence,
        safety=safety,
        governed_authority_approved=governed_authority_approved,
        business_commit_authorized=business_commit_authorized,
    )
    return PrivateValidationDecision(
        evidence=evidence,
        safety=safety,
        governed=governed,
        business_state_committed=False,
        result_state="result_candidate",
    )


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error not in deduped:
            deduped.append(error)
    return deduped
