"""Operational runtime metrics projection for 4.19 real-agent supply."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from nexus.mq.eligibility_reservation_policy import RuntimeEligibilityDecision, RuntimeReservationLease
from nexus.mq.runtime_lifecycle_controller import RuntimeLifecycleRecord


@dataclass
class RuntimeMetricsProjection:
    registered_runtime_count: int
    idle_runtime_count: int
    stale_or_offline_runtime_count: int
    allowed_decision_count: int
    blocked_decision_count: int
    active_lease_count: int
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_runtime_metrics_projection(
    *,
    runtimes: list[RuntimeLifecycleRecord],
    decisions: list[RuntimeEligibilityDecision],
    leases: list[RuntimeReservationLease],
) -> RuntimeMetricsProjection:
    return RuntimeMetricsProjection(
        registered_runtime_count=len(runtimes),
        idle_runtime_count=len([runtime for runtime in runtimes if runtime.lifecycle_state == "idle"]),
        stale_or_offline_runtime_count=len(
            [runtime for runtime in runtimes if runtime.presence_state in {"stale", "offline"}]
        ),
        allowed_decision_count=len([decision for decision in decisions if decision.accepted]),
        blocked_decision_count=len([decision for decision in decisions if not decision.accepted]),
        active_lease_count=len([lease for lease in leases if lease.active and lease.status == "active"]),
    )
