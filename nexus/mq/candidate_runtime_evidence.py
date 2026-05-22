"""Non-secret evidence shape helpers for candidate runtime implementation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from nexus.mq.agent_registry_events import secret_material_errors


EVIDENCE_SCHEMA_VERSION = "4.19.candidate.runtime.evidence.v1"


@dataclass
class CandidateRuntimeEvidenceRecord:
    evidence_type: str
    status: str
    refs: list[str]
    details: dict[str, Any] = field(default_factory=dict)
    schema_version: str = EVIDENCE_SCHEMA_VERSION
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_candidate_runtime_evidence(
    *,
    evidence_type: str,
    status: str,
    refs: list[str],
    details: dict[str, Any] | None = None,
) -> CandidateRuntimeEvidenceRecord:
    record = CandidateRuntimeEvidenceRecord(
        evidence_type=evidence_type,
        status=status,
        refs=list(refs),
        details=dict(details or {}),
    )
    errors = validate_candidate_runtime_evidence(record)
    if errors:
        raise ValueError("; ".join(errors))
    return record


def validate_candidate_runtime_evidence(record: CandidateRuntimeEvidenceRecord) -> list[str]:
    errors: list[str] = []
    if record.schema_version != EVIDENCE_SCHEMA_VERSION:
        errors.append("UNSUPPORTED_CANDIDATE_RUNTIME_EVIDENCE_SCHEMA")
    if record.not_business_completion is not True:
        errors.append("CANDIDATE_RUNTIME_EVIDENCE_CANNOT_BE_BUSINESS_COMPLETION")
    if not record.evidence_type:
        errors.append("MISSING_EVIDENCE_TYPE")
    if record.status not in {"accepted", "rejected", "blocked", "duplicate_suppressed", "candidate"}:
        errors.append(f"UNSUPPORTED_EVIDENCE_STATUS: {record.status}")
    if not record.refs:
        errors.append("MISSING_EVIDENCE_REFS")
    errors.extend(secret_material_errors(record.to_dict(), path="candidate_runtime_evidence"))
    return _dedupe(errors)


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error not in deduped:
            deduped.append(error)
    return deduped
