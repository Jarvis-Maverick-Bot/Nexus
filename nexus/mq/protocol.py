"""
Agent collaboration protocol envelope for cross-machine NATS work.

Phase 1 scope:
- protocol envelope schema
- protocol-version validation
- mandatory causation rules
- minimum request/reply field checks
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import json
import uuid


SUPPORTED_PROTOCOL_VERSION = "agent-collab-nats/v0.1"
MISSING_CAUSATION = object()

VALID_PROTOCOL_MESSAGE_TYPES = {
    "command",
    "review",
    "feedback",
    "result",
    "callback",
    "handoff",
    "ack",
    "timeout",
    "anomaly",
    "rejected",
}

REQUEST_MESSAGE_TYPES = {
    "command",
    "review",
    "handoff",
}


@dataclass
class ProtocolEnvelopeValidationResult:
    valid: bool
    errors: list[str]


@dataclass
class ProtocolEnvelope:
    protocol_version: str = SUPPORTED_PROTOCOL_VERSION
    message_id: str = field(default_factory=lambda: f"pmsg-{uuid.uuid4().hex[:12]}")
    correlation_id: str = field(default_factory=lambda: f"corr-{uuid.uuid4().hex[:12]}")
    causation_id: Any = MISSING_CAUSATION
    idempotency_key: str = ""
    message_type: str = ""
    source_agent_id: str = ""
    source_runtime_instance_id: str = ""
    source_role: str = ""
    target_agent_id: Optional[str] = None
    target_role: Optional[str] = None
    capability: Optional[str] = None
    authority_scope: str = ""
    reply_to_subject: Optional[str] = None
    expires_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload_schema: Optional[str] = None
    payload: dict = field(default_factory=dict)
    evidence_refs: list[str] = field(default_factory=list)
    signature_ref: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def validate(self) -> ProtocolEnvelopeValidationResult:
        errors: list[str] = []

        if self.protocol_version != SUPPORTED_PROTOCOL_VERSION:
            errors.append(
                f"UNSUPPORTED_PROTOCOL_VERSION: expected {SUPPORTED_PROTOCOL_VERSION}, got {self.protocol_version or 'missing'}"
            )

        if not self.message_id:
            errors.append("MISSING_REQUIRED_FIELD: message_id")
        if not self.correlation_id:
            errors.append("MISSING_REQUIRED_FIELD: correlation_id")
        if self.causation_id is MISSING_CAUSATION:
            errors.append("MISSING_REQUIRED_FIELD: causation_id")
        elif self.causation_id == "":
            errors.append("INVALID_CAUSATION_ID: causation_id must be null or a non-empty parent message_id")

        if not self.idempotency_key:
            errors.append("MISSING_REQUIRED_FIELD: idempotency_key")

        if not self.message_type:
            errors.append("MISSING_REQUIRED_FIELD: message_type")
        elif self.message_type not in VALID_PROTOCOL_MESSAGE_TYPES:
            errors.append(f"INVALID_MESSAGE_TYPE: {self.message_type}")

        if not self.source_agent_id:
            errors.append("MISSING_REQUIRED_FIELD: source_agent_id")
        if not self.source_runtime_instance_id:
            errors.append("MISSING_REQUIRED_FIELD: source_runtime_instance_id")
        if not self.source_role:
            errors.append("MISSING_REQUIRED_FIELD: source_role")
        if not self.authority_scope:
            errors.append("MISSING_REQUIRED_FIELD: authority_scope")
        if not self.expires_at:
            errors.append("MISSING_REQUIRED_FIELD: expires_at")
        else:
            try:
                datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            except ValueError:
                errors.append(f"INVALID_EXPIRES_AT: {self.expires_at}")

        if self.payload is None:
            errors.append("MISSING_REQUIRED_FIELD: payload")

        if self.message_type in REQUEST_MESSAGE_TYPES:
            if not self.reply_to_subject:
                errors.append("MISSING_REQUIRED_FIELD: reply_to_subject")
            if not any([self.target_agent_id, self.target_role, self.capability]):
                errors.append(
                    "MISSING_ROUTING_TARGET: one of target_agent_id, target_role, or capability is required"
                )

        return ProtocolEnvelopeValidationResult(valid=len(errors) == 0, errors=errors)

    def is_root_message(self) -> bool:
        return self.causation_id is None

    def to_dict(self) -> dict:
        return {
            "protocol_version": self.protocol_version,
            "message_id": self.message_id,
            "correlation_id": self.correlation_id,
            "causation_id": None if self.causation_id is MISSING_CAUSATION else self.causation_id,
            "idempotency_key": self.idempotency_key,
            "message_type": self.message_type,
            "source_agent_id": self.source_agent_id,
            "source_runtime_instance_id": self.source_runtime_instance_id,
            "source_role": self.source_role,
            "target_agent_id": self.target_agent_id,
            "target_role": self.target_role,
            "capability": self.capability,
            "authority_scope": self.authority_scope,
            "reply_to_subject": self.reply_to_subject,
            "expires_at": self.expires_at,
            "payload_schema": self.payload_schema,
            "payload": self.payload,
            "evidence_refs": list(self.evidence_refs),
            "signature_ref": self.signature_ref,
            "created_at": self.created_at,
        }

    def to_json_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), ensure_ascii=False).encode("utf-8")

    @classmethod
    def from_dict(cls, data: dict) -> "ProtocolEnvelope":
        kwargs = dict(data)
        if "causation_id" not in kwargs:
            kwargs["causation_id"] = MISSING_CAUSATION
        return cls(**kwargs)

    @classmethod
    def from_json_bytes(cls, payload: bytes) -> "ProtocolEnvelope":
        return cls.from_dict(json.loads(payload.decode("utf-8")))


def build_protocol_envelope(
    message_type: str,
    source_agent_id: str,
    source_runtime_instance_id: str,
    source_role: str,
    authority_scope: str,
    payload: dict,
    idempotency_key: Optional[str] = None,
    target_agent_id: Optional[str] = None,
    target_role: Optional[str] = None,
    capability: Optional[str] = None,
    reply_to_subject: Optional[str] = None,
    correlation_id: Optional[str] = None,
    causation_id: Any = None,
    expires_at: Optional[str] = None,
    payload_schema: Optional[str] = None,
    evidence_refs: Optional[list[str]] = None,
    signature_ref: Optional[str] = None,
) -> ProtocolEnvelope:
    corr = correlation_id or f"corr-{uuid.uuid4().hex[:12]}"
    idem = idempotency_key or f"{message_type}:{source_agent_id}:{uuid.uuid4().hex[:8]}"
    expiry = expires_at or datetime.now(timezone.utc).isoformat()
    return ProtocolEnvelope(
        message_type=message_type,
        source_agent_id=source_agent_id,
        source_runtime_instance_id=source_runtime_instance_id,
        source_role=source_role,
        authority_scope=authority_scope,
        payload=payload,
        idempotency_key=idem,
        target_agent_id=target_agent_id,
        target_role=target_role,
        capability=capability,
        reply_to_subject=reply_to_subject,
        correlation_id=corr,
        causation_id=causation_id,
        expires_at=expiry,
        payload_schema=payload_schema,
        evidence_refs=evidence_refs or [],
        signature_ref=signature_ref,
    )
