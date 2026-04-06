"""
langgraph_engine.nodes.viper_dev — Viper DEV stage node

DEV stage: performs DEV work, signals QA-ready.

Node contract:
- Receives GovernanceState
- Advances workitem from DEV to QA via StateMachine
- Checkpoints + emits event via harness
- Returns command: advance (done) or halt (blocked/error)
"""

from __future__ import annotations

from gov_langgraph.langgraph_engine.state import GovernanceState
from gov_langgraph.langgraph_engine.nodes.base import NodeCommand
from gov_langgraph.langgraph_engine.runtime import get_runtime
from gov_langgraph.platform_model import get_v1_pipeline_workflow, TaskStatus
from gov_langgraph.platform_model.state_machine import StateMachine


def viper_dev_node(state: GovernanceState) -> NodeCommand:
    """
    DEV stage node — advances workitem from DEV to QA.
    """
    rt = get_runtime()

    workitem = state.workitem
    if workitem is None:
        return {
            "current_action": "halt",
            "halt_reason": "DEV: workitem not in state",
        }

    sm = StateMachine(
        workflow=get_v1_pipeline_workflow(),
        checkpointer=rt.checkpointer,
        event_journal=rt.event_journal,
    )

    try:
        sm.advance_stage(
            work_item=workitem,
            target_stage="QA",
            actor_role="viper_dev",
            project_id=state.project_id,
        )

        rt.store.save_workitem(workitem)

        ts = rt.store.load_taskstate(workitem.task_id)
        ts.current_stage = "QA"
        ts.state_status = TaskStatus.IN_PROGRESS
        rt.store.save_taskstate(ts)

        return {"current_action": "advance"}

    except Exception as e:
        return {
            "current_action": "halt",
            "halt_reason": f"DEV: {e}",
        }
