"""
MQ Message Envelope — 3.5 Implementation
Standard Message_Envelope for all governed workflow MQ traffic.

Design source: GOVERNED_WORKFLOW_RUNTIME_AND_MESSAGE_QUEUE_ARCHITECTURE_V0_1.md §7.1
Baseline status: accepted-for-skeleton (3.5 V1.1, commit 3f7a5a0)
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import uuid
from typing import Optional, Any

SUPPORTED_SCHEMA_VERSION = "1.0"


@dataclass
class EnvelopeValidationResult:
    valid: bool
    errors: list[str]


@dataclass
class MessageEnvelope:
    """
    Standard message envelope for all governed workflow MQ traffic.

    Required fields (§7.1):
    - message_id: unique identifier for this message
    - message_type: Command_Message | Business_Message | Review_Task | Feedback_Message | Timeout_Message | Dead_Letter_Message
    - message_class: command | business_event | hitl_review | hitl_feedback | timeout | dead_letter
    - schema_version: envelope schema version (for forward compatibility)
    - idempotency_key: deduplication key — duplicate delivery must not duplicate side effects
    - workflow_instance_id: which workflow instance this belongs to
    - workflow_type: type of workflow
    - workflow_version: version of workflow
    - correlation_id: links messages in a causally related chain
    - producer: who/what produced this message
    - created_at: ISO-8601 timestamp
    - payload: message body or ref
    """

    message_id: str = field(default_factory=lambda: f"env-{uuid.uuid4().hex[:12]}")
    message_type: str = ""
    message_class: str = ""
    schema_version: str = SUPPORTED_SCHEMA_VERSION
    idempotency_key: str = ""
    workflow_instance_id: str = ""
    workflow_type: str = ""
    workflow_version: str = ""
    correlation_id: str = ""
    producer: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: dict = field(default_factory=dict)

    # Optional extended fields
    producer_timestamp: Optional[str] = None
    causal_parent_id: Optional[str] = None
    target_handler: Optional[str] = None

    def validate(self) -> EnvelopeValidationResult:
        """
        Validate required envelope fields.
        ACK means intake only — this validator does NOT check workflow state.
        """
        errors = []

        if not self.message_id:
            errors.append("MISSING_REQUIRED_FIELD: message_id")

        if not self.message_type:
            errors.append("MISSING_REQUIRED_FIELD: message_type")
        elif self.message_type not in VALID_MESSAGE_TYPES:
            errors.append(f"INVALID_MESSAGE_TYPE: {self.message_type}")

        if not self.message_class:
            errors.append("MISSING_REQUIRED_FIELD: message_class")
        elif self.message_class not in VALID_MESSAGE_CLASSES:
            errors.append(f"INVALID_MESSAGE_CLASS: {self.message_class}")

        if not self.schema_version:
            errors.append("MISSING_REQUIRED_FIELD: schema_version")
        elif self.schema_version != SUPPORTED_SCHEMA_VERSION:
            errors.append(
                f"SCHEMA_VERSION_MISMATCH: expected {SUPPORTED_SCHEMA_VERSION}, got {self.schema_version}"
            )

        if not self.idempotency_key:
            errors.append("MISSING_REQUIRED_FIELD: idempotency_key")

        if not self.workflow_instance_id:
            errors.append("MISSING_WORKFLOW_REFS: workflow_instance_id")

        if not self.workflow_type:
            errors.append("MISSING_WORKFLOW_REFS: workflow_type")

        if not self.workflow_version:
            errors.append("MISSING_WORKFLOW_REFS: workflow_version")

        if not self.correlation_id:
            errors.append("MISSING_REQUIRED_FIELD: correlation_id")

        if not self.producer:
            errors.append("MISSING_REQUIRED_FIELD: producer")

        if not self.created_at:
            errors.append("MISSING_REQUIRED_FIELD: created_at")

        if self.payload is None:
            errors.append("MISSING_REQUIRED_FIELD: payload")

        return EnvelopeValidationResult(valid=len(errors) == 0, errors=errors)

    def is_valid(self) -> bool:
        return self.validate().valid

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json_bytes(self) -> bytes:
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False).encode('utf-8')

    @classmethod
    def from_dict(cls, d: dict) -> 'MessageEnvelope':
        # Strip None optional fields that aren't set
        return cls(**{k: v for k, v in d.items() if v is not None})

    @classmethod
    def from_json_bytes(cls, data: bytes) -> 'MessageEnvelope':
        import json
        return cls.from_dict(json.loads(data.decode('utf-8')))

    def with_command_payload(self, command_name: str, params: dict) -> 'MessageEnvelope':
        """Helper: attach command payload."""
        self.payload = {"command_name": command_name, "params": params}
        return self

    def with_correlation(self, correlation_id: str) -> 'MessageEnvelope':
        self.correlation_id = correlation_id
        return self


# Valid message types per §7.1 and §7.2
VALID_MESSAGE_TYPES = {
    "Command_Message",
    "Business_Message",
    "Review_Task",
    "Feedback_Message",
    "Timeout_Message",
    "Dead_Letter_Message",
    "Evidence_Write_Message",
    "State_Transition_Message",
}

# Valid message classes
VALID_MESSAGE_CLASSES = {
    "command",
    "business_event",
    "hitl_review",
    "hitl_feedback",
    "timeout",
    "dead_letter",
}


def build_envelope(
    message_type: str,
    workflow_instance_id: str,
    workflow_type: str,
    workflow_version: str,
    producer: str,
    payload: dict,
    idempotency_key: Optional[str] = None,
    correlation_id: str = "",
    message_class: str = "",
) -> MessageEnvelope:
    """
    Build a standard MessageEnvelope with required fields.

    Design rule: ACK means intake only. Building an envelope does not
    advance workflow state — it only creates a transport record.
    """
    import uuid
    key = idempotency_key or f"{message_type}:{workflow_instance_id}:{uuid.uuid4().hex[:8]}"
    corr_id = correlation_id or f"corr-{uuid.uuid4().hex[:12]}"

    # Infer message_class from message_type if not provided
    if not message_class:
        class_map = {
            "Command_Message": "command",
            "Business_Message": "business_event",
            "Review_Task": "hitl_review",
            "Feedback_Message": "hitl_feedback",
            "Timeout_Message": "timeout",
            "Dead_Letter_Message": "dead_letter",
        }
        message_class = class_map.get(message_type, "command")

    return MessageEnvelope(
        message_type=message_type,
        message_class=message_class,
        workflow_instance_id=workflow_instance_id,
        workflow_type=workflow_type,
        workflow_version=workflow_version,
        producer=producer,
        idempotency_key=key,
        correlation_id=corr_id,
        payload=payload,
    )
