"""
platform_model.authority — Step 4 Authority Rules

V1 role-based authority enforcement.
Tier 1/2/3 mapped to Step 4 governance model.

Tier 1: Query-only (all roles can query)
Tier 2: Management Layer governance actions (create, assign, approve, close)
Tier 3: Delivery Layer execution actions (execute stage, handoff own task)

IMPORTANT: This is NOT a privilege hierarchy.
TIER3 does NOT imply TIER2 authority.
Delivery roles (TIER3) cannot perform governance actions even if they outrank TIER2 in privilege.
Governance actions are reserved for Management Layer roles.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, NamedTuple

from .objects import Role
from .exceptions import AuthorityViolation


# ---------------------------------------------------------------------------
# Tier Enum
# ---------------------------------------------------------------------------


class Tier(Enum):
    """
    Authority tier — NOT a privilege hierarchy.

    TIER1: Query-only. All roles (Management + Delivery) can query.
    TIER2: Management Layer governance actions only.
           ALEX, NOVA, JARVIS, MAVERICK — never Delivery roles.
    TIER3: Delivery Layer execution actions.
           VIPER_BA, VIPER_SA, VIPER_DEV, VIPER_QA for their own task actions.
    """

    TIER1 = 1  # Query only
    TIER2 = 2  # Management Layer governance actions
    TIER3 = 3  # Delivery Layer execution actions


# ---------------------------------------------------------------------------
# Step 3 Action Enum
# ---------------------------------------------------------------------------


class Action(str, Enum):
    """All V1 actions from Step 3."""

    # Management / Mutation — Governance actions (TIER2, Management only)
    CREATE_PROJECT = "create_project"
    UPDATE_PROJECT = "update_project"
    CLOSE_PROJECT = "close_project"
    CREATE_TASK = "create_task"
    UPDATE_TASK = "update_task"          # current owner OR Management
    ASSIGN_OWNER = "assign_owner"
    UPDATE_TASK_STATE = "update_task_state"  # current owner OR Management
    SUBMIT_HANDOFF = "submit_handoff"   # current owner OR Management
    RECORD_BLOCKER = "record_blocker"    # current owner OR Management
    RESOLVE_BLOCKER = "resolve_blocker" # current owner OR Management
    CLOSE_TASK = "close_task"

    # Gate / Approval — Management Layer only
    GATE_APPROVE = "gate_approve"
    GATE_REJECT = "gate_reject"
    GATE_HOLD = "gate_hold"
    GATE_STOP = "gate_stop"
    GATE_RETURN = "gate_return"

    # Query — open to all (TIER1)
    QUERY_PROJECT_STATUS = "query_project_status"
    QUERY_TASK_STATUS = "query_task_status"
    QUERY_TASK_OWNER = "query_task_owner"
    QUERY_TASK_BLOCKER = "query_task_blocker"
    QUERY_PENDING_HANDOFFS = "query_pending_handoffs"
    QUERY_PENDING_GATES = "query_pending_gates"
    QUERY_RECENT_EVENTS = "query_recent_events"
    QUERY_TASKS_BY_STAGE = "query_tasks_by_stage"
    QUERY_TASKS_BY_OWNER = "query_tasks_by_owner"


# ---------------------------------------------------------------------------
# Authorization Record — Audit Trail
# ---------------------------------------------------------------------------


@dataclass
class AuthorizationRecord:
    """Audit trail entry for every authorization check."""

    action: str
    actor_role: str
    tier: Tier
    granted: bool
    reason: str = ""
    task_id: Optional[str] = None
    project_id: Optional[str] = None
    recorded_at: datetime = field(default_factory=datetime.utcnow)
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# Role Definitions
# ---------------------------------------------------------------------------


MANAGEMENT_ROLES: set[str] = {
    Role.ALEX.value,
    Role.NOVA.value,
    Role.JARVIS.value,
    Role.MAVERICK.value,
}

DELIVERY_ROLES: set[str] = {
    Role.VIPER_BA.value,
    Role.VIPER_SA.value,
    Role.VIPER_DEV.value,
    Role.VIPER_QA.value,
}


def get_tier_for_role(role: str) -> Tier:
    """Map role string to its action-authority tier."""
    if role in MANAGEMENT_ROLES:
        return Tier.TIER2
    if role in DELIVERY_ROLES:
        return Tier.TIER3
    return Tier.TIER1


# ---------------------------------------------------------------------------
# Action Rule Definition
# ---------------------------------------------------------------------------


class ActionRule(NamedTuple):
    """Definition of what is required to perform an action."""
    min_tier: Tier
    management_only: bool  # If True: ONLY Management roles can perform (no owner exception)
    owner_check: bool      # If True: current owner CAN perform even at lower tier
    description: str


ACTION_RULES: dict[str, ActionRule] = {
    # Project-level — Management Layer only
    Action.CREATE_PROJECT:   ActionRule(Tier.TIER2, management_only=True,  owner_check=False, description="Create project"),
    Action.UPDATE_PROJECT:   ActionRule(Tier.TIER2, management_only=True,  owner_check=False, description="Update project"),
    Action.CLOSE_PROJECT:   ActionRule(Tier.TIER2, management_only=True,  owner_check=False, description="Close project"),

    # Task-level
    Action.CREATE_TASK:      ActionRule(Tier.TIER2, management_only=True,  owner_check=False, description="Create task"),
    Action.ASSIGN_OWNER:     ActionRule(Tier.TIER2, management_only=True,  owner_check=False, description="Assign task owner"),
    Action.CLOSE_TASK:       ActionRule(Tier.TIER2, management_only=True,  owner_check=False, description="Close task"),

    # Task State — current owner OR Management
    Action.UPDATE_TASK_STATE: ActionRule(Tier.TIER2, management_only=False, owner_check=True, description="Update task state"),
    Action.RECORD_BLOCKER:    ActionRule(Tier.TIER2, management_only=False, owner_check=True, description="Record blocker"),
    Action.RESOLVE_BLOCKER:   ActionRule(Tier.TIER2, management_only=False, owner_check=True, description="Resolve blocker"),

    # Handoff — current owner OR Management
    Action.SUBMIT_HANDOFF:   ActionRule(Tier.TIER2, management_only=False, owner_check=True, description="Submit handoff"),
    Action.UPDATE_TASK:       ActionRule(Tier.TIER2, management_only=False, owner_check=True, description="Update task"),

    # Gate — Management Layer only
    Action.GATE_APPROVE:     ActionRule(Tier.TIER2, management_only=True,  owner_check=False, description="Approve gate"),
    Action.GATE_REJECT:      ActionRule(Tier.TIER2, management_only=True,  owner_check=False, description="Reject gate"),
    Action.GATE_HOLD:        ActionRule(Tier.TIER2, management_only=True,  owner_check=False, description="Hold gate"),
    Action.GATE_STOP:        ActionRule(Tier.TIER2, management_only=True,  owner_check=False, description="Stop gate"),
    Action.GATE_RETURN:       ActionRule(Tier.TIER2, management_only=True,  owner_check=False, description="Return gate"),

    # Queries — open to all (TIER1)
    Action.QUERY_PROJECT_STATUS:   ActionRule(Tier.TIER1, management_only=False, owner_check=False, description="Query project status"),
    Action.QUERY_TASK_STATUS:     ActionRule(Tier.TIER1, management_only=False, owner_check=False, description="Query task status"),
    Action.QUERY_TASK_OWNER:      ActionRule(Tier.TIER1, management_only=False, owner_check=False, description="Query task owner"),
    Action.QUERY_TASK_BLOCKER:   ActionRule(Tier.TIER1, management_only=False, owner_check=False, description="Query task blocker"),
    Action.QUERY_PENDING_HANDOFFS:ActionRule(Tier.TIER1, management_only=False, owner_check=False, description="Query pending handoffs"),
    Action.QUERY_PENDING_GATES:   ActionRule(Tier.TIER1, management_only=False, owner_check=False, description="Query pending gates"),
    Action.QUERY_RECENT_EVENTS:   ActionRule(Tier.TIER1, management_only=False, owner_check=False, description="Query recent events"),
    Action.QUERY_TASKS_BY_STAGE: ActionRule(Tier.TIER1, management_only=False, owner_check=False, description="Query tasks by stage"),
    Action.QUERY_TASKS_BY_OWNER: ActionRule(Tier.TIER1, management_only=False, owner_check=False, description="Query tasks by owner"),
}


# ---------------------------------------------------------------------------
# Core Authority Check
# ---------------------------------------------------------------------------


def check_authority(
    action: str,
    actor_role: str,
    task_id: Optional[str] = None,
    project_id: Optional[str] = None,
    current_owner: Optional[str] = None,
) -> AuthorizationRecord:
    """
    Check if actor_role is authorized to perform action.

    Args:
        action: Action being performed
        actor_role: Role of the caller (from Role enum string value)
        task_id: Optional task context
        project_id: Optional project context
        current_owner: The current_owner field of the WorkItem (if applicable)

    Returns:
        AuthorizationRecord with the decision

    Raises:
        AuthorityViolation: if the action is not authorized

    Example:
        record = check_authority(
            action=Action.UPDATE_TASK_STATE,
            actor_role="viper_ba",
            current_owner="viper_ba"
        )
    """
    actor_tier = get_tier_for_role(actor_role)

    # Get rule for this action
    rule = ACTION_RULES.get(action)
    if rule is None:
        record = AuthorizationRecord(
            action=action,
            actor_role=actor_role,
            tier=actor_tier,
            granted=False,
            reason=f"Unknown action '{action}'",
            task_id=task_id,
            project_id=project_id,
        )
        raise AuthorityViolation(action, actor_role, f"Unknown action '{action}'")

    # Step 1: If management_only, ONLY Management roles can perform
    if rule.management_only:
        if actor_role not in MANAGEMENT_ROLES:
            reason = f"'{action}' is a Management Layer action"
            record = AuthorizationRecord(
                action=action, actor_role=actor_role, tier=actor_tier,
                granted=False, reason=reason, task_id=task_id, project_id=project_id,
            )
            raise AuthorityViolation(action, actor_role, reason)
        # Management role — always allowed
        record = AuthorizationRecord(
            action=action, actor_role=actor_role, tier=actor_tier,
            granted=True, reason=f"Management Layer action", 
            task_id=task_id, project_id=project_id,
        )
        return record

    # Step 2: If owner_check and current_owner matches actor_role — allow
    if rule.owner_check and current_owner is not None:
        if actor_role == current_owner:
            record = AuthorizationRecord(
                action=action, actor_role=actor_role, tier=actor_tier,
                granted=True, reason=f"Current owner of task: {current_owner}",
                task_id=task_id, project_id=project_id,
            )
            return record

    # Step 3: Check minimum tier
    if actor_tier.value >= rule.min_tier.value:
        record = AuthorizationRecord(
            action=action, actor_role=actor_role, tier=actor_tier,
            granted=True, reason=f"Tier {actor_tier.value} >= required Tier {rule.min_tier.value}",
            task_id=task_id, project_id=project_id,
        )
        return record

    # Denied
    reason = f"Role {actor_role} (Tier {actor_tier.value}) cannot perform '{action}' (requires Tier {rule.min_tier.value})"
    record = AuthorizationRecord(
        action=action, actor_role=actor_role, tier=actor_tier,
        granted=False, reason=reason, task_id=task_id, project_id=project_id,
    )
    raise AuthorityViolation(action, actor_role, reason)
