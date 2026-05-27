"""Readiness taxonomy guard for 4.19 real-agent operating evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


FORBIDDEN_FINAL_READY_LABEL = "THUNDER_REAL_AGENT_OPERATING_ENVIRONMENT_READY"


@dataclass
class RealAgentEvidenceStatus:
    integrated_package_complete: bool
    phase3_minitest_only: bool
    diagnostic_only: bool
    source_evidence_refs: list[str] = field(default_factory=list)
    not_business_completion: bool = True


@dataclass
class RealAgentReadinessClassification:
    status: str
    ready_label_allowed: bool
    diagnostic_only: bool
    final_readiness_claimed: bool
    errors: list[str] = field(default_factory=list)
    forbidden_final_label: str = FORBIDDEN_FINAL_READY_LABEL
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_real_agent_readiness(evidence: RealAgentEvidenceStatus) -> RealAgentReadinessClassification:
    errors: list[str] = []
    if evidence.not_business_completion is not True:
        errors.append("REAL_AGENT_READINESS_CANNOT_BE_BUSINESS_COMPLETION")
    if evidence.phase3_minitest_only or evidence.diagnostic_only:
        if evidence.phase3_minitest_only:
            errors.append("PHASE3_MINITEST_DIAGNOSTIC_ONLY")
        if evidence.diagnostic_only:
            errors.append("DIAGNOSTIC_EVIDENCE_ONLY")
        return RealAgentReadinessClassification(
            status="DIAGNOSTIC_ONLY",
            ready_label_allowed=False,
            diagnostic_only=True,
            final_readiness_claimed=False,
            errors=_dedupe(errors),
        )
    if not evidence.integrated_package_complete:
        errors.append("INTEGRATED_EVIDENCE_PACKAGE_INCOMPLETE")
        return RealAgentReadinessClassification(
            status="BLOCKED_INCOMPLETE_PACKAGE",
            ready_label_allowed=False,
            diagnostic_only=False,
            final_readiness_claimed=False,
            errors=_dedupe(errors),
        )
    return RealAgentReadinessClassification(
        status="READY_FOR_NOVA_REVIEW",
        ready_label_allowed=True,
        diagnostic_only=False,
        final_readiness_claimed=False,
        errors=_dedupe(errors),
    )


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error and error not in deduped:
            deduped.append(error)
    return deduped
