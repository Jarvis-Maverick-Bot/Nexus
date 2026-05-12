"""V0.3 abnormal-state and timeout helpers for Nexus MQ/HITL skeleton."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid

from nexus.mq.taxonomy import ABNORMAL_CLASSES, ERROR_CLASSES


UTC = timezone.utc
BLOCKING_ABNORMAL_CLASSES = set(ABNORMAL_CLASSES)

ERROR_CLASS_TO_ABNORMAL_CLASS = {
    "transport": "mechanism_stall",
    "business_blocked": "business_stall",
    "review_failure": "notification_failure",
    "authority_unresolved": "authority_stall",
    "context_failure": "boundary_drift",
    "mechanism_stall": "mechanism_stall",
    "owner_execution_stall": "owner_execution_stall",
    "durable_evidence_inconsistency": "durable_evidence_inconsistency",
    "duplicate_runtime_suspicion": "duplicate_runtime_suspicion",
    "boundary_drift": "boundary_drift",
    "blocker_fade_out": "blocker_fade_out",
    "notification_failure": "notification_failure",
    "other": "other",
}


@dataclass
class AbnormalValidationResult:
    valid: bool
    errors: list[str]


@dataclass
class AbnormalStateRecord:
    abnormal_state_id: str = field(default_factory=lambda: f"abn-{uuid.uuid4().hex[:12]}")
    error_event_id: str = ""
    workflow_instance_id: Optional[str] = None
    error_class: str = ""
    abnormal_class: str = ""
    detected_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    resolved_at: Optional[str] = None
    resolved: bool = False
    resolution_record_id: Optional[str] = None
    notification_sent: bool = False
    escalation_timer_id: Optional[str] = None

    def validate(self) -> AbnormalValidationResult:
        errors: list[str] = []
        if not self.error_event_id:
            errors.append("MISSING_REQUIRED_FIELD: error_event_id")
        if self.error_class not in ERROR_CLASSES:
            errors.append(f"INVALID_ERROR_CLASS: {self.error_class}")
        if self.abnormal_class not in ABNORMAL_CLASSES:
            errors.append(f"INVALID_ABNORMAL_CLASS: {self.abnormal_class}")
        if self.resolved and not self.resolution_record_id:
            errors.append("MISSING_REQUIRED_FIELD: resolution_record_id")
        return AbnormalValidationResult(valid=len(errors) == 0, errors=errors)


@dataclass
class ResolutionRecord:
    resolution_id: str = field(default_factory=lambda: f"res-{uuid.uuid4().hex[:12]}")
    error_event_id: str = ""
    abnormal_state_id: str = ""
    resolved_by: str = ""
    resolution_action: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    workflow_instance_id: str = ""
    state_transition_id: Optional[str] = None


@dataclass
class EscalationTimerRecord:
    escalation_timer_id: str = field(default_factory=lambda: f"esc-{uuid.uuid4().hex[:12]}")
    workflow_instance_id: str = ""
    trigger_type: str = ""
    due_at: str = ""
    status: str = "pending"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


def classify_abnormal_state(
    error_event_id: str,
    error_class: str,
    workflow_instance_id: Optional[str] = None,
) -> AbnormalStateRecord:
    abnormal_class = ERROR_CLASS_TO_ABNORMAL_CLASS.get(error_class, "other")
    return AbnormalStateRecord(
        error_event_id=error_event_id,
        workflow_instance_id=workflow_instance_id,
        error_class=error_class,
        abnormal_class=abnormal_class,
    )


def has_blocking_abnormal_state(states: list[AbnormalStateRecord]) -> bool:
    return any(not state.resolved and state.abnormal_class in BLOCKING_ABNORMAL_CLASSES for state in states)


def should_notify(abnormal_class: str) -> bool:
    return abnormal_class in BLOCKING_ABNORMAL_CLASSES


def mark_notification_sent(state: AbnormalStateRecord) -> AbnormalStateRecord:
    state.notification_sent = True
    return state


def resolve_abnormal_state(
    state: AbnormalStateRecord,
    resolved_by: str,
    resolution_action: str,
    workflow_instance_id: str,
    evidence_refs: Optional[list[str]] = None,
    state_transition_id: Optional[str] = None,
) -> tuple[AbnormalStateRecord, ResolutionRecord]:
    resolution = ResolutionRecord(
        error_event_id=state.error_event_id,
        abnormal_state_id=state.abnormal_state_id,
        resolved_by=resolved_by,
        resolution_action=resolution_action,
        evidence_refs=evidence_refs or [],
        workflow_instance_id=workflow_instance_id,
        state_transition_id=state_transition_id,
    )
    state.resolved = True
    state.resolved_at = datetime.now(UTC).isoformat()
    state.resolution_record_id = resolution.resolution_id
    return state, resolution


def start_escalation_timer(
    workflow_instance_id: str,
    trigger_type: str,
    due_at: str,
) -> EscalationTimerRecord:
    return EscalationTimerRecord(
        workflow_instance_id=workflow_instance_id,
        trigger_type=trigger_type,
        due_at=due_at,
    )
