"""V0.3 message and abnormal taxonomy for Nexus MQ/HITL skeleton contracts."""

from __future__ import annotations


PRIMARY_MESSAGE_TYPES = (
    "Command_Message",
    "Review_Task",
    "Feedback_Message",
    "Business_Message",
    "Timeout_Message",
    "Retry_Message",
    "Dead_Letter_Message",
)

DEFERRED_MESSAGE_TYPES = (
    "Evidence_Write_Message",
    "State_Transition_Message",
)

ALL_MESSAGE_TYPES = PRIMARY_MESSAGE_TYPES + DEFERRED_MESSAGE_TYPES

MESSAGE_CLASSES_BY_TYPE = {
    "Command_Message": "command",
    "Review_Task": "review_task",
    "Feedback_Message": "feedback",
    "Business_Message": "business_event",
    "Timeout_Message": "timeout",
    "Retry_Message": "retry",
    "Dead_Letter_Message": "dead_letter",
    "Evidence_Write_Message": "evidence_write",
    "State_Transition_Message": "state_transition",
}

ALL_MESSAGE_CLASSES = tuple(MESSAGE_CLASSES_BY_TYPE.values())

ABNORMAL_CLASSES = (
    "mechanism_stall",
    "business_stall",
    "owner_execution_stall",
    "durable_evidence_inconsistency",
    "duplicate_runtime_suspicion",
    "boundary_drift",
    "blocker_fade_out",
    "authority_stall",
    "notification_failure",
    "other",
)

RETRY_POLICY_CLASSIFICATIONS = (
    "transport_recoverable",
    "context_adjustable",
)

ERROR_CLASSES = (
    "transport",
    "business_blocked",
    "review_failure",
    "authority_unresolved",
    "context_failure",
    "mechanism_stall",
    "owner_execution_stall",
    "durable_evidence_inconsistency",
    "duplicate_runtime_suspicion",
    "boundary_drift",
    "blocker_fade_out",
    "notification_failure",
    "other",
)

HITL_ACTIONS = ("Approve", "Reject", "Revise")

DECISION_TYPES = (
    "approve",
    "reject",
    "revise",
    "defer",
    "clarify",
    "override",
    "stop",
    "resume",
    "no_response_escalated",
)

GATE_OUTCOMES = (
    "pass",
    "conditional_pass",
    "revise",
    "blocked",
    "defer",
    "waived",
)


def is_primary_message_type(message_type: str) -> bool:
    return message_type in PRIMARY_MESSAGE_TYPES


def is_deferred_message_type(message_type: str) -> bool:
    return message_type in DEFERRED_MESSAGE_TYPES


def is_valid_message_type(message_type: str) -> bool:
    return message_type in ALL_MESSAGE_TYPES


def is_valid_message_class(message_class: str) -> bool:
    return message_class in ALL_MESSAGE_CLASSES


def is_valid_abnormal_class(abnormal_class: str) -> bool:
    return abnormal_class in ABNORMAL_CLASSES
