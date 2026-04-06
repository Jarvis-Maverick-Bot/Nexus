"""
langgraph_engine.nodes.viper_ba — Viper BA stage node

BA stage: performs BA work, signals SA-ready.

Node contract:
- Receives GovernanceState
- Loads workitem from StateStore (if not already in state)
- Advances workitem from BA to SA via StateMachine
- Checkpoints + emits event via harness
- Returns command: advance (done) or halt (blocked/error)
"""

from __future__ import annotations

from gov_langgraph.langgraph_engine.state import GovernanceState
from gov_langgraph.langgraph_engine.nodes.base import NodeCommand
from gov_langgraph.langgraph_engine.runtime import get_runtime
from gov_langgraph.platform_model import get_v1_pipeline_workflow, TaskStatus
from gov_langgraph.platform_model.state_machine import StateMachine


def viper_ba_node(state: GovernanceState) -> NodeCommand:
    """
    BA stage node — advances workitem from BA to SA.
    """
    rt = get_runtime()

    workitem = state.workitem
    if workitem is None:
        return {
            "current_action": "halt",
            "halt_reason": "BA: workitem not in state",
        }

    sm = StateMachine(
        workflow=get_v1_pipeline_workflow(),
        checkpointer=rt.checkpointer,
        event_journal=rt.event_journal,
    )

    try:
        sm.advance_stage(
            work_item=workitem,
            target_stage="SA",
            actor_role="viper_ba",
            project_id=state.project_id,
        )

        # Persist updated workitem
        rt.store.save_workitem(workitem)

        # Update task state — propagate error if this fails
        ts = rt.store.load_taskstate(workitem.task_id)
        ts.current_stage = "SA"
        ts.state_status = TaskStatus.IN_PROGRESS
        rt.store.save_taskstate(ts)

        return {"current_action": "advance"}

    except Exception as e:
        return {
            "current_action": "halt",
            "halt_reason": f"BA: {e}",
        }
