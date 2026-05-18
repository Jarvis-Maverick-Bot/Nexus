"""Runtime adapter contract records for 4.19."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from nexus.mq.agent_registry import DispatchAssignmentRecord


ADAPTER_EVENT_TYPES = {"received", "heartbeat", "result", "anomaly"}


@dataclass
class RuntimeAdapterEvent:
    adapter_id: str
    adapter_type: str
    protocol_version: str
    event_type: str
    agent_id: str
    runtime_instance_id: str
    message_id: Optional[str]
    correlation_id: Optional[str]
    assignment_id: Optional[str]
    payload: dict[str, Any]
    evidence_refs: list[str] = field(default_factory=list)
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RuntimeAdapterValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


def validate_runtime_adapter_event(
    event: RuntimeAdapterEvent,
    *,
    assignment: Optional[DispatchAssignmentRecord] = None,
) -> RuntimeAdapterValidationResult:
    errors: list[str] = []
    if not event.protocol_version:
        errors.append("MISSING_PROTOCOL_VERSION")
    if event.event_type not in ADAPTER_EVENT_TYPES:
        errors.append(f"UNSUPPORTED_ADAPTER_EVENT_TYPE: {event.event_type}")
    if event.event_type in {"received", "result"} and not event.message_id:
        errors.append("MISSING_MESSAGE_ID")
    if event.event_type == "result" and assignment is None:
        errors.append("MISSING_ASSIGNMENT")
    if assignment is not None:
        if event.assignment_id != assignment.assignment_id:
            errors.append("ASSIGNMENT_ID_MISMATCH")
        if event.agent_id != assignment.assigned_agent_id:
            errors.append("ASSIGNED_AGENT_MISMATCH")
        if event.runtime_instance_id != assignment.assigned_runtime_instance_id:
            errors.append("ASSIGNED_RUNTIME_MISMATCH")
    return RuntimeAdapterValidationResult(valid=not errors, errors=errors)


def build_heartbeat_event(
    *,
    adapter_id: str,
    adapter_type: str,
    agent_id: str,
    runtime_instance_id: str,
    presence_state: str,
    evidence_refs: Optional[list[str]] = None,
) -> RuntimeAdapterEvent:
    return RuntimeAdapterEvent(
        adapter_id=adapter_id,
        adapter_type=adapter_type,
        protocol_version="4.19.runtime_adapter.v1",
        event_type="heartbeat",
        agent_id=agent_id,
        runtime_instance_id=runtime_instance_id,
        message_id=None,
        correlation_id=None,
        assignment_id=None,
        payload={"presence_state": presence_state},
        evidence_refs=list(evidence_refs or []),
    )
