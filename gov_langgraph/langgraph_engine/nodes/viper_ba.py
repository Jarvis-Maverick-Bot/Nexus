"""
langgraph_engine.nodes.viper_ba — Viper BA stage node

BA stage: performs BA work, signals SA-ready.

Node contract:
- Receives GovernanceState
- Loads workitem from StateStore (if not already in state)
- Advances workitem from BA to SA via StateMachine
- Checkpoints + emits event
- Returns command: advance (done) or halt (blocked/error)
"""

from __future__ import annotations

from gov_langgraph.langgraph_engine.state import GovernanceState
from gov_langgraph.langgraph_engine.nodes.base import NodeCommand
from gov_langgraph.platform_model import get_v1_pipeline_workflow, TaskStatus
from gov_langgraph.harness import HarnessConfig, StateStore, Checkpointer, EventJournal
from gov_langgraph.platform_model.state_machine import StateMachine


def make_viper_node(stage: str, next_stage: str, role_owner: str):
    """
    Factory to create a stage node for a given stage.

    Args:
        stage: current stage (e.g. "BA")
        next_stage: next stage (e.g. "SA")
        role_owner: role that owns this stage (e.g. "viper_ba")
    """

    def node(state: GovernanceState) -> NodeCommand:
        cfg = HarnessConfig()
        cfg.ensure_dirs()
        store = StateStore(cfg.state_dir)
        ckpt = Checkpointer(cfg)
        journal = EventJournal(cfg.event_dir)

        # Load workitem if not in state
        workitem = state.workitem
        if workitem is None:
            return {
                "current_action": "halt",
                "halt_reason": f"{stage}: workitem not in state",
            }

        # Create StateMachine wired to harness
        sm = StateMachine(
            workflow=get_v1_pipeline_workflow(),
            checkpointer=ckpt,
            event_journal=journal,
        )

        # Try to advance
        try:
            record = sm.advance_stage(
                work_item=workitem,
                target_stage=next_stage,
                actor_role=role_owner,
                project_id=state.project_id,
            )

            # Persist updated workitem
            store.save_workitem(workitem)

            # Update task state
            try:
                ts = store.load_taskstate(workitem.task_id)
                ts.current_stage = next_stage
                ts.state_status = TaskStatus.IN_PROGRESS
                store.save_taskstate(ts)
            except Exception:
                pass

            return {
                "current_action": "advance",
            }

        except Exception as e:
            error_msg = str(e)
            return {
                "current_action": "halt",
                "halt_reason": f"{stage}: {error_msg}",
            }

    return node


# Convenience: named BA node
viper_ba_node = make_viper_node("BA", "SA", "viper_ba")
