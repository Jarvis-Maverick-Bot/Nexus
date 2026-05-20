"""Live MQ transport evidence gates.

The records here describe transport observations only. They never mark a
workflow complete and do not carry credential material.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


REQUIRED_LIVE_MQ_EVIDENCE_EVENTS = (
    "publish",
    "receive",
    "ack",
    "return",
    "duplicate",
    "timeout_or_anomaly",
    "cleanup",
    "secret_scan",
)

SECRET_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer ",
    "client_secret",
    "password",
    "private_key",
    "secret",
    "token",
)
SECRET_VALUE_MARKERS = (
    "authorization:",
    "bearer ",
    "client_secret=",
    "password=",
    "private_key",
    "token=",
)


@dataclass
class TransportEvidenceRecord:
    event_type: str
    message_id: str
    subject: str
    status: str
    observed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LiveMqEvidenceGateResult:
    accepted: bool
    missing_events: list[str]
    errors: list[str]
    not_pass: bool = True
    not_business_completion: bool = True


def evidence_record(
    event_type: str,
    *,
    message_id: str,
    subject: str,
    status: str,
    details: dict[str, Any] | None = None,
    errors: list[str] | None = None,
) -> TransportEvidenceRecord:
    return TransportEvidenceRecord(
        event_type=event_type,
        message_id=message_id,
        subject=subject,
        status=status,
        details=redact_secret_values(details or {}),
        errors=list(errors or []),
    )


def evaluate_live_mq_evidence_gate(
    records: list[TransportEvidenceRecord],
) -> LiveMqEvidenceGateResult:
    present = {record.event_type for record in records}
    missing = [event for event in REQUIRED_LIVE_MQ_EVIDENCE_EVENTS if event not in present]
    errors: list[str] = []
    if not records:
        errors.append("LIVE_MQ_EVIDENCE_EMPTY")
    if any(record.not_business_completion is not True for record in records):
        errors.append("LIVE_MQ_EVIDENCE_MUST_NOT_CLAIM_BUSINESS_COMPLETION")
    for record in records:
        errors.extend(secret_material_errors(record.to_dict(), path=f"record[{record.event_type}]"))
    if present == {"publish"}:
        errors.append("LIVE_MQ_SENDER_ONLY_EVIDENCE_CANNOT_PASS")
    return LiveMqEvidenceGateResult(
        accepted=not missing and not errors,
        missing_events=missing,
        errors=list(dict.fromkeys(errors)),
    )


def contains_secret_material(value: Any) -> bool:
    return bool(secret_material_errors(value))


def secret_material_errors(value: Any, path: str = "value") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key).lower()
            if any(marker.strip() in key_text for marker in SECRET_MARKERS):
                errors.append(f"SECRET_MATERIAL_FIELD_FORBIDDEN: {path}.{key}")
            errors.extend(secret_material_errors(nested, f"{path}.{key}"))
        return errors
    if isinstance(value, list):
        for index, nested in enumerate(value):
            errors.extend(secret_material_errors(nested, f"{path}[{index}]"))
        return errors
    if isinstance(value, str):
        normalized = value.lower()
        if any(marker in normalized for marker in SECRET_VALUE_MARKERS):
            errors.append(f"SECRET_MATERIAL_VALUE_FORBIDDEN: {path}")
    return errors


def redact_secret_values(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, nested in value.items():
            if any(marker.strip() in str(key).lower() for marker in SECRET_MARKERS):
                redacted[str(key)] = "<redacted>"
            else:
                redacted[str(key)] = redact_secret_values(nested)
        return redacted
    if isinstance(value, list):
        return [redact_secret_values(item) for item in value]
    if isinstance(value, str) and any(marker in value.lower() for marker in SECRET_VALUE_MARKERS):
        return "<redacted>"
    return value
