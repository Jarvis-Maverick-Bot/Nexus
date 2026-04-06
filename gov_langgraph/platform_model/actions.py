"""
platform_model.actions — Stage Action Definitions

Explicit actions for each stage role.
Authority enforcement is tied to a specific action being taken,
not just a general "can this role do anything."

Nova decision (2026-04-06): LOCKED for V1.
Action enforcement must be concrete and visible.
"""

from __future__ import annotations
from enum import Enum


class BAAction(str, Enum):
    """Business Analysis stage actions."""
    CREATE_ARTIFACT = "create_artifact"      # Produce BRD
    SUBMIT_HANDOFF = "submit_handoff"        # Hand off to SA
    REQUEST_CLARIFICATION = "request_clarification"  # Flag ambiguity
    FLAG_BLOCKER = "flag_blocker"           # Surface blocker to Maverick


class SAAction(str, Enum):
    """Systems Analysis stage actions."""
    CREATE_ARTIFACT = "create_artifact"      # Produce SPEC
    SUBMIT_HANDOFF = "submit_handoff"        # Hand off to DEV
    REQUEST_CLARIFICATION = "request_clarification"
    FLAG_BLOCKER = "flag_blocker"


class DEVAction(str, Enum):
    """Development stage actions."""
    CREATE_ARTIFACT = "create_artifact"      # Produce deliverable
    SUBMIT_HANDOFF = "submit_handoff"        # Hand off to QA
    REQUEST_CLARIFICATION = "request_clarification"
    FLAG_BLOCKER = "flag_blocker"


class QAAction(str, Enum):
    """QA stage actions."""
    CREATE_ARTIFACT = "create_artifact"      # Produce QA report
    APPROVE = "approve"                     # Approve delivery
    REJECT = "reject"                      # Reject and return to DEV
    FLAG_BLOCKER = "flag_blocker"


# Stage-to-action-enum mapping
STAGE_ACTIONS = {
    "BA": BAAction,
    "SA": SAAction,
    "DEV": DEVAction,
    "QA": QAAction,
}


def get_stage_action_enum(stage: str):
    """Get the action enum for a given stage."""
    return STAGE_ACTIONS.get(stage)
