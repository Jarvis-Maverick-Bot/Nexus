"""Candidate-safe event mapping for Candidate Adapter operations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from nexus.mq.agent_registry_events import secret_material_errors
from nexus.mq.candidate_adapter_assignment_validator import CandidateAssignmentEvent
from nexus.mq.candidate_adapter_session_store import CandidateAdapterSession


CANDIDATE_ADAPTER_EVENT_SCHEMA_VERSION = "4.19.candidate_adapter.event.v1"
RAW_INTERNAL_PAYLOAD_KEYS = {
    "ack_subject",
    "broker_credentials",
    "broker_subject",
    "headers",
    "internal_headers",
    "internal_message",
    "message_package",
    "mq_envelope",
    "nats_headers",
    "nats_subject",
    "nexus_envelope",
    "raw_envelope",
    "raw_message",
    "reply_to",
    "transport_ack",
    "transport_headers",
    "transport_metadata",
}


@dataclass
class CandidateAdapterEvent:
    event_type: str
    status: str
    agent_id: str
    runtime_instance_id: str
    session_id: str
    assignment_id: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    schema_version: str = CANDIDATE_ADAPTER_EVENT_SCHEMA_VERSION
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def map_assignment_to_candidate_event(
    assignment: CandidateAssignmentEvent,
    *,
    session: CandidateAdapterSession,
) -> CandidateAdapterEvent:
    return _validated_event(
        CandidateAdapterEvent(
            event_type="assignment_available",
            status="candidate",
            agent_id=session.agent_id,
            runtime_instance_id=session.runtime_instance_id,
            session_id=session.session_id,
            assignment_id=assignment.assignment_id,
            payload=_candidate_safe_payload(assignment.payload),
        )
    )


def build_candidate_action_event(
    event_type: str,
    *,
    session: CandidateAdapterSession,
    assignment_id: str = "",
    evidence_refs: list[str] | None = None,
    payload: dict[str, Any] | None = None,
) -> CandidateAdapterEvent:
    refs = list(evidence_refs or [])
    if event_type == "offline" and not refs:
        raise ValueError("OFFLINE_REQUIRES_FINAL_EVIDENCE_REF")
    safe_payload = _candidate_safe_payload(payload or {})
    if event_type == "result_candidate":
        safe_payload["business_acceptance"] = False
    event = CandidateAdapterEvent(
        event_type=event_type,
        status=_status_for_event(event_type),
        agent_id=session.agent_id,
        runtime_instance_id=session.runtime_instance_id,
        session_id=session.session_id,
        assignment_id=assignment_id,
        evidence_refs=refs,
        payload=safe_payload,
    )
    return _validated_event(event)


def _candidate_safe_payload(payload: dict[str, Any]) -> dict[str, Any]:
    safe_payload = _candidate_safe_value(payload)
    if not isinstance(safe_payload, dict):
        return {}
    return safe_payload


def _candidate_safe_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _candidate_safe_value(item)
            for key, item in value.items()
            if str(key).lower() not in RAW_INTERNAL_PAYLOAD_KEYS
        }
    if isinstance(value, list):
        return [_candidate_safe_value(item) for item in value]
    return value


def _status_for_event(event_type: str) -> str:
    if event_type in {"assignment_rejected", "anomaly"}:
        return "rejected"
    if event_type == "result_candidate":
        return "candidate"
    if event_type in {"draining", "offline"}:
        return event_type
    return "accepted"


def _validated_event(event: CandidateAdapterEvent) -> CandidateAdapterEvent:
    errors: list[str] = []
    if event.schema_version != CANDIDATE_ADAPTER_EVENT_SCHEMA_VERSION:
        errors.append("UNSUPPORTED_CANDIDATE_ADAPTER_EVENT_SCHEMA")
    if event.not_business_completion is not True:
        errors.append("CANDIDATE_ADAPTER_EVENT_CANNOT_BE_BUSINESS_COMPLETION")
    if not event.event_type:
        errors.append("MISSING_EVENT_TYPE")
    errors.extend(secret_material_errors(event.to_dict(), path="candidate_adapter_event"))
    if errors:
        raise ValueError("; ".join(_dedupe(errors)))
    return event


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error not in deduped:
            deduped.append(error)
    return deduped
