"""
platform_model — Platform Core

Source of truth for V1 governance model.
Exports only public interfaces; internal helpers stay in their modules.

Public API:
    Objects:    Project, WorkItem, TaskState, Workflow, Handoff, Gate, Event
    Enums:      Role, Tier, Action, ProjectStatus, TaskStatus,
                HandoffStatus, GateDecision
    Authority:  check_authority(), AuthorizationRecord
    State:      StateMachine, TransitionRecord
    Handoff:    HandoffDocument (minimum V1 handoff schema)
    Exceptions: PlatformException, AuthorityViolation, InvalidTransitionError,
                StageNotFoundError, ObjectNotFoundError, ValidationError
"""

# ---------------------------------------------------------------------------
# Exceptions (load first — other modules reference these)
# ---------------------------------------------------------------------------
from .exceptions import (
    AuthorityViolation,
    InvalidTransitionError,
    ObjectNotFoundError,
    PlatformException,
    StageNotFoundError,
    ValidationError,
)

# ---------------------------------------------------------------------------
# Objects
# ---------------------------------------------------------------------------
from .objects import (
    Event,
    Gate,
    GateDecision,
    Handoff,
    HandoffStatus,
    Project,
    ProjectStatus,
    Role,
    TaskState,
    TaskStatus,
    WorkItem,
    Workflow,
)

# ---------------------------------------------------------------------------
# Authority
# ---------------------------------------------------------------------------
from .authority import (
    Action,
    AuthorizationRecord,
    Tier,
    check_authority,
)

# ---------------------------------------------------------------------------
# State Machine
# ---------------------------------------------------------------------------
from .state_machine import (
    StateMachine,
    TransitionRecord,
)

# ---------------------------------------------------------------------------
# Workflows (single source for V1 pipeline definition)
# ---------------------------------------------------------------------------
from .workflows import (
    V1_PIPELINE_STAGES,
    get_v1_pipeline_workflow,
)

# ---------------------------------------------------------------------------
# Handoff Schema (V1 minimum handoff document)
# ---------------------------------------------------------------------------
from .handoff_schema import (
    HandoffDocument,
)

# Actions (explicit stage actions for authority enforcement)
# ---------------------------------------------------------------------------
from .actions import (
    BAAction,
    SAAction,
    DEVAction,
    QAAction,
    STAGE_ACTIONS,
)

__all__ = [
    # Exceptions
    "PlatformException",
    "AuthorityViolation",
    "InvalidTransitionError",
    "StageNotFoundError",
    "ObjectNotFoundError",
    "ValidationError",
    # Objects
    "Project",
    "WorkItem",
    "TaskState",
    "Workflow",
    "Handoff",
    "Gate",
    "Event",
    # Enums
    "Role",
    "Tier",
    "Action",
    "ProjectStatus",
    "TaskStatus",
    "HandoffStatus",
    "GateDecision",
    # Authority
    "check_authority",
    "AuthorizationRecord",
    # State Machine
    "StateMachine",
    "TransitionRecord",
    # Workflows
    "V1_PIPELINE_STAGES",
    "get_v1_pipeline_workflow",
    # Handoff
    "HandoffDocument",
    # Actions
    "BAAction",
    "SAAction",
    "DEVAction",
    "QAAction",
    "STAGE_ACTIONS",
]
