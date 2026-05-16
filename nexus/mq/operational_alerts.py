"""Phase 6 durable alert event and lifecycle helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import uuid

from nexus.mq.durable_state import DurableStateStore


UTC = timezone.utc
ALERT_SEVERITIES = {"SEV-0", "SEV-1", "SEV-2", "SEV-3"}
ALERT_TERMINAL_STATES = {"resolved"}
ALERT_TRANSITIONS = {
    "pending": {"routed", "suppressed", "escalated", "failed_delivery", "resolved"},
    "routed": {"acknowledged", "resolved", "escalated", "failed_delivery"},
    "acknowledged": {"resolved", "escalated"},
    "suppressed": {"resolved"},
    "failed_delivery": {"escalated", "resolved"},
    "escalated": {"resolved"},
    "resolved": set(),
}


@dataclass
class AlertEvent:
    alert_id: str
    dedupe_key: str
    severity: str
    source_component: str
    lifecycle_state: str
    routing_policy_ref: str
    suppression_policy_ref: str
    workflow_instance_id: Optional[str] = None
    correlation_id: Optional[str] = None
    abnormal_record_id: Optional[str] = None
    recovery_scan_id: Optional[str] = None
    evidence_refs: list[str] = field(default_factory=list)
    count: int = 1
    first_seen_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_seen_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    resolved_at: Optional[str] = None
    resolution_ref: Optional[str] = None
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def create_alert_event(
    *,
    severity: str,
    source_component: str,
    failure_class: str,
    routing_policy_ref: str,
    suppression_policy_ref: str,
    workflow_instance_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    cause_id: Optional[str] = None,
    abnormal_record_id: Optional[str] = None,
    recovery_scan_id: Optional[str] = None,
    evidence_refs: Optional[list[str]] = None,
) -> AlertEvent:
    if severity not in ALERT_SEVERITIES:
        raise ValueError(f"invalid alert severity: {severity}")
    target = workflow_instance_id or correlation_id or "runtime"
    stable_cause = cause_id or abnormal_record_id or recovery_scan_id or failure_class
    return AlertEvent(
        alert_id=f"alert-{uuid.uuid4().hex[:12]}",
        dedupe_key=f"{severity}:{source_component}:{target}:{failure_class}:{stable_cause}",
        severity=severity,
        source_component=source_component,
        lifecycle_state="pending",
        routing_policy_ref=routing_policy_ref,
        suppression_policy_ref=suppression_policy_ref,
        workflow_instance_id=workflow_instance_id,
        correlation_id=correlation_id,
        abnormal_record_id=abnormal_record_id,
        recovery_scan_id=recovery_scan_id,
        evidence_refs=list(evidence_refs or []),
    )


def transition_alert(event: AlertEvent, next_state: str, *, resolution_ref: Optional[str] = None) -> AlertEvent:
    allowed = ALERT_TRANSITIONS.get(event.lifecycle_state, set())
    if next_state not in allowed:
        raise ValueError(f"invalid alert transition: {event.lifecycle_state} -> {next_state}")
    event.lifecycle_state = next_state
    event.updated_at = datetime.now(UTC).isoformat()
    if next_state == "resolved":
        event.resolved_at = event.updated_at
        event.resolution_ref = resolution_ref
    return event


def dedupe_alert(existing: AlertEvent, duplicate: AlertEvent) -> AlertEvent:
    if existing.dedupe_key != duplicate.dedupe_key:
        raise ValueError("cannot dedupe alerts with different dedupe keys")
    existing.count += 1
    existing.last_seen_at = datetime.now(UTC).isoformat()
    existing.updated_at = existing.last_seen_at
    existing.evidence_refs = sorted(set(existing.evidence_refs + duplicate.evidence_refs))
    return existing


def suppress_alert(event: AlertEvent, reason: str) -> AlertEvent:
    if event.severity == "SEV-0":
        raise ValueError("SEV-0 alert suppression is not allowed")
    event.evidence_refs = sorted(set(event.evidence_refs + [f"suppression:{reason}"]))
    return transition_alert(event, "suppressed")


def persist_alert_event(store: DurableStateStore, event: AlertEvent) -> Any:
    return store.create_phase5_durable_record(
        family="alert_event",
        workflow_instance_id=event.workflow_instance_id,
        target_ref=event.alert_id,
        dedupe_key=f"alert:{event.alert_id}:{event.lifecycle_state}:{event.updated_at}",
        status=event.lifecycle_state,
        payload=event.to_dict(),
    )
