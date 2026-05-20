"""WBS 7.17 live send/receive correction helpers.

This module is transport-mechanics scope only. It provides preflight checks,
in-memory adapter send/receive evidence, intake ACKs, duplicate suppression,
and return-message routing without starting listeners or running business work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from nexus.mq.adapter import MqAdapterStub
from nexus.mq.agent_message_capability_policy import AgentMessagePolicyDecision
from nexus.mq.live_transport_evidence import TransportEvidenceRecord, evidence_record
from nexus.mq.message_contracts import ExecutionMessageEnvelope, validate_wbs717_diagnostic_envelope
from nexus.mq.protocol_routing import validate_wbs717_subject


@dataclass
class CredentialResolutionResult:
    accepted: bool
    credential_ref: str
    resolver_ref: str = ""
    errors: list[str] = field(default_factory=list)
    material_exposed: bool = False


@dataclass
class LiveSendResult:
    accepted: bool
    published: bool
    subject: str
    ack: Optional[dict[str, Any]]
    evidence: list[TransportEvidenceRecord]
    errors: list[str]
    not_business_completion: bool = True


@dataclass
class LiveReceiveResult:
    accepted: bool
    acked: bool
    duplicate: bool
    side_effects_allowed: bool
    subject: str
    envelope: Optional[dict[str, Any]]
    ack: Optional[dict[str, Any]]
    evidence: list[TransportEvidenceRecord]
    errors: list[str]
    not_business_completion: bool = True


@dataclass
class RunScopedDedupeLedger:
    claims: dict[str, tuple[str, str]] = field(default_factory=dict)

    def claim(self, *, idempotency_key: str, payload_hash: str, message_id: str) -> bool:
        existing = self.claims.get(idempotency_key)
        if existing is not None:
            return False
        self.claims[idempotency_key] = (payload_hash, message_id)
        return True


def publish_live_message(
    adapter: MqAdapterStub,
    envelope: ExecutionMessageEnvelope,
    *,
    subject: str,
    policy_decision: AgentMessagePolicyDecision,
    credential_result: CredentialResolutionResult,
) -> LiveSendResult:
    errors = _send_preflight_errors(
        envelope,
        subject=subject,
        policy_decision=policy_decision,
        credential_result=credential_result,
    )
    evidence: list[TransportEvidenceRecord] = [
        evidence_record(
            "publish_preflight",
            message_id=envelope.message_id,
            subject=subject,
            status="accepted" if not errors else "rejected",
            errors=errors,
        )
    ]
    if errors:
        return LiveSendResult(
            accepted=False,
            published=False,
            subject=subject,
            ack=None,
            evidence=evidence,
            errors=errors,
        )

    envelope_dict = envelope.to_dict()
    envelope_dict["subject"] = subject
    ack = adapter.publish(envelope_dict)
    evidence.append(
        evidence_record(
            "publish",
            message_id=envelope.message_id,
            subject=subject,
            status="broker_received",
            details={"ack": ack, "credential_ref": credential_result.credential_ref},
        )
    )
    return LiveSendResult(
        accepted=True,
        published=True,
        subject=subject,
        ack=ack,
        evidence=evidence,
        errors=[],
    )


def receive_live_message_once(
    adapter: MqAdapterStub,
    *,
    expected_subject: str,
    expected_target_agent_id: str,
    expected_target_runtime_instance_id: str,
    policy_decision: AgentMessagePolicyDecision,
    dedupe_ledger: RunScopedDedupeLedger,
    safe_intake: Callable[[dict[str, Any]], dict[str, Any]],
) -> LiveReceiveResult:
    message = adapter.consume()
    if message is None:
        evidence = [
            evidence_record(
                "timeout_or_anomaly",
                message_id="",
                subject=expected_subject,
                status="empty_queue",
                errors=["NO_MESSAGE_AVAILABLE"],
            )
        ]
        return LiveReceiveResult(
            accepted=False,
            acked=False,
            duplicate=False,
            side_effects_allowed=False,
            subject=expected_subject,
            envelope=None,
            ack=None,
            evidence=evidence,
            errors=["NO_MESSAGE_AVAILABLE"],
        )

    envelope = message["envelope"]
    subject = str(message["subject"])
    errors = _receive_preflight_errors(
        envelope,
        subject=subject,
        expected_subject=expected_subject,
        expected_target_agent_id=expected_target_agent_id,
        expected_target_runtime_instance_id=expected_target_runtime_instance_id,
        policy_decision=policy_decision,
    )
    evidence = [
        evidence_record(
            "receive",
            message_id=str(envelope.get("message_id", "")),
            subject=subject,
            status="accepted" if not errors else "rejected",
            errors=errors,
        )
    ]
    if errors:
        return LiveReceiveResult(
            accepted=False,
            acked=False,
            duplicate=False,
            side_effects_allowed=False,
            subject=subject,
            envelope=envelope,
            ack=None,
            evidence=evidence,
            errors=errors,
        )

    claimed = dedupe_ledger.claim(
        idempotency_key=str(envelope.get("idempotency_key", "")),
        payload_hash=str(envelope.get("payload_hash", "")),
        message_id=str(envelope.get("message_id", "")),
    )
    if not claimed:
        ack = adapter.ack(str(envelope["message_id"]))
        evidence.extend(
            [
                evidence_record(
                    "duplicate",
                    message_id=str(envelope["message_id"]),
                    subject=subject,
                    status="suppressed",
                ),
                evidence_record(
                    "ack",
                    message_id=str(envelope["message_id"]),
                    subject=subject,
                    status="consumer_intake",
                    details={"ack": ack},
                ),
            ]
        )
        return LiveReceiveResult(
            accepted=True,
            acked=True,
            duplicate=True,
            side_effects_allowed=False,
            subject=subject,
            envelope=envelope,
            ack=ack,
            evidence=evidence,
            errors=[],
        )

    intake_record = safe_intake(envelope)
    ack = adapter.ack(str(envelope["message_id"]))
    evidence.append(
        evidence_record(
            "ack",
            message_id=str(envelope["message_id"]),
            subject=subject,
            status="consumer_intake",
            details={"ack": ack, "intake": intake_record},
        )
    )
    return LiveReceiveResult(
        accepted=True,
        acked=True,
        duplicate=False,
        side_effects_allowed=True,
        subject=subject,
        envelope=envelope,
        ack=ack,
        evidence=evidence,
        errors=[],
    )


def publish_return_message(
    adapter: MqAdapterStub,
    envelope: ExecutionMessageEnvelope,
    *,
    policy_decision: AgentMessagePolicyDecision,
    credential_result: CredentialResolutionResult,
) -> LiveSendResult:
    result = publish_live_message(
        adapter,
        envelope,
        subject=str(envelope.reply_to_subject),
        policy_decision=policy_decision,
        credential_result=credential_result,
    )
    if result.published:
        result.evidence.append(
            evidence_record(
                "return",
                message_id=envelope.message_id,
                subject=str(envelope.reply_to_subject),
                status="broker_received",
                details={"not_business_completion": True},
            )
        )
    return result


def _send_preflight_errors(
    envelope: ExecutionMessageEnvelope,
    *,
    subject: str,
    policy_decision: AgentMessagePolicyDecision,
    credential_result: CredentialResolutionResult,
) -> list[str]:
    errors: list[str] = []
    validation = validate_wbs717_diagnostic_envelope(envelope)
    errors.extend(validation.errors)
    subject_validation = validate_wbs717_subject(subject, envelope.workflow_instance_id)
    if not subject_validation.valid:
        errors.extend(subject_validation.errors or [])
    errors.extend(_policy_errors(policy_decision))
    if not credential_result.accepted:
        errors.extend(credential_result.errors or ["CREDENTIAL_RESOLUTION_REJECTED"])
    if credential_result.material_exposed:
        errors.append("CREDENTIAL_MATERIAL_EXPOSED")
    return list(dict.fromkeys(errors))


def _receive_preflight_errors(
    envelope: dict[str, Any],
    *,
    subject: str,
    expected_subject: str,
    expected_target_agent_id: str,
    expected_target_runtime_instance_id: str,
    policy_decision: AgentMessagePolicyDecision,
) -> list[str]:
    errors: list[str] = []
    validation = validate_wbs717_diagnostic_envelope(envelope)
    errors.extend(validation.errors)
    if subject != expected_subject:
        errors.append(f"WBS717_SUBJECT_MISMATCH: expected {expected_subject}, got {subject}")
    subject_validation = validate_wbs717_subject(subject, str(envelope.get("workflow_instance_id", "")))
    if not subject_validation.valid:
        errors.extend(subject_validation.errors or [])
    if envelope.get("target_agent_id") != expected_target_agent_id:
        errors.append("WBS717_TARGET_AGENT_MISMATCH")
    if envelope.get("target_runtime_instance_id") != expected_target_runtime_instance_id:
        errors.append("WBS717_TARGET_RUNTIME_MISMATCH")
    errors.extend(_policy_errors(policy_decision))
    return list(dict.fromkeys(errors))


def _policy_errors(policy_decision: AgentMessagePolicyDecision) -> list[str]:
    if not policy_decision.allowed:
        return policy_decision.errors or ["AGENT_MESSAGE_POLICY_DENIED"]
    return []
