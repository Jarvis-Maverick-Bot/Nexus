"""Persistent agent registry lifecycle events for WBS 7.8 Phase A."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import uuid


REGISTRY_EVENT_SCHEMA_VERSION = "4.19.registry.event.v1"
REGISTRY_EVENT_TYPES = {
    "heartbeat_accepted",
    "heartbeat_offline",
    "heartbeat_rejected",
    "heartbeat_stale",
    "registry_record_upserted",
    "registry_record_unchanged",
    "registry_record_rejected",
    "registry_record_quarantined",
    "registry_store_load_failed",
}
SECRET_KEY_MARKERS = {
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
}
SECRET_VALUE_MARKERS = {
    "api_key=",
    "authorization:",
    "bearer ",
    "password=",
    "secret=",
    "token=",
    "-----begin",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AgentRegistryEvent:
    event_type: str
    agent_id: Optional[str]
    runtime_instance_id: Optional[str]
    revision: Optional[int]
    payload: dict[str, Any]
    event_id: str = field(default_factory=lambda: f"registry-event-{uuid.uuid4().hex[:12]}")
    schema_version: str = REGISTRY_EVENT_SCHEMA_VERSION
    occurred_at: str = field(default_factory=_now_iso)
    evidence_refs: list[str] = field(default_factory=list)
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentRegistryEventValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


def build_registry_event(
    *,
    event_type: str,
    agent_id: Optional[str],
    runtime_instance_id: Optional[str],
    revision: Optional[int],
    payload: Optional[dict[str, Any]] = None,
    evidence_refs: Optional[list[str]] = None,
) -> AgentRegistryEvent:
    return AgentRegistryEvent(
        event_type=event_type,
        agent_id=agent_id,
        runtime_instance_id=runtime_instance_id,
        revision=revision,
        payload=dict(payload or {}),
        evidence_refs=list(evidence_refs or []),
    )


def validate_registry_event(event: AgentRegistryEvent) -> AgentRegistryEventValidationResult:
    errors: list[str] = []
    if event.schema_version != REGISTRY_EVENT_SCHEMA_VERSION:
        errors.append(f"UNSUPPORTED_REGISTRY_EVENT_SCHEMA: {event.schema_version}")
    if event.event_type not in REGISTRY_EVENT_TYPES:
        errors.append(f"UNSUPPORTED_REGISTRY_EVENT_TYPE: {event.event_type}")
    if event.event_type != "registry_store_load_failed" and not event.agent_id:
        errors.append("MISSING_AGENT_ID")
    if event.not_business_completion is not True:
        errors.append("REGISTRY_EVENT_CANNOT_BE_BUSINESS_COMPLETION")
    errors.extend(secret_material_errors(event.payload))
    errors.extend(secret_material_errors(event.evidence_refs, path="evidence_refs"))
    return AgentRegistryEventValidationResult(valid=not errors, errors=errors)


def secret_material_errors(value: Any, *, path: str = "payload") -> list[str]:
    errors: list[str] = []
    _scan_secret_material(value, path, errors)
    return errors


def _scan_secret_material(value: Any, path: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            if _is_secret_key(key_text):
                errors.append(f"SECRET_MATERIAL_FIELD: {path}.{key_text}")
            _scan_secret_material(item, f"{path}.{key_text}", errors)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _scan_secret_material(item, f"{path}[{index}]", errors)
        return
    if isinstance(value, str) and _is_secret_value(value):
        errors.append(f"SECRET_MATERIAL_VALUE: {path}")


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    if lowered.endswith("_ref") or lowered.endswith("_refs"):
        return False
    return any(marker in lowered for marker in SECRET_KEY_MARKERS)


def _is_secret_value(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith("sk-") or any(marker in lowered for marker in SECRET_VALUE_MARKERS)
