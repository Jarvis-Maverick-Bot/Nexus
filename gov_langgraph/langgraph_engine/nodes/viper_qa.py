"""
langgraph_engine.nodes.viper_qa — Viper QA stage node

QA stage: performs QA work, signals done (terminal stage).

QA is the terminal stage — workitem is complete when it reaches QA.
Node explicitly returns "done" (halts at END, not via invalid transition).
"""

from __future__ import annotations

from gov_langgraph.langgraph_engine.state import GovernanceState
from gov_langgraph.langgraph_engine.nodes.base import NodeCommand
from gov_langgraph.langgraph_engine.runtime import get_runtime
from gov_langgraph.platform_model import TaskStatus


def viper_qa_node(state: GovernanceState) -> NodeCommand:
    """
    QA stage node — marks workitem as complete.

    QA is the terminal stage. This node:
    1. Loads TaskState
    2. Marks task as DONE
    3. Persists updated TaskState
    4. Returns "done" (halts graph normally at END)
    """
    rt = get_runtime()

    workitem = state.workitem
    if workitem is None:
        return {
            "current_action": "halt",
            "halt_reason": "QA: workitem not in state",
        }

    try:
        ts = rt.store.load_taskstate(workitem.task_id)
        ts.current_stage = "QA"
        ts.state_status = TaskStatus.DONE
        rt.store.save_taskstate(ts)

        # Persist workitem as complete
        workitem.current_stage = "QA"
        rt.store.save_workitem(workitem)

        return {"current_action": "done"}

    except Exception as e:
        return {
            "current_action": "halt",
            "halt_reason": f"QA: {e}",
        }
