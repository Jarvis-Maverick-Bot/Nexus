"""Contract-first V0.3 envelope and payload validation for Nexus MQ/HITL."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any, Optional
import uuid

from nexus.mq.message_families import MessageFamilyDefinition, get_message_family
from nexus.mq.payloads import (
    BusinessMessagePayload,
    CommandMessagePayload,
    DeadLetterMessagePayload,
    EvidenceWriteMessagePayload,
    FeedbackMessagePayload,
    GoalDrivenCommandPayload,
    PayloadContract,
    ReviewTaskPayload,
    RetryMessagePayload,
    StateTransitionMessagePayload,
    TimeoutMessagePayload,
)
from nexus.mq.taxonomy import MESSAGE_CLASSES_BY_TYPE, is_valid_message_class, is_valid_message_type


SUPPORTED_EXECUTION_SCHEMA_VERSION = "1.0"


PAYLOAD_TYPE_BY_MESSAGE_TYPE = {
    "Command_Message": CommandMessagePayload,
    "Review_Task": ReviewTaskPayload,
    "Feedback_Message": FeedbackMessagePayload,
    "Business_Message": BusinessMessagePayload,
    "Timeout_Message": TimeoutMessagePayload,
    "Retry_Message": RetryMessagePayload,
    "Dead_Letter_Message": DeadLetterMessagePayload,
    "Evidence_Write_Message": EvidenceWriteMessagePayload,
    "State_Transition_Message": StateTransitionMessagePayload,
}

_CALLBACK_OR_RESPONSE_TYPES = {
    "Feedback_Message",
    "Business_Message",
    "Timeout_Message",
    "Retry_Message",
    "Dead_Letter_Message",
}


@dataclass
class ContractValidationResult:
    valid: bool
    errors: list[str]
    family: Optional[MessageFamilyDefinition] = None
    payload_contract: Optional[PayloadContract] = None


@dataclass
class ExecutionMessageEnvelope:
    message_id: str = field(default_factory=lambda: f"env-{uuid.uuid4().hex[:12]}")
    message_type: str = ""
    message_class: str = ""
    schema_version: str = SUPPORTED_EXECUTION_SCHEMA_VERSION
    idempotency_key: str = ""
    workflow_instance_id: str = ""
    workflow_type: str = ""
    workflow_version: str = ""
    step_id: Optional[str] = None
    checkpoint_id: Optional[str] = None
    gate_id: Optional[str] = None
    correlation_id: str = field(default_factory=lambda: f"corr-{uuid.uuid4().hex[:12]}")
    causation_id: Optional[str] = None
    producer: str = ""
    intended_consumer: Optional[str] = None
    actor_id: Optional[str] = None
    actor_role: Optional[str] = None
    payload_ref: Optional[str] = None
    payload: Any = None
    artifact_refs: list[Any] = field(default_factory=list)
    evidence_refs: list[Any] = field(default_factory=list)
    state_refs: list[Any] = field(default_factory=list)
    priority: str = "normal"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    available_at: Optional[str] = None
    expires_at: Optional[str] = None
    retry_policy_ref: Optional[str] = None
    ack_policy: str = "explicit"
    source_agent_id: Optional[str] = None
    source_runtime_instance_id: Optional[str] = None
    source_role: Optional[str] = None
    authority_scope: Optional[str] = None
    reply_to_subject: Optional[str] = None
    target_agent_id: Optional[str] = None

    def to_dict(self) -> dict:
        data = asdict(self)
        if isinstance(self.payload, PayloadContract):
            data["payload"] = asdict(self.payload)
        elif is_dataclass(self.payload):
            data["payload"] = asdict(self.payload)
        return data

    @classmethod
    def from_dict(cls, payload: dict) -> "ExecutionMessageEnvelope":
        return cls(**payload)


def build_execution_envelope(
    message_type: str,
    workflow_instance_id: str,
    workflow_type: str,
    workflow_version: str,
    producer: str,
    payload: dict | PayloadContract,
    idempotency_key: Optional[str] = None,
    correlation_id: Optional[str] = None,
    message_class: Optional[str] = None,
    **kwargs,
) -> ExecutionMessageEnvelope:
    message_class = message_class or MESSAGE_CLASSES_BY_TYPE[message_type]
    return ExecutionMessageEnvelope(
        message_type=message_type,
        message_class=message_class,
        workflow_instance_id=workflow_instance_id,
        workflow_type=workflow_type,
        workflow_version=workflow_version,
        producer=producer,
        payload=payload,
        idempotency_key=idempotency_key or f"{message_type}:{workflow_instance_id}:{uuid.uuid4().hex[:8]}",
        correlation_id=correlation_id or f"corr-{uuid.uuid4().hex[:12]}",
        **kwargs,
    )


def validate_execution_message(
    envelope: ExecutionMessageEnvelope | dict,
    require_runtime_overlay: bool = False,
) -> ContractValidationResult:
    if isinstance(envelope, dict):
        envelope = ExecutionMessageEnvelope.from_dict(envelope)

    errors: list[str] = []
    family: Optional[MessageFamilyDefinition] = None

    if not envelope.message_id:
        errors.append("MISSING_REQUIRED_FIELD: message_id")
    if not envelope.message_type:
        errors.append("MISSING_REQUIRED_FIELD: message_type")
    elif not is_valid_message_type(envelope.message_type):
        errors.append(f"INVALID_MESSAGE_TYPE: {envelope.message_type}")
    else:
        family = get_message_family(envelope.message_type)

    if not envelope.message_class:
        errors.append("MISSING_REQUIRED_FIELD: message_class")
    elif not is_valid_message_class(envelope.message_class):
        errors.append(f"INVALID_MESSAGE_CLASS: {envelope.message_class}")
    elif family and family.message_class != envelope.message_class:
        errors.append(
            f"MESSAGE_CLASS_MISMATCH: expected {family.message_class}, got {envelope.message_class}"
        )

    if envelope.schema_version != SUPPORTED_EXECUTION_SCHEMA_VERSION:
        errors.append(
            f"SCHEMA_VERSION_MISMATCH: expected {SUPPORTED_EXECUTION_SCHEMA_VERSION}, got {envelope.schema_version}"
        )

    for field_name in (
        "idempotency_key",
        "workflow_instance_id",
        "workflow_type",
        "workflow_version",
        "correlation_id",
        "producer",
        "created_at",
    ):
        if not getattr(envelope, field_name):
            errors.append(f"MISSING_REQUIRED_FIELD: {field_name}")

    if envelope.priority not in {"low", "normal", "high", "urgent"}:
        errors.append(f"INVALID_PRIORITY: {envelope.priority}")
    if envelope.ack_policy not in {"explicit", "none"}:
        errors.append(f"INVALID_ACK_POLICY: {envelope.ack_policy}")

    payload_contract, payload_error = _coerce_payload_contract(envelope.message_type, envelope.payload)
    if payload_contract is None:
        errors.append(payload_error or f"UNSUPPORTED_PAYLOAD_CONTRACT: {envelope.message_type}")
    else:
        payload_validation = payload_contract.validate()
        errors.extend(payload_validation.errors)

    if require_runtime_overlay:
        _validate_runtime_overlay(envelope, errors)

    return ContractValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        family=family,
        payload_contract=payload_contract,
    )


def is_transport_active(message_type: str) -> bool:
    family = get_message_family(message_type)
    return bool(family and family.transport_active)


def _coerce_payload_contract(
    message_type: str, payload: Any
) -> tuple[Optional[PayloadContract], Optional[str]]:
    if message_type == "Command_Message":
        if isinstance(payload, GoalDrivenCommandPayload):
            return payload, None
        if isinstance(payload, dict) and payload.get("command_name") == "Goal_Driven_Command":
            try:
                return GoalDrivenCommandPayload.from_dict(payload), None
            except TypeError:
                return None, "PAYLOAD_SCHEMA_MISMATCH: Command_Message"
    payload_type = PAYLOAD_TYPE_BY_MESSAGE_TYPE.get(message_type)
    if payload_type is None:
        return None, None
    if isinstance(payload, payload_type):
        return payload, None
    if isinstance(payload, dict):
        try:
            return payload_type.from_dict(payload), None
        except TypeError:
            return None, f"PAYLOAD_SCHEMA_MISMATCH: {message_type}"
    return None, f"UNSUPPORTED_PAYLOAD_CONTRACT: {message_type}"


def _validate_runtime_overlay(envelope: ExecutionMessageEnvelope, errors: list[str]) -> None:
    for field_name in ("source_agent_id", "source_runtime_instance_id", "source_role"):
        if not getattr(envelope, field_name):
            errors.append(f"MISSING_RUNTIME_OVERLAY_FIELD: {field_name}")

    if envelope.message_type in {"Review_Task", "Feedback_Message"} and not envelope.authority_scope:
        errors.append("MISSING_RUNTIME_OVERLAY_FIELD: authority_scope")

    if envelope.message_type in _CALLBACK_OR_RESPONSE_TYPES and not envelope.reply_to_subject:
        errors.append("MISSING_RUNTIME_OVERLAY_FIELD: reply_to_subject")

    if envelope.message_type in {"Command_Message", "Review_Task"} and not envelope.target_agent_id:
        errors.append("MISSING_RUNTIME_OVERLAY_FIELD: target_agent_id")
