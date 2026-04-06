"""
langgraph_engine.graph — LangGraph StateGraph scaffold

Graph structure:
    START -> maverick
    maverick -> (conditional on workitem.current_stage) -> BA | SA | DEV | QA | END
    BA -> (conditional on action) -> SA | DEV | QA | END
    SA -> (conditional on action) -> DEV | QA | END
    DEV -> (conditional on action) -> QA | END
    QA -> (conditional on action) -> END

Stage routing:
    - "advance" -> next stage (or END if at QA)
    - "halt" -> END (graph stops, checkpoint saved)
    - "done" -> END (normal completion)

Maverick routing:
    - Routes to the stage matching workitem.current_stage
    - Halts on: halt_reason, workitem missing, block, done, gate_rejected
"""

from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from gov_langgraph.langgraph_engine.state import GovernanceState


# Valid stage sequence
STAGE_SEQUENCE = ["BA", "SA", "DEV", "QA"]


def _next_stage(current: str) -> str | type[END]:
    """Return the next stage after current, or END if at terminal."""
    idx = STAGE_SEQUENCE.index(current)
    if idx + 1 < len(STAGE_SEQUENCE):
        return f"__stage_{STAGE_SEQUENCE[idx + 1]}__"
    return END


def build_graph() -> StateGraph:
    """
    Build the V1 pipeline StateGraph scaffold.

    Nodes are stubs in this file — real implementation in Day 2.
    """
    graph = StateGraph(state_schema=GovernanceState)

    # Import nodes
    from gov_langgraph.langgraph_engine.nodes.maverick import maverick_node
    from gov_langgraph.langgraph_engine.nodes import register_node

    # Register real stage nodes (Day 2 will replace these stubs)
    for stage in STAGE_SEQUENCE:
        node_name = f"__stage_{stage}__"
        graph.add_node(node_name, _make_stage_stub(stage))

    # Entry point: maverick
    graph.add_node("__maverick__", maverick_node)
    graph.add_edge(START, "__maverick__")

    # Maverick routes to the current stage node
    graph.add_conditional_edges(
        "__maverick__",
        _maverick_router,
        {
            "__stage_BA__": "__stage_BA__",
            "__stage_SA__": "__stage_SA__",
            "__stage_DEV__": "__stage_DEV__",
            "__stage_QA__": "__stage_QA__",
        },
    )

    # Each stage node routes based on its action
    for stage in STAGE_SEQUENCE:
        node_name = f"__stage_{stage}__"
        next_node = _next_stage(stage)
        edge_map = {
            "__advance__": next_node,
            "__halt__": END,
            "__done__": END,
        }
        graph.add_conditional_edges(node_name, _stage_router, edge_map)

    return graph


def _maverick_router(state: GovernanceState) -> str:
    """Maverick routes to the current stage based on workitem."""
    if state.halt_reason or state.current_action == "halt":
        return END
    if state.current_action in ("block", "done", "gate_rejected"):
        return END
    if state.workitem is None:
        return END
    return f"__stage_{state.workitem.current_stage}__"


def _stage_router(state: GovernanceState) -> str:
    """Stage node routes based on the action it set in state."""
    action = state.current_action
    if action == "advance":
        return "__advance__"
    elif action in ("halt", "done", "gate_rejected"):
        return "__halt__"
    else:
        # Unknown action — halt for safety
        return "__halt__"


def _make_stage_stub(stage: str):
    """
    Create a stub node for a stage.
    Replaced by real implementation in Day 2.
    """

    def stub(state: GovernanceState):
        return {
            "current_action": "halt",
            "halt_reason": f"{stage} node: not yet implemented",
        }

    return stub
