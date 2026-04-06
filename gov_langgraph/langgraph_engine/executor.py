"""
langgraph_engine.executor — Agent Executor

Routes agent actions through the LangGraph pipeline.
Agent cannot bypass the pipeline — all actions go through stage nodes.

Nova decision (2026-04-06): LOCKED for V1.
Authority enforcement:
  1. Pre-execution check: Is this role allowed to attempt this stage?
  2. Tool/action-level: Is this exact action allowed for this role on this object?
  3. Completion review: Did the output satisfy governance conditions?

No async, no background polling, no hidden control loops.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from gov_langgraph.platform_model import (
    check_authority, Action, Role,
    HandoffDocument, Event,
)
from gov_langgraph.langgraph_engine.agent import (
    RoleShapedAgent, make_agent_for_stage, AgentStatus,
)
from gov_langgraph.langgraph_engine.runtime import get_runtime


class AgentExecutor:
    """
    Executes a role-shaped agent within governance boundaries.

    Enforcement layers:
      1. Pre-execution: role allowed to attempt this stage?
      2. Action-level: is action permitted for this role?
      3. Completion: does output satisfy governance conditions?
    """

    def __init__(self, agent: RoleShapedAgent):
        self.agent = agent
        self._last_handoff: Optional[HandoffDocument] = None
        self._last_event: Optional[Event] = None
        self._halt_reason: Optional[str] = None

    def pre_execution_check(self, stage: str, actor_role: str) -> None:
        """
        Layer 1: Pre-execution authority check.

        Raises:
            PermissionError — role is not allowed in this stage
        """
        if not self.agent.can_act_in_stage(stage):
            self.agent.halt(f"Role {actor_role} denied: stage '{stage}' not in {self.agent.allowed_stages}")
            self._halt_reason = f"pre_execution_denied: {actor_role} cannot act in {stage}"
            raise PermissionError(self._halt_reason)

    def check_action(self, action: str) -> None:
        """
        Layer 2: Action-level authority check.

        Raises:
            PermissionError — action is not permitted for this role
        """
        if not self.agent.can_take_action(action):
            self.agent.halt(f"Action '{action}' not permitted for role {self.agent.role_name}")
            self._halt_reason = f"action_denied: {action} not permitted for {self.agent.role_name}"
            raise PermissionError(self._halt_reason)

    def execute_with_enforcement(
        self,
        task_id: str,
        project_id: str,
        stage: str,
        actor_role: str,
    ) -> HandoffDocument:
        """
        Execute agent with all 3 enforcement layers.

        1. Pre-execution: is role allowed in this stage?
        2. Execute: synchronous agent execution
        3. Completion review: did handoff document satisfy governance?

        Returns:
            HandoffDocument if all checks pass

        Raises:
            PermissionError — authority check failed
            ValueError — handoff incomplete
        """
        # Layer 1: Pre-execution check
        self.pre_execution_check(stage, actor_role)

        # Layer 2: Execute agent synchronously
        try:
            handoff = self.agent.execute(task_id, project_id, stage)
        except PermissionError:
            raise
        except RuntimeError as e:
            self._halt_reason = f"execution_error: {e}"
            self.agent.halt(str(e))
            raise

        # Layer 3: Completion review
        if not handoff.is_complete():
            self._halt_reason = "completion_denied: handoff incomplete"
            self.agent.halt("Handoff incomplete, does not satisfy governance conditions")
            raise ValueError("HandoffDocument is incomplete, cannot advance stage")

        # Record handoff
        self._last_handoff = handoff

        # Write event to journal
        self._write_event(task_id, project_id, stage, handoff)

        return handoff

    def _write_event(self, task_id: str, project_id: str, stage: str, handoff: HandoffDocument) -> None:
        """Write agent execution event to the event journal."""
        try:
            rt = get_runtime()
            event = Event(
                event_type="agent_executed",
                project_id=project_id,
                task_id=task_id,
                actor=handoff.producer_role,
                event_summary=f"{handoff.producer_role} completed stage {stage}, produced {len(handoff.artifact_references)} artifact(s)",
                metadata={
                    "stage": stage,
                    "handoff_status": handoff.status,
                    "artifact_count": len(handoff.artifact_references),
                    "to_stage": handoff.to_stage,
                },
            )
            rt.event_journal.append(event)
        except Exception:
            # Event journal failure should not halt the pipeline
            pass

    def was_halted(self) -> bool:
        return self.agent.is_halted()

    def halt_reason(self) -> Optional[str]:
        return self._halt_reason or self.agent.halt_reason

    def last_handoff(self) -> Optional[HandoffDocument]:
        return self._last_handoff
