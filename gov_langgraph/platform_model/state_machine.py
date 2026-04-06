"""
platform_model.state_machine — V1 State Machine

Validates WorkItem stage transitions.
Integrates with Workflow.allowed_transitions and authority rules.
Integrates with Harness: checkpointing and event journaling.

Harness instances are injected by the caller (dependency injection).
StateMachine does not create or own harness instances.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from .objects import Role, TaskState, WorkItem
from .authority import Action, check_authority
from .exceptions import InvalidTransitionError, StageNotFoundError

if TYPE_CHECKING:
    from gov_langgraph.harness.checkpointer import Checkpointer
    from gov_langgraph.harness.events import EventJournal


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

    Optional harness integration (dependency injection):
    - checkpointer: saves checkpoint before/after each transition
    - event_journal: appends event after each transition

    Usage:
        sm = StateMachine(
            workflow,
            checkpointer=ckpt,
            event_journal=journal,
        )
        record = sm.advance_stage(work_item, target_stage, actor_role)
    """

    def __init__(
        self,
        workflow,
        *,
        checkpointer: Optional["Checkpointer"] = None,
        event_journal: Optional["EventJournal"] = None,
    ):
        """
        Args:
            workflow: Workflow instance defining valid transitions
            checkpointer: Optional Checkpointer for Layer 2 checkpointing
            event_journal: Optional EventJournal for Layer 3 event journaling
        """
        self.workflow = workflow
        self.checkpointer = checkpointer
        self.event_journal = event_journal

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
        project_id: Optional[str] = None,
    ) -> TransitionRecord:
        """
        Validate, authorize, checkpoint, execute, and journal a stage advance.

        Lifecycle:
          1. Validate target_stage exists in workflow
          2. Validate transition is in allowed_transitions
          3. Check authority (UPDATE_TASK_STATE action)
          4. [Harness] checkpoint_before — save state before change
          5. Mutate work_item.current_stage
          6. [Harness] checkpoint_after — confirm new state
          7. [Harness] append event to journal

        Args:
            work_item: WorkItem instance (will be mutated)
            target_stage: Stage to advance to
            actor_role: Role attempting the advance
            current_owner: current_owner of the task (for authority check)
            project_id: project_id for event journal (required if event_journal is set)

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
        check_authority(
            action=Action.UPDATE_TASK_STATE,
            actor_role=actor_role,
            task_id=work_item.task_id,
            current_owner=current_owner or work_item.current_owner,
        )

        # Step 4: [Harness] checkpoint_before — save state before change
        if self.checkpointer is not None:
            self.checkpointer.checkpoint_before(
                task_id=work_item.task_id,
                from_stage=from_stage,
                to_stage=target_stage,
                actor_role=actor_role,
                workitem_state={
                    "task_id": work_item.task_id,
                    "current_stage": work_item.current_stage,
                    "current_owner": work_item.current_owner,
                },
            )

        # Step 5: All checks passed — mutate the WorkItem state
        work_item.current_stage = target_stage

        # Step 6: [Harness] checkpoint_after — confirm new state
        if self.checkpointer is not None:
            self.checkpointer.checkpoint_after(
                record=self.checkpointer.get_latest_checkpoint(work_item.task_id),
                workitem_state={
                    "task_id": work_item.task_id,
                    "current_stage": work_item.current_stage,
                    "current_owner": work_item.current_owner,
                },
            )

        # Step 7: [Harness] append event to journal
        if self.event_journal is not None and project_id is not None:
            self.event_journal.append_raw(
                project_id=project_id,
                event_type="stage_advanced",
                event_summary=f"Task '{work_item.task_id}' advanced from '{from_stage}' to '{target_stage}'",
                actor=actor_role,
                task_id=work_item.task_id,
                related_stage=target_stage,
            )

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
