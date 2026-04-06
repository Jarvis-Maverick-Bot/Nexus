"""
langgraph_engine.executor — Agent Executor

Routes agent actions through the LangGraph pipeline.
Agent cannot bypass the pipeline — all actions go through stage nodes.

Nova decision (2026-04-06): LOCKED for V1.

Authority enforcement (3 layers, all mandatory):
  1. Pre-execution: is this role allowed to attempt this stage?
  2. Action-specific: is this exact action permitted for this role?
  3. Completion: did handoff satisfy governance?

Failure handling:
  - Authority failures (layers 1-2): ALWAYS propagate — no silent swallow
  - Event journal failure: silently contained (does not halt pipeline)
  - Handoff completeness failure: propagates as ValueError

Key separation:
  - initiator (state.actor): who initiated this pipeline run — tracked, not used for stage authority
  - executing role: the role-shaped agent's own role — used for authority checks
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from gov_langgraph.platform_model import (
    check_authority, Action, Role,
    HandoffDocument, Event,
)
from gov_langgraph.langgraph_engine.agent import (
    RoleShapedAgent, AgentStatus,
)
from gov_langgraph.langgraph_engine.runtime import get_runtime


class AgentExecutor:
    """
    Executes a role-shaped agent within governance boundaries.

    The initiating actor (state.actor) and the executing role are SEPARATE:
      - state.actor: who started the pipeline run — tracked in event metadata
      - executor.agent.role_name: the executing agent — used for ALL authority checks

    Authority failures (PermissionError) always propagate — never swallowed.
    Event journal failures are silently contained — do not halt the pipeline.
    """

    def __init__(self, agent: RoleShapedAgent):
        self.agent = agent
        self._last_handoff: Optional[HandoffDocument] = None
        self._last_event: Optional[Event] = None
        self._halt_reason: Optional[str] = None

    # -------------------------------------------------------------------------
    # Layer 1: Pre-execution — is this role allowed in this stage?
    # -------------------------------------------------------------------------
    def pre_execution_check(self, stage: str) -> None:
        """
        Layer 1: Pre-execution authority check.

        Uses the EXECUTING ROLE (agent.role_name), not the initiator.

        Raises:
            PermissionError — role is not permitted in this stage
        """
        if not self.agent.can_act_in_stage(stage):
            self._set_halted(
                reason=f"Role {self.agent.role_name} denied: not permitted in stage '{stage}'"
            )
            raise PermissionError(
                f"pre_execution_denied: {self.agent.role_name} cannot act in {stage}"
            )

    # -------------------------------------------------------------------------
    # Layer 2: Action-specific — is this exact action permitted?
    # -------------------------------------------------------------------------
    def enforce_action(self, action: str) -> None:
        """
        Layer 2: Action-specific authority check.

        Takes an EXPLICIT action string and checks it against the role's
        allowed_actions list. This is not a general check — it validates
        the specific action the agent is attempting to take right now.

        Raises:
            PermissionError — action is not permitted for this role
        """
        # Record what we're about to do
        self.agent.record_action(action)

        if not self.agent.can_take_action(action):
            self._set_halted(
                reason=f"Action '{action}' not permitted for role {self.agent.role_name}"
            )
            raise PermissionError(
                f"action_denied: {action} not permitted for {self.agent.role_name}"
            )

    # -------------------------------------------------------------------------
    # Layer 3: Completion — did output satisfy governance?
    # -------------------------------------------------------------------------
    def review_completion(self, handoff: HandoffDocument) -> None:
        """
        Layer 3: Completion review.

        Checks the handoff satisfies governance conditions before the
        pipeline advances.

        Raises:
            ValueError — handoff incomplete or does not meet governance
        """
        if not handoff.is_complete():
            self._set_halted(
                reason="Handoff incomplete: missing required fields"
            )
            raise ValueError(
                f"completion_denied: handoff is incomplete, "
                f"cannot advance from {handoff.from_stage}"
            )

    # -------------------------------------------------------------------------
    # Full execution with all 3 layers
    # -------------------------------------------------------------------------
    def execute_with_enforcement(
        self,
        task_id: str,
        project_id: str,
        stage: str,
        action: str,
        initiator: str = "",
    ) -> HandoffDocument:
        """
        Execute agent with all 3 enforcement layers.

        Args:
            task_id: workitem task id
            project_id: project id
            stage: the stage to execute in (BA, SA, DEV, QA)
            action: the EXPLICIT action being taken (e.g. "create_artifact", "submit_handoff")
            initiator: who initiated this pipeline run (for event metadata only)

        Returns:
            HandoffDocument if all checks pass

        Raises:
            PermissionError — layer 1 or 2 authority check failed
            ValueError — layer 3 completion check failed

        Notes:
            - initiator is recorded in event metadata, NOT used for authority
            - executing role authority is checked via agent.role_name
        """
        # Layer 1: Is executing role allowed in this stage?
        self.pre_execution_check(stage)

        # Layer 2: Is the specific action permitted for this role?
        self.enforce_action(action)

        # Layer 3: Execute and verify completion
        try:
            handoff = self.agent.execute(task_id, project_id, stage)
        except PermissionError:
            raise
        except RuntimeError as e:
            self._set_halted(str(e))
            raise

        self.review_completion(handoff)

        # Record handoff
        self._last_handoff = handoff

        # Write event — journal failure is silently contained (pipeline continues)
        self._write_event(task_id, project_id, stage, initiator, handoff)

        return handoff

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------
    def _set_halted(self, reason: str) -> None:
        """Set halted state with reason."""
        self.agent.halt(reason)
        self._halt_reason = reason

    def _write_event(
        self,
        task_id: str,
        project_id: str,
        stage: str,
        initiator: str,
        handoff: HandoffDocument,
    ) -> None:
        """
        Write agent execution event to the event journal.

        SILENTLY CONTAINED: journal failure does not halt the pipeline.
        This is intentional — governance events are important but the
        pipeline should not crash over a journaling failure.
        """
        try:
            rt = get_runtime()
            event = Event(
                event_type="agent_executed",
                project_id=project_id,
                task_id=task_id,
                actor=self.agent.role_name,
                event_summary=(
                    f"{self.agent.role_name} took action '{self.agent.last_action}' "
                    f"in {stage}, produced {len(handoff.artifact_references)} artifact(s)"
                ),
                metadata={
                    "stage": stage,
                    "initiator": initiator,  # who started the run
                    "executing_role": self.agent.role_name,  # the actual executing role
                    "action_taken": self.agent.last_action,  # explicit action
                    "handoff_status": handoff.status,
                    "artifact_count": len(handoff.artifact_references),
                    "to_stage": handoff.to_stage,
                },
            )
            rt.event_journal.append(event)
        except Exception:
            # Silently contained — pipeline continues
            pass

    def was_halted(self) -> bool:
        """True if agent was halted during execution."""
        return self.agent.is_halted()

    def halt_reason(self) -> Optional[str]:
        """Reason for halt, if any."""
        return self._halt_reason or self.agent.halt_reason

    def last_handoff(self) -> Optional[HandoffDocument]:
        """Last handoff produced, if any."""
        return self._last_handoff

    def last_action(self) -> Optional[str]:
        """The specific action last taken by the agent."""
        return self.agent.last_action
