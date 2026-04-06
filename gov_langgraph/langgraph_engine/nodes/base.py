"""
langgraph_engine.nodes.base — Base node function pattern

Every node follows this contract:
- Receives GovernanceState
- Performs one bounded action within its role scope
- Returns a command dict (not a modified state directly)
- Does NOT own governance judgment
- Does NOT make routing decisions

Routing is handled by LangGraph's conditional edges based on current_action.
"""

from __future__ import annotations

from typing import Protocol

from gov_langgraph.langgraph_engine.state import GovernanceState


# Node return type — a command dict that LangGraph uses to update state
NodeCommand = dict


class NodeFunction(Protocol):
    """
    Protocol for a node function.

    Args:
        state: GovernanceState for this workitem

    Returns:
        NodeCommand dict with at minimum:
        - current_action: str — advance | block | handoff | halt | gate_approved | gate_rejected | done
        - Optionally: halt_reason, blocked, blocker to update state
    """

    def __call__(self, state: GovernanceState) -> NodeCommand:
        ...


# Valid node actions
VALID_ACTIONS = {
    "advance",   # Work is done, advance to next stage
    "block",     # Task is blocked, route to escalation
    "handoff",   # Handoff submitted, await acceptance
    "halt",      # Cannot proceed, halt and await intervention
    "gate_approved",  # Gate approved, advance
    "gate_rejected", # Gate rejected, halt and await intervention
    "done",      # Workitem is complete
}
