"""
Phase 2 protocol validation boundary.

Scope:
- validate protocol envelope + sender identity
- resolve deterministic publish subject
- validate inbound delivery for a specific consumer and subject
- emit deterministic anomaly envelopes for protocol rejection paths
"""

from dataclasses import dataclass
from typing import Optional

from nexus.mq.identity import AgentIdentityStore
from nexus.mq.protocol import ProtocolEnvelope, build_protocol_envelope
from nexus.mq.protocol_routing import (
    RoutingResult,
    build_ops_anomaly_subject,
    route_protocol_envelope,
    subject_matches_trusted_prefixes,
)


@dataclass
class ProtocolBoundaryResult:
    valid: bool
    errors: list[str]
    subject: Optional[str] = None
    envelope: Optional[ProtocolEnvelope] = None


class ProtocolMessageBoundary:
    def __init__(self, identity_store: AgentIdentityStore):
        self._identity_store = identity_store

    def validate_outbound(self, envelope_dict: dict) -> ProtocolBoundaryResult:
        envelope = ProtocolEnvelope.from_dict(envelope_dict)
        errors: list[str] = []

        env_result = envelope.validate()
        errors.extend(env_result.errors)

        sender_result = self._identity_store.validate_sender(
            source_agent_id=envelope.source_agent_id,
            source_role=envelope.source_role,
            authority_scope=envelope.authority_scope,
        )
        errors.extend(sender_result.errors)

        errors.extend(self._validate_outbound_target(envelope))

        routing = route_protocol_envelope(envelope)
        if not routing.valid:
            errors.extend(routing.errors or [])

        return ProtocolBoundaryResult(
            valid=len(errors) == 0,
            errors=errors,
            subject=routing.subject if routing.valid else None,
            envelope=envelope,
        )

    def validate_inbound_for_consumer(
        self,
        consumer_agent_id: str,
        subject: str,
        envelope_dict: dict,
    ) -> ProtocolBoundaryResult:
        outbound = self.validate_outbound(envelope_dict)
        errors = list(outbound.errors)
        envelope = outbound.envelope or ProtocolEnvelope.from_dict(envelope_dict)

        consumer = self._identity_store.get_agent(consumer_agent_id)
        if consumer is None:
            errors.append(f"UNKNOWN_CONSUMER: {consumer_agent_id}")
        else:
            if not subject_matches_trusted_prefixes(subject, consumer.trusted_subject_prefixes):
                errors.append(f"UNTRUSTED_SUBJECT: {subject}")

        target_result = self._identity_store.validate_target_for_consumer(
            consumer_agent_id=consumer_agent_id,
            target_agent_id=envelope.target_agent_id,
            target_role=envelope.target_role,
            capability=envelope.capability,
        )
        errors.extend(target_result.errors)

        expected_routing = route_protocol_envelope(envelope)
        if expected_routing.valid and expected_routing.subject != subject:
            errors.append(
                f"SUBJECT_ROUTE_MISMATCH: expected {expected_routing.subject}, got {subject}"
            )

        return ProtocolBoundaryResult(
            valid=len(errors) == 0,
            errors=errors,
            subject=subject if len(errors) == 0 else None,
            envelope=envelope,
        )

    def build_anomaly_envelope(
        self,
        original_envelope_dict: dict,
        reporting_agent_id: str,
        reporting_runtime_instance_id: str,
        reporting_role: str,
        error_code: str,
        details: Optional[dict] = None,
    ) -> ProtocolEnvelope:
        original = ProtocolEnvelope.from_dict(original_envelope_dict)
        return build_protocol_envelope(
            message_type="anomaly",
            source_agent_id=reporting_agent_id,
            source_runtime_instance_id=reporting_runtime_instance_id,
            source_role=reporting_role,
            authority_scope="workflow.anomaly",
            payload={
                "error_code": error_code,
                "details": details or {},
                "reported_subject": build_ops_anomaly_subject(),
            },
            correlation_id=original.correlation_id,
            causation_id=original.message_id if original.message_id else None,
            idempotency_key=f"anomaly:{reporting_agent_id}:{error_code}:{original.message_id or 'unknown'}",
            target_agent_id=original.source_agent_id or None,
            reply_to_subject=original.reply_to_subject,
        )

    def _validate_outbound_target(self, envelope: ProtocolEnvelope) -> list[str]:
        errors: list[str] = []
        if envelope.target_agent_id:
            target = self._identity_store.get_agent(envelope.target_agent_id)
            if target is None:
                errors.append(f"INVALID_TARGET_AGENT: {envelope.target_agent_id}")
            else:
                if envelope.target_role and target.role != envelope.target_role:
                    errors.append(
                        f"TARGET_ROLE_MISMATCH: expected {envelope.target_role}, got {target.role}"
                    )
                if envelope.capability and not target.supports_capability(envelope.capability):
                    errors.append(f"UNSUPPORTED_CAPABILITY: {envelope.capability}")
        elif envelope.capability:
            if not any(
                agent.status == "active" and agent.supports_capability(envelope.capability)
                for agent in self._identity_store.all_agents()
            ):
                errors.append(f"UNSUPPORTED_CAPABILITY: {envelope.capability}")
        elif envelope.target_role:
            if not any(
                agent.status == "active" and agent.role == envelope.target_role
                for agent in self._identity_store.all_agents()
            ):
                errors.append(f"INVALID_TARGET_ROLE: {envelope.target_role}")
        return errors
