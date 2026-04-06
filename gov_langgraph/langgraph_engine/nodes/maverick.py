"""
langgraph_engine.nodes.maverick — Maverick coordinator node

PMO coordinator — routes workitems, assigns owners, monitors health.
Does NOT make sovereign governance decisions.

Maverick's role:
- Load workitem state from StateStore
- Check for blockers
- Monitor handoffs
- Route to appropriate stage node
- Emit monitor events
"""

from __future__ import annotations

from gov_langgraph.langgraph_engine.state import GovernanceState
from gov_langgraph.langgraph_engine.nodes.base import NodeCommand


def maverick_node(state: GovernanceState) -> NodeCommand:
    """
    Maverick coordinator node.

    Responsibilities:
    - Verify workitem is loaded
    - Check current stage and blocked status
    - Route to the appropriate stage node based on current_stage

    Returns:
        NodeCommand with action="advance" (routes to current stage node via edges)
    """
    if state.workitem is None:
        return {
            "action": "halt",
            "halt_reason": "maverick: workitem not loaded",
        }

    if state.blocked:
        return {
            "action": "block",
            "blocked": True,
            "blocker": state.blocker,
        }

    # Route to current stage node
    return {
        "action": "advance",
    }
