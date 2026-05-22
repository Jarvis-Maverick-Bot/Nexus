"""Deterministic candidate runtime scheduler for WBS 7.18."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any, Optional

from nexus.mq.agent_registry import AgentRegistryRecord
from nexus.mq.candidate_runtime_capacity import CandidateRuntimeCapacitySnapshot, evaluate_capacity_before_claim
from nexus.mq.candidate_runtime_lifecycle import evaluate_candidate_runtime_lifecycle
from nexus.mq.dispatch_request import BUSINESS_ASSIGNMENT_KIND, DispatchRequest, validate_dispatch_request


@dataclass
class CandidateRuntimeClaim:
    claim_id: str
    idempotency_key: str
    request_id: str
    correlation_id: str
    target_agent_id: str
    target_runtime_instance_id: str
    registry_revision_seen: int
    capacity_revision_seen: int
    assignment_kind: str
    required_capability: str
    required_authority_scope: str
    required_privacy_scope: str
    allowed_task_boundary: str
    business_execution_allowed: bool
    no_go_scope: list[str]
    evidence_refs: list[str] = field(default_factory=list)
    state: str = "claim_candidate"
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CandidateSchedulerDecision:
    accepted: bool
    claim: Optional[CandidateRuntimeClaim] = None
    errors: list[str] = field(default_factory=list)
    duplicate_suppressed: bool = False
    not_business_completion: bool = True


def build_candidate_runtime_claim(
    *,
    request: DispatchRequest,
    record: AgentRegistryRecord,
    registry_revision_seen: int,
    capacity_snapshot: Optional[CandidateRuntimeCapacitySnapshot],
    now_at: str,
    prior_claims: Optional[dict[str, str]] = None,
) -> CandidateSchedulerDecision:
    request_validation = validate_dispatch_request(request, now_at=now_at)
    errors = list(request_validation.errors)
    if request.assignment_kind == BUSINESS_ASSIGNMENT_KIND or request.business_dispatch_authorized:
        errors.append("BUSINESS_DISPATCH_NOT_AUTHORIZED")
    lifecycle = evaluate_candidate_runtime_lifecycle(record, now_at=now_at)
    errors.extend(lifecycle.errors)
    errors.extend(_scope_errors(request, record))
    capacity = evaluate_capacity_before_claim(
        capacity_snapshot,
        runtime_instance_id=record.runtime_instance_id,
        required_claim_class=request.assignment_kind,
        now_at=now_at,
    )
    errors.extend(capacity.errors)
    if registry_revision_seen <= 0:
        errors.append("INVALID_REGISTRY_REVISION_SEEN")
    if errors:
        return CandidateSchedulerDecision(False, errors=_dedupe(errors))

    seed = "|".join(
        [
            request.request_id,
            request.correlation_id,
            record.agent_id,
            record.runtime_instance_id,
            str(registry_revision_seen),
            str(capacity.capacity_revision),
        ]
    )
    digest = sha256(seed.encode("utf-8")).hexdigest()
    idempotency_key = f"candidate-runtime-claim:{digest}"
    if prior_claims and idempotency_key in prior_claims:
        return CandidateSchedulerDecision(
            accepted=True,
            claim=None,
            duplicate_suppressed=True,
            errors=["DUPLICATE_CLAIM_SUPPRESSED"],
        )
    claim = CandidateRuntimeClaim(
        claim_id=f"candidate-claim-{digest[:16]}",
        idempotency_key=idempotency_key,
        request_id=request.request_id,
        correlation_id=request.correlation_id,
        target_agent_id=record.agent_id,
        target_runtime_instance_id=record.runtime_instance_id,
        registry_revision_seen=registry_revision_seen,
        capacity_revision_seen=capacity.capacity_revision or 0,
        assignment_kind=request.assignment_kind,
        required_capability=request.required_capability,
        required_authority_scope=request.required_authority_scope,
        required_privacy_scope=request.required_privacy_scope,
        allowed_task_boundary=request.allowed_task_boundary,
        business_execution_allowed=False,
        no_go_scope=list(request.no_go_scope),
        evidence_refs=[*request.evidence_refs, capacity_snapshot.evidence_ref if capacity_snapshot else ""],
    )
    return CandidateSchedulerDecision(True, claim=claim)


def _scope_errors(request: DispatchRequest, record: AgentRegistryRecord) -> list[str]:
    errors: list[str] = []
    if request.target_agent_id and request.target_agent_id != record.agent_id:
        errors.append("TARGET_AGENT_ID_MISMATCH")
    if request.target_runtime_instance_id and request.target_runtime_instance_id != record.runtime_instance_id:
        errors.append("TARGET_RUNTIME_INSTANCE_MISMATCH")
    if request.required_capability not in record.capabilities:
        errors.append("CAPABILITY_MISMATCH")
    if request.required_authority_scope not in record.authority_scopes:
        errors.append("AUTHORITY_SCOPE_MISMATCH")
    if request.required_privacy_scope not in record.privacy_scopes:
        errors.append("PRIVACY_SCOPE_MISMATCH")
    if request.allowed_task_boundary not in record.allowed_task_boundaries:
        errors.append("TASK_BOUNDARY_MISMATCH")
    return errors


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error and error not in deduped:
            deduped.append(error)
    return deduped
