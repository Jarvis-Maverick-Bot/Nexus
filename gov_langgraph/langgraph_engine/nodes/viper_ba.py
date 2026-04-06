"""
langgraph_engine.nodes.viper_ba — Viper BA stage node

BA stage: performs BA work, signals SA-ready.

Node contract:
  - Layer 1: pre_execution_check(role) — is viper_ba allowed in BA? (uses executing role, not initiator)
  - Layer 2: enforce_action(action) — is "create_artifact" permitted for viper_ba?
  - Layer 3: review_completion(handoff) — does handoff satisfy governance?
  - All actions routed through executor (no bypass)
  - Advances workitem from BA to SA via StateMachine
  - Checkpoint + emit event via harness
  - Returns: advance (done) or halt (authority failure / governance failure)
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
    BA stage node — executes viper_ba agent with governance enforcement.

    Authority separation:
      - state.actor = initiator (who started the pipeline run) — for event metadata only
      - agent.role_name = viper_ba = executing role — used for ALL authority checks
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

    # The explicit BA action — must be one of viper_ba's allowed_actions
    BA_ACTION = "create_artifact"  # viper_ba produces the BRD artifact

    try:
        # Execute with all 3 enforcement layers:
        #   Layer 1: pre_execution_check — is viper_ba allowed in BA? (NOT state.actor)
        #   Layer 2: enforce_action — is "create_artifact" allowed for viper_ba?
        #   Layer 3: review_completion — does handoff satisfy governance?
        #
        # initiator=state.actor goes into event metadata, NOT into authority checks
        handoff = executor.execute_with_enforcement(
            task_id=workitem.task_id,
            project_id=state.project_id,
            stage="BA",
            action=BA_ACTION,
            initiator=state.actor,  # tracked separately, NOT used for authority
        )

        # Advance workitem from BA -> SA
        sm = StateMachine(
            workflow=get_v1_pipeline_workflow(),
            checkpointer=rt.checkpointer,
            event_journal=rt.event_journal,
        )

        sm.advance_stage(
            work_item=workitem,
            target_stage="SA",
            actor_role=agent.role_name,  # viper_ba — not state.actor
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
