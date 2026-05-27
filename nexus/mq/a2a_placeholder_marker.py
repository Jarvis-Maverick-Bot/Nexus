"""A2A V0.1 placeholder boundary.

4.19 V0.1 records that direct agent-to-agent routing is deferred. The helper
below returns a deterministic rejection and intentionally avoids state mutation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


A2A_PLACEHOLDER_STATUS = "A2A_V0_1_PLACEHOLDER_ONLY"


@dataclass
class A2APlaceholderDecision:
    accepted: bool
    status: str
    errors: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def reject_a2a_route_request(
    request: dict[str, Any],
    *,
    state: dict[str, Any] | None = None,
) -> A2APlaceholderDecision:
    _ = state
    return A2APlaceholderDecision(
        accepted=False,
        status=A2A_PLACEHOLDER_STATUS,
        errors=["A2A_DEFERRED_TO_V0_2"],
        payload={
            "source_agent_id": str(request.get("source_agent_id") or ""),
            "target_agent_id": str(request.get("target_agent_id") or ""),
            "assignment_id": str(request.get("assignment_id") or ""),
            "state_mutated": False,
        },
    )
