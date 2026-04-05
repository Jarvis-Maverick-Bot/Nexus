"""
platform_model.state_machine — V1 State Machine

Validates WorkItem stage transitions.
Integrates with Workflow.allowed_transitions and authority rules.
Enforces: current stage -> target stage is valid AND actor has authority.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .objects import Role, TaskState, WorkItem
from .authority import Action, check_authority
from .exceptions import InvalidTransitionError, StageNotFoundError


# ---------------------------------------------------------------------------
# Transition Record
# ---------------------------------------------------------------------------


@dataclass
class TransitionRecord:
    """
    Audit record for every transition attempt.
    Records the from/to stages, actor, and whether it was allowed or denied.
    """

    task_id: str
    from_stage: str
    to_stage: str
    actor_role: str
    allowed: bool
    reason: str = ""
    recorded_at: datetime = field(default_factory=datetime.utcnow)
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# State Machine
# ---------------------------------------------------------------------------


class StateMachine:
    """
    V1 State Machine for WorkItem stage transitions.

    Validates transitions against:
    1. Workflow's allowed_transitions (what stages can move to what)
    2. Role authority (who is allowed to perform the advance)

    Usage:
        sm = StateMachine(workflow)
        record = sm.advance_stage(work_item, target_stage, actor_role)
    """

    def __init__(self, workflow):
        """
        Args:
            workflow: Workflow instance defining valid transitions
        """
        self.workflow = workflow

    def get_valid_transitions(self, from_stage: str) -> list[str]:
        """
        Return list of valid target stages from a given stage.
        """
        return self.workflow.get_valid_next_stages(from_stage)

    def is_valid_transition(self, from_stage: str, to_stage: str) -> bool:
        """
        Check if a transition is in the workflow's allowed_transitions.
        Does NOT check authority — only the transition map.
        """
        valid_targets = self.get_valid_transitions(from_stage)
        return to_stage in valid_targets

    def advance_stage(
        self,
        work_item: WorkItem,
        target_stage: str,
        actor_role: str,
        current_owner: Optional[str] = None,
    ) -> TransitionRecord:
        """
        Validate, authorize, and execute a WorkItem stage advance.

        This method:
          1. Validates target_stage exists in the workflow
          2. Checks the transition is in allowed_transitions
          3. Checks actor has authority (UPDATE_TASK_STATE action)
          4. Mutates work_item.current_stage to target_stage

        Args:
            work_item: WorkItem instance (will be mutated)
            target_stage: Stage to advance to
            actor_role: Role attempting the advance (from Role enum value)
            current_owner: current_owner of the task (for owner authority check)

        Returns:
            TransitionRecord with the outcome

        Raises:
            StageNotFoundError: if target_stage is not in the workflow's stage_list
            InvalidTransitionError: if the transition is not in allowed_transitions
            AuthorityViolation: if the actor is not authorized to advance
        """
        # Step 1: Validate target_stage exists in workflow
        if target_stage not in self.workflow.stage_list:
            raise StageNotFoundError(target_stage)

        from_stage = work_item.current_stage

        # Step 2: Check if transition is in allowed_transitions
        if not self.is_valid_transition(from_stage, target_stage):
            valid = self.get_valid_transitions(from_stage)
            record = TransitionRecord(
                task_id=work_item.task_id,
                from_stage=from_stage,
                to_stage=target_stage,
                actor_role=actor_role,
                allowed=False,
                reason=f"'{from_stage}' cannot advance to '{target_stage}'. Valid: {valid}",
            )
            raise InvalidTransitionError(from_stage, target_stage, record.reason)

        # Step 3: Check authority to perform stage advance
        # Using UPDATE_TASK_STATE as the governing action for stage advances
        try:
            check_authority(
                action=Action.UPDATE_TASK_STATE,
                actor_role=actor_role,
                task_id=work_item.task_id,
                current_owner=current_owner or work_item.current_owner,
            )
        except Exception as e:
            record = TransitionRecord(
                task_id=work_item.task_id,
                from_stage=from_stage,
                to_stage=target_stage,
                actor_role=actor_role,
                allowed=False,
                reason=str(e),
            )
            raise

        # Step 4: All checks passed — mutate the WorkItem state
        work_item.current_stage = target_stage

        record = TransitionRecord(
            task_id=work_item.task_id,
            from_stage=from_stage,
            to_stage=target_stage,
            actor_role=actor_role,
            allowed=True,
            reason=f"Transition '{from_stage}' -> '{target_stage}' authorized and applied",
        )
        return record

    def get_current_stage_info(self, work_item: WorkItem) -> dict:
        """
        Return a snapshot of the current stage context for a WorkItem.
        """
        valid_targets = self.get_valid_transitions(work_item.current_stage)
        return {
            "task_id": work_item.task_id,
            "current_stage": work_item.current_stage,
            "valid_next_stages": valid_targets,
            "is_terminal": work_item.current_stage == self.workflow.stage_list[-1],
        }
