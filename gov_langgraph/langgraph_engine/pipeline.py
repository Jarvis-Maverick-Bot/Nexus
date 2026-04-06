"""
langgraph_engine.pipeline — Pipeline compilation + execution

pipeline.compile() — returns CompiledStateGraph ready to run.
pipeline.run(workitem_id) — load workitem, run graph, return final state.

Usage:
    pipeline = compile()
    result = pipeline.invoke(initial_state)
"""

from __future__ import annotations

from typing import Optional

from gov_langgraph.langgraph_engine.graph import build_graph
from gov_langgraph.langgraph_engine.state import GovernanceState
from gov_langgraph.harness import HarnessConfig, StateStore


def compile():
    """
    Compile the V1 pipeline graph.

    Returns:
        CompiledStateGraph ready to invoke
    """
    graph = build_graph()
    return graph.compile()


def run_workitem(task_id: str, project_id: str) -> GovernanceState:
    """
    Run the pipeline for one workitem.

    Args:
        task_id: ID of the workitem to process
        project_id: project ID

    Returns:
        Final GovernanceState after graph execution
    """
    cfg = HarnessConfig()
    store = StateStore(cfg.state_dir)

    # Load workitem from StateStore
    workitem = store.load_workitem(task_id)

    # Initialize state
    initial_state = GovernanceState(
        project_id=project_id,
        task_id=task_id,
        workitem=workitem,
        current_action="advance",
    )

    # Compile and run
    pipeline = compile()
    result = pipeline.invoke(initial_state)

    return result


# Singleton compiled pipeline (lazily compiled once)
_compiled: Optional[any] = None


def get_pipeline():
    """
    Get the compiled pipeline (singleton, compiled once on first call).
    """
    global _compiled
    if _compiled is None:
        _compiled = compile()
    return _compiled
