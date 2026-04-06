"""
langgraph_engine.nodes.viper_ba — Viper BA stage node

BA stage: performs BA work, signals SA-ready.

Node contract:
- Layer 1 (pre-execution): is role allowed in BA stage?
- Layer 2 (agent execution): produce handoff document
- Layer 3 (completion review): is handoff complete?
- All actions routed through executor (no bypass)
- Advances workitem from BA to SA via StateMachine
- Checkpoint + emit event via harness
- Returns command: advance (done) or halt (blocked/error)
"""

from __future__ import annotations

from gov_langgraph.langgraph_engine.state import GovernanceState
from gov_langgraph.langgraph_engine.nodes.base import NodeCommand
from gov_langgraph.langgraph_engine.runtime import get_runtime
from gov_langgraph.langgraph_engine.executor import AgentExecutor
from gov_langgraph.langgraph_engine.agent import make_viper_ba
from gov_langgraph.platform_model import get_v1_pipeline_workflow, TaskStatus
from gov_langgraph.platform_model.state_machine import StateMachine


def viper_ba_node(state: GovernanceState) -> NodeCommand:
    """
    BA stage node — executes BA agent with governance enforcement.
    """
    rt = get_runtime()

    workitem = state.workitem
    if workitem is None:
        return {
            "current_action": "halt",
            "halt_reason": "BA: workitem not in state",
        }

    # Create role-shaped BA agent + executor
    agent = make_viper_ba()
    executor = AgentExecutor(agent)

    try:
        # Execute with all 3 enforcement layers
        # Executor handles event journaling internally
        handoff = executor.execute_with_enforcement(
            task_id=workitem.task_id,
            project_id=state.project_id,
            stage="BA",
            actor_role=state.actor or "viper_ba",
        )

        # Advance stage via StateMachine
        sm = StateMachine(
            workflow=get_v1_pipeline_workflow(),
            checkpointer=rt.checkpointer,
            event_journal=rt.event_journal,
        )

        sm.advance_stage(
            work_item=workitem,
            target_stage="SA",
            actor_role=state.actor or "viper_ba",
            project_id=state.project_id,
        )

        # Persist updated workitem + task state
        rt.store.save_workitem(workitem)
        ts = rt.store.load_taskstate(workitem.task_id)
        ts.current_stage = "SA"
        ts.state_status = TaskStatus.IN_PROGRESS
        rt.store.save_taskstate(ts)

        return {"current_action": "advance"}

    except PermissionError as e:
        return {
            "current_action": "halt",
            "halt_reason": f"BA authority denied: {e}",
        }
    except ValueError as e:
        return {
            "current_action": "halt",
            "halt_reason": f"BA governance failure: {e}",
        }
    except Exception as e:
        return {
            "current_action": "halt",
            "halt_reason": f"BA: {e}",
        }
