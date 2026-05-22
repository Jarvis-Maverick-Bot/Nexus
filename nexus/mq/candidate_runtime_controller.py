"""Pure candidate runtime controller decisions for WBS 7.18."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from nexus.mq.agent_registry import AgentRegistryRecord
from nexus.mq.candidate_runtime_capacity import CandidateRuntimeCapacitySnapshot
from nexus.mq.candidate_runtime_lifecycle import evaluate_candidate_runtime_lifecycle
from nexus.mq.candidate_runtime_scheduler import CandidateSchedulerDecision, build_candidate_runtime_claim
from nexus.mq.dispatch_request import DispatchRequest


@dataclass
class CandidateControllerPolicy:
    controller_enabled: bool = True
    emergency_stop: bool = False
    allow_business_dispatch: bool = False


@dataclass
class CandidateControllerDecision:
    accepted: bool
    scheduler_decision: Optional[CandidateSchedulerDecision] = None
    errors: list[str] = field(default_factory=list)
    not_business_completion: bool = True


def evaluate_candidate_controller_preflight(
    *,
    record: Optional[AgentRegistryRecord],
    policy: CandidateControllerPolicy,
    now_at: str,
) -> CandidateControllerDecision:
    if not policy.controller_enabled:
        return CandidateControllerDecision(False, errors=["CANDIDATE_CONTROLLER_DISABLED"])
    if policy.emergency_stop:
        return CandidateControllerDecision(False, errors=["CANDIDATE_CONTROLLER_EMERGENCY_STOP"])
    lifecycle = evaluate_candidate_runtime_lifecycle(record, now_at=now_at)
    return CandidateControllerDecision(lifecycle.accepted, errors=lifecycle.errors)


def evaluate_candidate_assignment(
    *,
    request: DispatchRequest,
    record: AgentRegistryRecord,
    registry_revision_seen: int,
    capacity_snapshot: Optional[CandidateRuntimeCapacitySnapshot],
    policy: CandidateControllerPolicy,
    now_at: str,
) -> CandidateControllerDecision:
    preflight = evaluate_candidate_controller_preflight(record=record, policy=policy, now_at=now_at)
    if not preflight.accepted:
        return preflight
    if request.business_dispatch_authorized and not policy.allow_business_dispatch:
        return CandidateControllerDecision(False, errors=["BUSINESS_DISPATCH_NOT_AUTHORIZED"])
    scheduler = build_candidate_runtime_claim(
        request=request,
        record=record,
        registry_revision_seen=registry_revision_seen,
        capacity_snapshot=capacity_snapshot,
        now_at=now_at,
    )
    return CandidateControllerDecision(scheduler.accepted, scheduler_decision=scheduler, errors=scheduler.errors)
