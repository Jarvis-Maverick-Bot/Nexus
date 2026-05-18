"""Phase 6 observability records.

Logs, metrics, traces, and health probes here are diagnostic evidence only.
They intentionally do not expose APIs that mutate governed workflow state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import uuid


UTC = timezone.utc
SECRET_KEYS = {"password", "token", "secret", "private_key", "credential", "authorization"}


@dataclass
class StructuredRuntimeLog:
    event_id: str
    timestamp: str
    runtime_instance_id: str
    workflow_instance_id: Optional[str]
    message_id: Optional[str]
    correlation_id: Optional[str]
    event_type: str
    severity: str
    component: str
    outcome: str
    evidence_refs: list[str]
    payload: dict[str, Any] = field(default_factory=dict)
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MetricSample:
    metric_name: str
    labels: dict[str, str]
    value: float
    unit: str
    sampled_at: str
    producer_component: str
    schema_version: str = "p6.metrics.v1"
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TraceSpan:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    correlation_id: Optional[str]
    causation_id: Optional[str]
    component: str
    started_at: str
    ended_at: Optional[str]
    outcome: str
    evidence_refs: list[str] = field(default_factory=list)
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HealthProbeResult:
    component: str
    status: str
    checked_at: str
    dependency_status: dict[str, str]
    latency_ms: Optional[float] = None
    error_ref: Optional[str] = None
    evidence_refs: list[str] = field(default_factory=list)
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_runtime_log(
    *,
    runtime_instance_id: str,
    event_type: str,
    severity: str,
    component: str,
    outcome: str,
    workflow_instance_id: Optional[str] = None,
    message_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    evidence_refs: Optional[list[str]] = None,
    payload: Optional[dict[str, Any]] = None,
) -> StructuredRuntimeLog:
    return StructuredRuntimeLog(
        event_id=f"log-{uuid.uuid4().hex[:12]}",
        timestamp=datetime.now(UTC).isoformat(),
        runtime_instance_id=runtime_instance_id,
        workflow_instance_id=workflow_instance_id,
        message_id=message_id,
        correlation_id=correlation_id,
        event_type=event_type,
        severity=severity,
        component=component,
        outcome=outcome,
        evidence_refs=list(evidence_refs or []),
        payload=redact_payload(payload or {}),
    )


def build_metric_sample(
    metric_name: str,
    labels: dict[str, str],
    value: float,
    unit: str,
    producer_component: str,
) -> MetricSample:
    return MetricSample(
        metric_name=metric_name,
        labels=redact_labels(labels),
        value=value,
        unit=unit,
        sampled_at=datetime.now(UTC).isoformat(),
        producer_component=producer_component,
    )


def build_trace_span(
    *,
    trace_id: str,
    component: str,
    outcome: str,
    correlation_id: Optional[str] = None,
    causation_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
    evidence_refs: Optional[list[str]] = None,
) -> TraceSpan:
    return TraceSpan(
        trace_id=trace_id,
        span_id=f"span-{uuid.uuid4().hex[:12]}",
        parent_span_id=parent_span_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        component=component,
        started_at=datetime.now(UTC).isoformat(),
        ended_at=datetime.now(UTC).isoformat(),
        outcome=outcome,
        evidence_refs=list(evidence_refs or []),
    )


def build_health_probe(
    *,
    component: str,
    status: str,
    dependency_status: dict[str, str],
    latency_ms: Optional[float] = None,
    error_ref: Optional[str] = None,
    evidence_refs: Optional[list[str]] = None,
) -> HealthProbeResult:
    if status not in {"healthy", "degraded", "unavailable"}:
        raise ValueError(f"invalid health status: {status}")
    return HealthProbeResult(
        component=component,
        status=status,
        checked_at=datetime.now(UTC).isoformat(),
        dependency_status=dict(dependency_status),
        latency_ms=latency_ms,
        error_ref=error_ref,
        evidence_refs=list(evidence_refs or []),
    )


def build_agent_access_evidence_ref(
    *,
    source_doc: str,
    source_record: str,
    evidence_ref: str,
    checksum_ref: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "evidence_ref": evidence_ref,
        "source_doc": source_doc,
        "source_record": source_record,
        "timestamp": datetime.now(UTC).isoformat(),
        "checksum_ref": checksum_ref,
        "not_business_completion": True,
    }


def redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        if key.lower() in SECRET_KEYS:
            redacted[key] = "[REDACTED]"
        elif isinstance(value, dict):
            redacted[key] = redact_payload(value)
        elif isinstance(value, str) and _looks_secret(value):
            redacted[key] = "[REDACTED]"
        else:
            redacted[key] = value
    return redacted


def redact_labels(labels: dict[str, str]) -> dict[str, str]:
    return {key: ("[REDACTED]" if key.lower() in SECRET_KEYS or _looks_secret(value) else value) for key, value in labels.items()}


def _looks_secret(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in ("password=", "token=", "secret=", "bearer "))
