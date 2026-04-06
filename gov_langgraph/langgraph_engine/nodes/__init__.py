"""
langgraph_engine.nodes — Node registry for LangGraph graph

Node registry maps stage names to node functions.
"""

from gov_langgraph.langgraph_engine.nodes.base import NodeFunction

# Node registry: stage name -> node function
NODE_REGISTRY: dict[str, NodeFunction] = {}


def register_node(stage: str, node_fn: NodeFunction) -> None:
    """Register a node function for a stage."""
    NODE_REGISTRY[stage] = node_fn


def get_node(stage: str) -> NodeFunction:
    """Get the node function for a stage."""
    if stage not in NODE_REGISTRY:
        raise KeyError(f"No node registered for stage: {stage}")
    return NODE_REGISTRY[stage]


__all__ = ["NodeFunction", "NODE_REGISTRY", "register_node", "get_node"]
