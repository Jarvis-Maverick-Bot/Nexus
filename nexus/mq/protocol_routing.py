"""
Thin subject-routing helpers for the Phase 2 protocol and V0.3 execution layer.

Scope:
- deterministic subject builders
- protocol envelope to subject mapping
- simple subject prefix matching for trusted-subject checks
"""

from dataclasses import dataclass
from typing import Optional

from nexus.mq.protocol import ProtocolEnvelope


SUBJECT_OPS_ANOMALY = "ops.anomaly"
SUBJECT_OPS_TIMEOUT = "ops.timeout"
SUBJECT_OPS_DLQ = "ops.dlq"


@dataclass
class RoutingResult:
    valid: bool
    subject: Optional[str] = None
    errors: list[str] | None = None


def build_agent_inbox_subject(agent_id: str) -> str:
    return f"agent.{agent_id}.inbox"


def build_agent_callback_subject(agent_id: str) -> str:
    return f"agent.{agent_id}.callbacks"


def build_workflow_request_subject(capability: str) -> str:
    return f"workflow.{capability}.requests"


def build_review_request_subject(review_kind: str) -> str:
    return f"review.{review_kind}.requests"


def build_feedback_event_subject(workflow_id: str) -> str:
    return f"feedback.{workflow_id}.events"


def build_ops_anomaly_subject() -> str:
    return SUBJECT_OPS_ANOMALY


def build_ops_timeout_subject() -> str:
    return SUBJECT_OPS_TIMEOUT


def subject_matches_trusted_prefixes(subject: str, trusted_prefixes: list[str]) -> bool:
    return any(subject.startswith(prefix) for prefix in trusted_prefixes)


def route_protocol_envelope(envelope: ProtocolEnvelope) -> RoutingResult:
    errors: list[str] = []
    message_type = envelope.message_type

    if message_type in {"command", "handoff"}:
        if envelope.target_agent_id:
            return RoutingResult(valid=True, subject=build_agent_inbox_subject(envelope.target_agent_id))
        if envelope.capability:
            return RoutingResult(valid=True, subject=build_workflow_request_subject(envelope.capability))
        if envelope.target_role:
            return RoutingResult(valid=True, subject=build_workflow_request_subject(envelope.target_role))
        errors.append("MISSING_ROUTING_TARGET")
        return RoutingResult(valid=False, errors=errors)

    if message_type == "review":
        if envelope.target_agent_id:
            return RoutingResult(valid=True, subject=build_agent_inbox_subject(envelope.target_agent_id))
        review_kind = (
            envelope.payload.get("review_kind")
            or envelope.capability
            or envelope.target_role
        )
        if review_kind:
            return RoutingResult(valid=True, subject=build_review_request_subject(str(review_kind)))
        errors.append("MISSING_REVIEW_KIND")
        return RoutingResult(valid=False, errors=errors)

    if message_type == "feedback":
        workflow_id = envelope.payload.get("workflow_id") or envelope.payload.get("workflow_instance_id")
        if not workflow_id:
            errors.append("MISSING_WORKFLOW_ID_FOR_FEEDBACK")
            return RoutingResult(valid=False, errors=errors)
        return RoutingResult(valid=True, subject=build_feedback_event_subject(str(workflow_id)))

    if message_type in {"result", "callback", "ack", "rejected"}:
        if envelope.reply_to_subject:
            return RoutingResult(valid=True, subject=envelope.reply_to_subject)
        if envelope.target_agent_id:
            return RoutingResult(valid=True, subject=build_agent_callback_subject(envelope.target_agent_id))
        errors.append("MISSING_REPLY_ROUTE")
        return RoutingResult(valid=False, errors=errors)

    if message_type == "timeout":
        return RoutingResult(valid=True, subject=SUBJECT_OPS_TIMEOUT)

    if message_type == "anomaly":
        return RoutingResult(valid=True, subject=SUBJECT_OPS_ANOMALY)

    errors.append(f"UNROUTABLE_MESSAGE_TYPE: {message_type}")
    return RoutingResult(valid=False, errors=errors)


def route_execution_envelope_dict(envelope_dict: dict) -> RoutingResult:
    """Route V0.3 execution envelopes without depending on protocol_version."""
    message_type = envelope_dict.get("message_type")
    reply_to_subject = envelope_dict.get("reply_to_subject")
    target_agent_id = envelope_dict.get("target_agent_id")
    workflow_type = envelope_dict.get("workflow_type")
    payload = envelope_dict.get("payload") or {}

    if message_type in {"Command_Message", "Review_Task"}:
        if target_agent_id:
            if (
                message_type == "Command_Message"
                and workflow_type == "controlled_3_5_uat"
                and target_agent_id in {"nova", "jarvis"}
            ):
                return RoutingResult(valid=True, subject=f"nexus.3_5.uat.{target_agent_id}.inbox")
            return RoutingResult(valid=True, subject=build_agent_inbox_subject(str(target_agent_id)))
        return RoutingResult(valid=False, errors=["MISSING_ROUTING_TARGET"])

    if message_type in {"Feedback_Message", "Business_Message"}:
        if reply_to_subject:
            return RoutingResult(valid=True, subject=str(reply_to_subject))
        if target_agent_id:
            return RoutingResult(valid=True, subject=build_agent_callback_subject(str(target_agent_id)))
        workflow_id = envelope_dict.get("workflow_instance_id")
        if workflow_id:
            return RoutingResult(valid=True, subject=build_feedback_event_subject(str(workflow_id)))
        return RoutingResult(valid=False, errors=["MISSING_REPLY_ROUTE"])

    if message_type == "Timeout_Message":
        return RoutingResult(valid=True, subject=SUBJECT_OPS_TIMEOUT)

    if message_type == "Retry_Message":
        target_subject = None
        if isinstance(payload, dict):
            target_subject = payload.get("target_subject")
        if target_subject:
            return RoutingResult(valid=True, subject=str(target_subject))
        return RoutingResult(valid=False, errors=["MISSING_RETRY_TARGET_SUBJECT"])

    if message_type == "Dead_Letter_Message":
        return RoutingResult(valid=True, subject=SUBJECT_OPS_DLQ)

    if message_type in {"Evidence_Write_Message", "State_Transition_Message"}:
        return RoutingResult(valid=False, errors=[f"DEFERRED_TRANSPORT_INACTIVE: {message_type}"])

    return RoutingResult(valid=False, errors=[f"UNROUTABLE_MESSAGE_TYPE: {message_type}"])
