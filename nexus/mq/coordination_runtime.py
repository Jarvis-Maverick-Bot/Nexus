"""Durable coordination runtime primitives for always-on MQ/HITL work."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
import uuid

from nexus.mq.abnormal_state import (
    AbnormalStateRecord,
    ResolutionRecord,
    classify_abnormal_state,
    resolve_abnormal_state,
)
from nexus.mq.durable_state import (
    CallbackWaitRecord,
    DurableStateStore,
    PendingTaskRecord,
    RuntimeStatusRecord,
    SideEffectOutboxRecord,
)
from nexus.mq.hitl_lifecycle import AuthorityWaitStateV03, HitlDecisionRecordV03, HitlExecutionLifecycle
from nexus.mq.identity import AgentIdentityStore
from nexus.mq.message_contracts import (
    ContractValidationResult,
    ExecutionMessageEnvelope,
    build_execution_envelope,
    is_transport_active,
    validate_execution_message,
)
from nexus.mq.payloads import FeedbackMessagePayload, ReviewTaskPayload, TimeoutMessagePayload
from nexus.mq.protocol import ProtocolEnvelope, build_protocol_envelope
from nexus.mq.protocol_boundary import ProtocolMessageBoundary
from nexus.mq.protocol_routing import build_ops_timeout_subject, route_execution_envelope_dict


UTC = timezone.utc

RETRYABLE_EXPIRY_SUBJECT_PREFIXES = ("review.", "ops.timeout")
AUTHORITY_ERROR_MARKERS = (
    "UNKNOWN_SENDER",
    "SOURCE_ROLE_MISMATCH",
    "INVALID_SOURCE_ROLE",
    "INVALID_AUTHORITY_SCOPE",
    "UNKNOWN_TARGET",
    "TARGET_AGENT_MISMATCH",
    "UNTRUSTED_SUBJECT",
)


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _summarize_timeout_payload(record_type: str, record_id: str, reason: str, context: dict) -> dict:
    return {
        "error_code": "TIMEOUT",
        "record_type": record_type,
        "record_id": record_id,
        "reason": reason,
        "context": context,
    }


@dataclass
class RuntimeIntakeResult:
    valid: bool
    ack_allowed: bool
    duplicate: bool = False
    pending_task: Optional[PendingTaskRecord] = None
    envelope: Optional[Any] = None
    intake_record: Optional[Any] = None
    broker_action: Optional[str] = None
    failure_class: Optional[str] = None
    existing_result: Optional[Any] = None
    errors: list[str] = field(default_factory=list)


@dataclass
class CallbackReceiveResult:
    valid: bool
    ack_allowed: bool
    matched: bool
    callback_wait: Optional[CallbackWaitRecord] = None
    envelope: Optional[Any] = None
    intake_record: Optional[Any] = None
    broker_action: Optional[str] = None
    failure_class: Optional[str] = None
    errors: list[str] = field(default_factory=list)


@dataclass
class FeedbackReceiveResult:
    valid: bool
    ack_allowed: bool
    decision: Optional[HitlDecisionRecordV03] = None
    authority_wait: Optional[AuthorityWaitStateV03] = None
    outcome: Optional[str] = None
    raw_feedback_record: Optional[Any] = None
    normalized_decision_record: Optional[Any] = None
    resume_request_record: Optional[Any] = None
    duplicate_resolution_record: Optional[Any] = None
    envelope: Optional[ExecutionMessageEnvelope] = None
    intake_record: Optional[Any] = None
    broker_action: Optional[str] = None
    failure_class: Optional[str] = None
    errors: list[str] = field(default_factory=list)


@dataclass
class TimeoutScanResult:
    task_timeout_envelopes: list[Any]
    callback_timeout_envelopes: list[Any]
    authority_wait_timeout_envelopes: list[Any] = field(default_factory=list)


class CoordinationRuntime:
    """Small durable coordination layer for the accepted always-on runtime."""

    def __init__(
        self,
        runtime_id: str,
        agent_id: str,
        role: str,
        state_store: DurableStateStore,
        identity_store: AgentIdentityStore,
    ):
        self.runtime_id = runtime_id
        self.agent_id = agent_id
        self.role = role
        self.state_store = state_store
        self.identity_store = identity_store
        self.boundary = ProtocolMessageBoundary(identity_store)
        self.hitl_lifecycle = HitlExecutionLifecycle()
        agent = identity_store.get_agent(agent_id)
        if agent is None:
            raise ValueError(f"unknown runtime agent: {agent_id}")
        self._runtime_instance_id = agent.runtime_instance_id

    @classmethod
    def from_paths(
        cls,
        runtime_id: str,
        agent_id: str,
        role: str,
        db_path: str | Path,
        identity_yaml_path: str | Path,
    ) -> "CoordinationRuntime":
        return cls(
            runtime_id=runtime_id,
            agent_id=agent_id,
            role=role,
            state_store=DurableStateStore(db_path),
            identity_store=AgentIdentityStore.from_yaml_file(str(identity_yaml_path)),
        )

    def startup(self) -> RuntimeStatusRecord:
        valid, errors = self.state_store.verify_integrity()
        if not valid:
            return self.state_store.quarantine_runtime(
                runtime_id=self.runtime_id,
                agent_id=self.agent_id,
                reason="; ".join(errors),
            )
        self._rehydrate_hitl_state()
        return self.state_store.set_runtime_status(
            runtime_id=self.runtime_id,
            agent_id=self.agent_id,
            status="ACTIVE",
        )

    def close(self) -> None:
        self.state_store.close()

    def intake_inbound_message(self, subject: str, envelope_dict: dict) -> RuntimeIntakeResult:
        if not isinstance(envelope_dict, dict):
            return self._record_terminal_intake_failure(
                subject=subject,
                raw_inbound=envelope_dict,
                errors=["MALFORMED_ENVELOPE"],
                failure_class="IF-01",
                failure_subclass="malformed_unparseable_envelope",
                broker_action="REJECT",
                terminal_outcome="terminal",
                anomaly_code="schema_invalid",
            )
        if envelope_dict.get("protocol_version"):
            return self._intake_protocol_message(subject, envelope_dict)
        return self._intake_execution_message(subject, envelope_dict)

    def mark_task_completed(
        self,
        task_id: str,
        idempotency_key: str,
        message_id: str,
        workflow_id: str,
        result_payload: dict,
    ) -> PendingTaskRecord:
        record = self.state_store.update_pending_task(
            task_id=task_id,
            state="COMPLETED",
            updated_by=self.runtime_id,
            result_payload=result_payload,
            completed_at=datetime.now(UTC).isoformat(),
        )
        self.state_store.record_idempotency(
            idempotency_key=idempotency_key,
            message_id=message_id,
            workflow_id=workflow_id,
            result_detail=result_payload,
        )
        self.state_store.complete_envelope_inbox(message_id)
        return record

    def register_callback_wait(self, request_envelope: ProtocolEnvelope) -> CallbackWaitRecord:
        return self.state_store.create_callback_wait(
            callback_id=f"wait-{request_envelope.message_id}",
            correlation_id=request_envelope.correlation_id,
            expected_subject=request_envelope.reply_to_subject or "",
            expected_source_agent_id=request_envelope.target_agent_id or "",
            request_message_id=request_envelope.message_id,
            task_id=f"task-{request_envelope.message_id}",
            callback_type=request_envelope.message_type,
            payload=request_envelope.to_dict(),
            reply_subject=request_envelope.reply_to_subject,
            deadline_at=request_envelope.expires_at,
            created_by=self.runtime_id,
        )

    def create_authority_wait_state(
        self,
        workflow_instance_id: str,
        checkpoint_id: str,
        gate_id: str,
        requested_actor_role: str,
        evidence_package_id: Optional[str] = None,
        due_at: Optional[str] = None,
    ) -> AuthorityWaitStateV03:
        wait = self.hitl_lifecycle.create_authority_wait_state(
            workflow_instance_id=workflow_instance_id,
            checkpoint_id=checkpoint_id,
            gate_id=gate_id,
            requested_actor_role=requested_actor_role,
            evidence_package_id=evidence_package_id,
            due_at=due_at,
        )
        self._persist_authority_wait_state(wait)
        self.state_store.create_phase3_runtime_record(
            record_type="active_wait_record",
            workflow_instance_id=workflow_instance_id,
            authority_wait_id=wait.authority_wait_id,
            related_message_id=None,
            dedupe_key=f"{workflow_instance_id}:{checkpoint_id}:{gate_id}",
            status="created",
            payload={
                "workflow_instance_id": workflow_instance_id,
                "checkpoint_id": checkpoint_id,
                "gate_id": gate_id,
                "requested_actor_role": requested_actor_role,
                "due_at": due_at,
            },
        )
        return wait

    def register_review_task_message(
        self,
        authority_wait_id: str,
        review_task_message_id: str,
        review_task_id: Optional[str] = None,
        published: bool = False,
        publication_error: Optional[str] = None,
        resume_from_ref: Optional[str] = None,
    ) -> AuthorityWaitStateV03:
        wait = self._require_wait(authority_wait_id)
        payload = dict(getattr(wait, "payload", {}) or {})
        payload["review_task_message_id"] = review_task_message_id
        if review_task_id:
            payload["review_task_id"] = review_task_id
        if resume_from_ref:
            payload["resume_from_ref"] = resume_from_ref
        payload["publication_status"] = "published" if published else "pending"
        if publication_error:
            payload["publication_error"] = publication_error
        wait.payload = payload
        if published:
            wait.status = "waiting"
        elif publication_error:
            wait.status = "publication_failed"
        stored = self.state_store.create_authority_wait_state(
            authority_wait_id=wait.authority_wait_id,
            workflow_instance_id=wait.workflow_instance_id,
            checkpoint_id=wait.checkpoint_id,
            gate_id=wait.gate_id,
            requested_actor_role=wait.requested_actor_role,
            status=wait.status,
            review_task_message_id=review_task_message_id,
            evidence_package_id=wait.evidence_package_id,
            due_at=wait.due_at,
            responded_at=wait.responded_at,
            resolved_at=wait.resolved_at,
            hitl_decision_id=wait.hitl_decision_id,
            created_at=wait.created_at,
            payload=wait.payload,
        )
        return self._load_wait_from_store(stored)

    def record_review_task_publication(
        self,
        authority_wait_id: str,
        review_task_message_id: str,
        review_task_id: str,
        resume_from_ref: Optional[str],
    ) -> Any:
        wait = self.register_review_task_message(
            authority_wait_id=authority_wait_id,
            review_task_message_id=review_task_message_id,
            review_task_id=review_task_id,
            published=True,
            resume_from_ref=resume_from_ref,
        )
        return self.state_store.create_phase3_runtime_record(
            record_type="review_task_publication_record",
            workflow_instance_id=wait.workflow_instance_id,
            authority_wait_id=wait.authority_wait_id,
            related_message_id=review_task_message_id,
            dedupe_key=review_task_message_id,
            status="published",
            payload={
                "review_task_id": review_task_id,
                "review_task_message_id": review_task_message_id,
                "correlation_id": wait.authority_wait_id,
                "resume_from_ref": resume_from_ref,
                "due_at": wait.due_at,
            },
        )

    def record_review_task_publication_failure(
        self,
        authority_wait_id: str,
        review_task_message_id: str,
        review_task_id: str,
        error: str,
    ) -> Any:
        wait = self.register_review_task_message(
            authority_wait_id=authority_wait_id,
            review_task_message_id=review_task_message_id,
            review_task_id=review_task_id,
            published=False,
            publication_error=error,
        )
        return self.state_store.create_phase3_runtime_record(
            record_type="review_task_publication_failure_record",
            workflow_instance_id=wait.workflow_instance_id,
            authority_wait_id=wait.authority_wait_id,
            related_message_id=review_task_message_id,
            dedupe_key=review_task_message_id,
            status="publication_failed",
            payload={
                "review_task_id": review_task_id,
                "review_task_message_id": review_task_message_id,
                "error": error,
            },
        )

    def record_outbox_publish(self, envelope: Any) -> SideEffectOutboxRecord:
        payload = envelope.to_dict() if hasattr(envelope, "to_dict") else dict(envelope)
        return self.state_store.create_outbox_record(
            side_effect_type=f"publish_{payload.get('message_type', 'unknown')}",
            target=payload.get("reply_to_subject") or payload.get("target_agent_id") or payload.get("subject") or "unknown",
            correlation_id=payload.get("correlation_id", ""),
            payload=payload,
            created_by=self.runtime_id,
            message_id=payload.get("message_id"),
            causation_id=payload.get("causation_id") if isinstance(payload.get("causation_id"), str) else None,
        )

    def confirm_outbox_publish(self, outbox_id: str) -> SideEffectOutboxRecord:
        published = self.state_store.mark_outbox_published(outbox_id)
        return self.state_store.mark_outbox_confirmed(published.outbox_id, confirmed_by=self.runtime_id)

    def receive_callback(self, subject: str, envelope_dict: dict) -> CallbackReceiveResult:
        if not isinstance(envelope_dict, dict):
            terminal = self._record_terminal_intake_failure(
                subject=subject,
                raw_inbound=envelope_dict,
                errors=["MALFORMED_ENVELOPE"],
                failure_class="IF-01",
                failure_subclass="malformed_unparseable_envelope",
                broker_action="REJECT",
                terminal_outcome="terminal",
                anomaly_code="schema_invalid",
            )
            return CallbackReceiveResult(
                valid=False,
                ack_allowed=False,
                matched=False,
                intake_record=terminal.intake_record,
                broker_action=terminal.broker_action,
                failure_class=terminal.failure_class,
                errors=terminal.errors,
            )
        if envelope_dict.get("protocol_version"):
            return self._receive_protocol_callback(subject, envelope_dict)

        contract = validate_execution_message(envelope_dict, require_runtime_overlay=True)
        envelope = ExecutionMessageEnvelope.from_dict(envelope_dict)
        if not contract.valid or envelope.message_type != "Business_Message":
            errors = list(contract.errors)
            if envelope.message_type != "Business_Message":
                errors.append(f"INVALID_CALLBACK_FAMILY: {envelope.message_type}")
            terminal = self._record_terminal_intake_failure(
                subject=subject,
                raw_inbound=envelope_dict,
                normalized_envelope=envelope.to_dict(),
                errors=errors,
                failure_class="IF-02",
                failure_subclass="schema_validation_failure",
                broker_action="REJECT",
                terminal_outcome="terminal",
                anomaly_code="schema_invalid",
                workflow_instance_id=envelope.workflow_instance_id,
                message_id=envelope.message_id,
                causation_id=envelope.causation_id,
                correlation_id=envelope.correlation_id,
                source_agent_id=envelope.source_agent_id,
                target_agent_id=envelope.target_agent_id,
            )
            return CallbackReceiveResult(
                valid=False,
                ack_allowed=False,
                matched=False,
                errors=errors,
                envelope=envelope,
                intake_record=terminal.intake_record,
                broker_action=terminal.broker_action,
                failure_class=terminal.failure_class,
            )

        errors = self._validate_execution_runtime_boundary(subject, envelope)
        errors.extend(self._validate_temporal_prerequisites(envelope))
        if errors:
            terminal = self._record_terminal_intake_failure(
                subject=subject,
                raw_inbound=envelope_dict,
                normalized_envelope=envelope.to_dict(),
                errors=errors,
                failure_class="IF-03" if self._is_authority_scope_mismatch(errors) else "IF-04",
                failure_subclass="authority_scope_mismatch" if self._is_authority_scope_mismatch(errors) else "expired_callback",
                broker_action="REJECT" if self._is_authority_scope_mismatch(errors) else self._broker_action_for_expired_subject(subject, envelope.message_type),
                terminal_outcome="terminal" if self._broker_action_for_expired_subject(subject, envelope.message_type) != "NAK" else "retry",
                anomaly_code="authority_stall" if self._is_authority_scope_mismatch(errors) else self._anomaly_code_for_expiry(subject, envelope.message_type),
                abnormal_error_class="authority_unresolved" if self._is_authority_scope_mismatch(errors) else None,
                workflow_instance_id=envelope.workflow_instance_id,
                message_id=envelope.message_id,
                causation_id=envelope.causation_id,
                correlation_id=envelope.correlation_id,
                source_agent_id=envelope.source_agent_id,
                target_agent_id=envelope.target_agent_id,
            )
            return CallbackReceiveResult(
                valid=False,
                ack_allowed=False,
                matched=False,
                errors=errors,
                envelope=envelope,
                intake_record=terminal.intake_record,
                broker_action=terminal.broker_action,
                failure_class=terminal.failure_class,
            )

        waits = self.state_store.list_waiting_callbacks()
        match = next(
            (
                wait
                for wait in waits
                if wait.correlation_id == envelope.correlation_id
                and wait.request_message_id == envelope.causation_id
                and wait.expected_subject == subject
                and wait.expected_source_agent_id == envelope.source_agent_id
            ),
            None,
        )
        if match is None:
            terminal = self._record_terminal_intake_failure(
                subject=subject,
                raw_inbound=envelope_dict,
                normalized_envelope=envelope.to_dict(),
                errors=[f"ORPHAN_CALLBACK: {envelope.message_id}"],
                failure_class="IF-07",
                failure_subclass="unknown_correlation_causation",
                broker_action="REJECT",
                terminal_outcome="terminal",
                anomaly_code="other",
                abnormal_error_class="other",
                workflow_instance_id=envelope.workflow_instance_id,
                message_id=envelope.message_id,
                causation_id=envelope.causation_id,
                correlation_id=envelope.correlation_id,
                source_agent_id=envelope.source_agent_id,
                target_agent_id=envelope.target_agent_id,
            )
            return CallbackReceiveResult(
                valid=False,
                ack_allowed=False,
                matched=False,
                errors=[f"ORPHAN_CALLBACK: {envelope.message_id}"],
                envelope=envelope,
                intake_record=terminal.intake_record,
                broker_action=terminal.broker_action,
                failure_class=terminal.failure_class,
            )

        self.state_store.record_envelope_inbox(
            envelope_id=envelope.message_id,
            subject=subject,
            payload=envelope.to_dict(),
            normalized_execution_envelope=envelope.to_dict(),
            message_id=envelope.message_id,
            workflow_instance_id=envelope.workflow_instance_id,
            causation_id=envelope.causation_id,
            correlation_id=envelope.correlation_id,
            source_agent_id=envelope.source_agent_id,
            target_agent_id=envelope.target_agent_id,
        )
        completed = self.state_store.complete_callback_wait(
            callback_id=match.callback_id,
            response_payload=envelope.to_dict(),
        )
        self.state_store.complete_envelope_inbox(envelope.message_id)
        return CallbackReceiveResult(
            valid=True,
            ack_allowed=True,
            matched=True,
            callback_wait=completed,
            envelope=envelope,
            broker_action="ACK",
        )

    def receive_feedback(self, subject: str, envelope_dict: dict) -> FeedbackReceiveResult:
        if not isinstance(envelope_dict, dict):
            terminal = self._record_terminal_intake_failure(
                subject=subject,
                raw_inbound=envelope_dict,
                errors=["MALFORMED_ENVELOPE"],
                failure_class="IF-01",
                failure_subclass="malformed_unparseable_envelope",
                broker_action="REJECT",
                terminal_outcome="terminal",
                anomaly_code="schema_invalid",
            )
            return FeedbackReceiveResult(
                valid=False,
                ack_allowed=False,
                errors=terminal.errors,
                intake_record=terminal.intake_record,
                broker_action=terminal.broker_action,
                failure_class=terminal.failure_class,
            )

        contract = validate_execution_message(envelope_dict, require_runtime_overlay=True)
        envelope = ExecutionMessageEnvelope.from_dict(envelope_dict)
        if not contract.valid or envelope.message_type != "Feedback_Message":
            errors = list(contract.errors)
            if envelope.message_type != "Feedback_Message":
                errors.append(f"INVALID_FEEDBACK_FAMILY: {envelope.message_type}")
            terminal = self._record_terminal_intake_failure(
                subject=subject,
                raw_inbound=envelope_dict,
                normalized_envelope=envelope.to_dict(),
                errors=errors,
                failure_class="IF-02",
                failure_subclass="schema_validation_failure",
                broker_action="REJECT",
                terminal_outcome="terminal",
                anomaly_code="schema_invalid",
                workflow_instance_id=envelope.workflow_instance_id,
                message_id=envelope.message_id,
                causation_id=envelope.causation_id,
                correlation_id=envelope.correlation_id,
                source_agent_id=envelope.source_agent_id,
                target_agent_id=envelope.target_agent_id,
            )
            return FeedbackReceiveResult(
                valid=False,
                ack_allowed=False,
                errors=errors,
                envelope=envelope,
                intake_record=terminal.intake_record,
                broker_action=terminal.broker_action,
                failure_class=terminal.failure_class,
            )

        errors = self._validate_execution_runtime_boundary(subject, envelope)
        errors.extend(self._validate_temporal_prerequisites(envelope))
        if errors:
            failure_class = "IF-04" if any(error == "MESSAGE_EXPIRED" for error in errors) else "IF-03"
            broker_action = self._broker_action_for_expired_subject(subject, envelope.message_type) if failure_class == "IF-04" else "REJECT"
            terminal = self._record_terminal_intake_failure(
                subject=subject,
                raw_inbound=envelope_dict,
                normalized_envelope=envelope.to_dict(),
                errors=errors,
                failure_class=failure_class,
                failure_subclass="expired_feedback" if failure_class == "IF-04" else "authority_scope_mismatch",
                broker_action=broker_action,
                terminal_outcome="retry" if broker_action == "NAK" else "terminal",
                anomaly_code=None if broker_action == "NAK" else (
                    "authority_stall" if failure_class == "IF-03" else self._anomaly_code_for_expiry(subject, envelope.message_type)
                ),
                abnormal_error_class="authority_unresolved" if failure_class == "IF-03" else None,
                workflow_instance_id=envelope.workflow_instance_id,
                message_id=envelope.message_id,
                causation_id=envelope.causation_id,
                correlation_id=envelope.correlation_id,
                source_agent_id=envelope.source_agent_id,
                target_agent_id=envelope.target_agent_id,
            )
            return FeedbackReceiveResult(
                valid=False,
                ack_allowed=False,
                errors=errors,
                envelope=envelope,
                intake_record=terminal.intake_record,
                broker_action=terminal.broker_action,
                failure_class=terminal.failure_class,
            )

        payload_contract = contract.payload_contract
        if not isinstance(payload_contract, FeedbackMessagePayload):
            terminal = self._record_terminal_intake_failure(
                subject=subject,
                raw_inbound=envelope_dict,
                normalized_envelope=envelope.to_dict(),
                errors=["PAYLOAD_SCHEMA_MISMATCH: Feedback_Message"],
                failure_class="IF-02",
                failure_subclass="schema_validation_failure",
                broker_action="REJECT",
                terminal_outcome="terminal",
                anomaly_code="schema_invalid",
                workflow_instance_id=envelope.workflow_instance_id,
                message_id=envelope.message_id,
                causation_id=envelope.causation_id,
                correlation_id=envelope.correlation_id,
                source_agent_id=envelope.source_agent_id,
                target_agent_id=envelope.target_agent_id,
            )
            return FeedbackReceiveResult(
                valid=False,
                ack_allowed=False,
                errors=["PAYLOAD_SCHEMA_MISMATCH: Feedback_Message"],
                envelope=envelope,
                intake_record=terminal.intake_record,
                broker_action=terminal.broker_action,
                failure_class=terminal.failure_class,
            )

        stored_wait = self.state_store.get_authority_wait_state(payload_contract.authority_wait_id)
        raw_feedback_status = "received"
        raw_feedback_payload = {
            "feedback_id": payload_contract.feedback_id,
            "review_task_id": payload_contract.review_task_id,
            "correlation_id": envelope.correlation_id,
            "causation_id": envelope.causation_id,
            "reviewer_actor_id": payload_contract.reviewer_actor_id,
            "reviewer_role": payload_contract.reviewer_role,
            "action": payload_contract.action,
        }
        if stored_wait is None:
            raw_feedback_record = self.state_store.create_phase3_runtime_record(
                record_type="raw_feedback_intake_record",
                workflow_instance_id=envelope.workflow_instance_id,
                authority_wait_id=payload_contract.authority_wait_id,
                related_message_id=envelope.message_id,
                dedupe_key=f"{payload_contract.authority_wait_id}:{payload_contract.feedback_id}:{envelope.message_id}",
                status="feedback_rejected_stale",
                payload=raw_feedback_payload,
            )
            terminal = self._record_terminal_intake_failure(
                subject=subject,
                raw_inbound=envelope_dict,
                normalized_envelope=envelope.to_dict(),
                errors=[f"FEEDBACK_STALE: authority_wait_state not found: {payload_contract.authority_wait_id}"],
                failure_class="IF-08",
                failure_subclass="invalid_hitl_callback",
                broker_action="REJECT",
                terminal_outcome="terminal",
                anomaly_code="authority_stall",
                abnormal_error_class="authority_unresolved",
                workflow_instance_id=envelope.workflow_instance_id,
                message_id=envelope.message_id,
                causation_id=envelope.causation_id,
                correlation_id=envelope.correlation_id,
                source_agent_id=envelope.source_agent_id,
                target_agent_id=envelope.target_agent_id,
            )
            return FeedbackReceiveResult(
                valid=False,
                ack_allowed=False,
                outcome="feedback_rejected_stale",
                raw_feedback_record=raw_feedback_record,
                errors=[f"FEEDBACK_STALE: authority_wait_state not found: {payload_contract.authority_wait_id}"],
                envelope=envelope,
                intake_record=terminal.intake_record,
                broker_action=terminal.broker_action,
                failure_class=terminal.failure_class,
            )

        raw_feedback_record = self.state_store.create_phase3_runtime_record(
            record_type="raw_feedback_intake_record",
            workflow_instance_id=envelope.workflow_instance_id,
            authority_wait_id=stored_wait.authority_wait_id,
            related_message_id=envelope.message_id,
            dedupe_key=f"{stored_wait.authority_wait_id}:{payload_contract.feedback_id}:{envelope.message_id}",
            status=raw_feedback_status,
            payload=raw_feedback_payload,
        )
        duplicate_key = f"{stored_wait.authority_wait_id}:{payload_contract.feedback_id}:{payload_contract.action}"
        prior_decision_record = self.state_store.find_phase3_runtime_record(
            record_type="normalized_decision_record",
            dedupe_key=duplicate_key,
        )
        if prior_decision_record is not None:
            duplicate_resolution_record = self.state_store.create_phase3_runtime_record(
                record_type="duplicate_feedback_resolution_record",
                workflow_instance_id=stored_wait.workflow_instance_id,
                authority_wait_id=stored_wait.authority_wait_id,
                related_message_id=envelope.message_id,
                dedupe_key=f"{stored_wait.authority_wait_id}:{payload_contract.feedback_id}",
                status="feedback_accepted_duplicate",
                payload={
                    "prior_decision_record_id": prior_decision_record.record_id,
                    "prior_decision_id": prior_decision_record.payload.get("decision_id"),
                    "feedback_id": payload_contract.feedback_id,
                },
            )
            decision_payload = prior_decision_record.payload.get("decision_payload", {})
            return FeedbackReceiveResult(
                valid=True,
                ack_allowed=True,
                decision=HitlDecisionRecordV03(**decision_payload) if decision_payload else None,
                authority_wait=self._load_wait_from_store(stored_wait),
                outcome="feedback_accepted_duplicate",
                raw_feedback_record=raw_feedback_record,
                normalized_decision_record=prior_decision_record,
                duplicate_resolution_record=duplicate_resolution_record,
                envelope=envelope,
                broker_action="ACK",
            )

        if stored_wait.status in {"resolved", "superseded", "timed_out", "escalated", "stale"}:
            terminal = self._record_terminal_intake_failure(
                subject=subject,
                raw_inbound=envelope_dict,
                normalized_envelope=envelope.to_dict(),
                errors=[f"FEEDBACK_STALE: authority_wait_state is {stored_wait.status}"],
                failure_class="IF-08",
                failure_subclass="invalid_hitl_callback",
                broker_action="REJECT",
                terminal_outcome="terminal",
                anomaly_code="authority_stall",
                abnormal_error_class="authority_unresolved",
                workflow_instance_id=envelope.workflow_instance_id,
                message_id=envelope.message_id,
                causation_id=envelope.causation_id,
                correlation_id=envelope.correlation_id,
                source_agent_id=envelope.source_agent_id,
                target_agent_id=envelope.target_agent_id,
            )
            return FeedbackReceiveResult(
                valid=False,
                ack_allowed=False,
                outcome="feedback_rejected_stale",
                raw_feedback_record=raw_feedback_record,
                errors=[f"FEEDBACK_STALE: authority_wait_state is {stored_wait.status}"],
                envelope=envelope,
                intake_record=terminal.intake_record,
                broker_action=terminal.broker_action,
                failure_class=terminal.failure_class,
            )
        if stored_wait.status == "closed":
            return FeedbackReceiveResult(
                valid=False,
                ack_allowed=True,
                outcome="feedback_rejected_closed",
                raw_feedback_record=raw_feedback_record,
                errors=["FEEDBACK_CLOSED: authority_wait_state is closed"],
                envelope=envelope,
                broker_action="ACK",
                failure_class="HITL-CLOSED",
            )

        wait = self._load_wait_from_store(stored_wait)
        expected_review_task_id = (stored_wait.payload or {}).get("review_task_id")
        validation_errors: list[str] = []
        if not stored_wait.review_task_message_id or stored_wait.status == "publication_failed":
            validation_errors.append("REVIEW_TASK_NOT_PUBLISHED")
        if expected_review_task_id and expected_review_task_id != payload_contract.review_task_id:
            validation_errors.append("INVALID_REVIEW_TASK_LINKAGE")
        if stored_wait.requested_actor_role not in {"", "reviewer"} and payload_contract.reviewer_role != stored_wait.requested_actor_role:
            validation_errors.append("INVALID_FEEDBACK_ACTOR_SCOPE")
        if payload_contract.reviewer_actor_id != envelope.source_agent_id:
            validation_errors.append("INVALID_FEEDBACK_ACTOR_ID")

        correlation = self.hitl_lifecycle.validate_feedback_correlation(
            authority_wait_id=wait.authority_wait_id,
            correlation_id=envelope.correlation_id,
            review_task_message_id=stored_wait.review_task_message_id or payload_contract.review_task_id,
            causation_id=envelope.causation_id,
        )
        validation_errors.extend(correlation.errors)

        if validation_errors:
            terminal = self._record_terminal_intake_failure(
                subject=subject,
                raw_inbound=envelope_dict,
                normalized_envelope=envelope.to_dict(),
                errors=validation_errors,
                failure_class="IF-08",
                failure_subclass="invalid_hitl_callback",
                broker_action="REJECT",
                terminal_outcome="terminal",
                anomaly_code="authority_stall",
                abnormal_error_class="authority_unresolved",
                workflow_instance_id=envelope.workflow_instance_id,
                message_id=envelope.message_id,
                causation_id=envelope.causation_id,
                correlation_id=envelope.correlation_id,
                source_agent_id=envelope.source_agent_id,
                target_agent_id=envelope.target_agent_id,
            )
            return FeedbackReceiveResult(
                valid=False,
                ack_allowed=False,
                outcome="feedback_rejected_invalid",
                raw_feedback_record=raw_feedback_record,
                errors=validation_errors,
                envelope=envelope,
                intake_record=terminal.intake_record,
                broker_action=terminal.broker_action,
                failure_class=terminal.failure_class,
            )

        validation, decision = self.hitl_lifecycle.normalize_feedback(
            feedback_payload=payload_contract,
            workflow_instance_id=stored_wait.workflow_instance_id,
            checkpoint_id=stored_wait.checkpoint_id,
            gate_id=stored_wait.gate_id,
            checkpoint_class="mandatory_authority",
            scope_boundary=stored_wait.gate_id,
        )
        if not validation.valid or decision is None:
            terminal = self._record_terminal_intake_failure(
                subject=subject,
                raw_inbound=envelope_dict,
                normalized_envelope=envelope.to_dict(),
                errors=validation.errors,
                failure_class="IF-08",
                failure_subclass="invalid_hitl_callback",
                broker_action="REJECT",
                terminal_outcome="terminal",
                anomaly_code="authority_stall",
                abnormal_error_class="authority_unresolved",
                workflow_instance_id=envelope.workflow_instance_id,
                message_id=envelope.message_id,
                causation_id=envelope.causation_id,
                correlation_id=envelope.correlation_id,
                source_agent_id=envelope.source_agent_id,
                target_agent_id=envelope.target_agent_id,
            )
            return FeedbackReceiveResult(
                valid=False,
                ack_allowed=False,
                outcome="feedback_rejected_invalid",
                raw_feedback_record=raw_feedback_record,
                errors=validation.errors,
                envelope=envelope,
                intake_record=terminal.intake_record,
                broker_action=terminal.broker_action,
                failure_class=terminal.failure_class,
            )

        self.state_store.record_envelope_inbox(
            envelope_id=envelope.message_id,
            subject=subject,
            payload=envelope.to_dict(),
            normalized_execution_envelope=envelope.to_dict(),
            message_id=envelope.message_id,
            workflow_instance_id=envelope.workflow_instance_id,
            causation_id=envelope.causation_id,
            correlation_id=envelope.correlation_id,
            source_agent_id=envelope.source_agent_id,
            target_agent_id=envelope.target_agent_id,
        )
        phase3_managed = (stored_wait.payload or {}).get("publication_status") == "published"
        if phase3_managed:
            wait.status = "feedback_received"
            self._persist_authority_wait_state(wait)
        normalized_store_record = self.state_store.create_hitl_decision_record(
            decision_id=decision.decision_id,
            authority_wait_id=decision.authority_wait_id,
            workflow_instance_id=decision.workflow_instance_id,
            checkpoint_id=decision.checkpoint_id,
            linked_gate_id=decision.linked_gate_id,
            decision_type=decision.decision_type,
            decision_value=decision.decision_value,
            responding_actor_id=decision.responding_actor_id,
            responding_actor_role=decision.responding_actor_role,
            state_transition_allowed=decision.state_transition_allowed,
            validation_status=decision.validation_status,
            created_at=decision.created_at,
            payload=asdict(decision),
        )
        normalized_decision_record = self.state_store.create_phase3_runtime_record(
            record_type="normalized_decision_record",
            workflow_instance_id=decision.workflow_instance_id,
            authority_wait_id=decision.authority_wait_id,
            related_message_id=envelope.message_id,
            dedupe_key=duplicate_key,
            status="validated",
            payload={
                "decision_id": decision.decision_id,
                "decision_payload": asdict(decision),
                "feedback_id": payload_contract.feedback_id,
                "state_transition_allowed": decision.state_transition_allowed,
            },
        )
        if not phase3_managed:
            self._persist_authority_wait_state(wait)
            self.state_store.complete_envelope_inbox(envelope.message_id)
            return FeedbackReceiveResult(
                valid=True,
                ack_allowed=True,
                decision=decision,
                authority_wait=self._require_wait(wait.authority_wait_id),
                outcome="feedback_accepted",
                raw_feedback_record=raw_feedback_record,
                normalized_decision_record=normalized_decision_record,
                envelope=envelope,
                broker_action="ACK",
            )

        wait.status = "validated"
        self._persist_authority_wait_state(wait)

        resume_request_record = None
        close_reason = "decision_recorded"
        if decision.state_transition_allowed:
            resume_request_record = self.state_store.create_phase3_runtime_record(
                record_type="bounded_resume_request_record",
                workflow_instance_id=decision.workflow_instance_id,
                authority_wait_id=decision.authority_wait_id,
                related_message_id=envelope.message_id,
                dedupe_key=decision.decision_id,
                status="resumed",
                payload={
                    "decision_id": decision.decision_id,
                    "resume_from_ref": (stored_wait.payload or {}).get("resume_from_ref"),
                    "gate_id": stored_wait.gate_id,
                    "checkpoint_id": stored_wait.checkpoint_id,
                },
            )
            wait.status = "resumed"
            close_reason = "accepted_feedback"

        wait.status = "closed"
        wait.resolved_at = datetime.now(UTC).isoformat()
        self._persist_authority_wait_state(wait)
        self.state_store.create_phase3_runtime_record(
            record_type="wait_closure_record",
            workflow_instance_id=decision.workflow_instance_id,
            authority_wait_id=decision.authority_wait_id,
            related_message_id=envelope.message_id,
            dedupe_key=decision.decision_id,
            status="closed",
            payload={
                "decision_id": decision.decision_id,
                "close_reason": close_reason,
            },
        )
        self.state_store.complete_envelope_inbox(envelope.message_id)
        return FeedbackReceiveResult(
            valid=True,
            ack_allowed=True,
            decision=decision,
            authority_wait=self._require_wait(wait.authority_wait_id),
            outcome="feedback_accepted",
            raw_feedback_record=raw_feedback_record,
            normalized_decision_record=normalized_decision_record,
            resume_request_record=resume_request_record,
            envelope=envelope,
            broker_action="ACK",
        )

    def record_timeout_dispatch_evidence(self, envelope: ExecutionMessageEnvelope) -> Any:
        return self.state_store.create_phase3_runtime_record(
            record_type="timeout_dispatch_evidence_record",
            workflow_instance_id=envelope.workflow_instance_id,
            authority_wait_id=envelope.correlation_id,
            related_message_id=envelope.message_id,
            dedupe_key=envelope.message_id,
            status="timeout_recorded",
            payload=envelope.to_dict(),
        )

    def record_retry_dispatch_evidence(self, envelope: ExecutionMessageEnvelope) -> Any:
        return self.state_store.create_phase3_runtime_record(
            record_type="retry_dispatch_evidence_record",
            workflow_instance_id=envelope.workflow_instance_id,
            authority_wait_id=envelope.correlation_id,
            related_message_id=envelope.message_id,
            dedupe_key=envelope.message_id,
            status="retry_recorded",
            payload=envelope.to_dict(),
        )

    def record_dead_letter_dispatch_evidence(self, envelope: ExecutionMessageEnvelope) -> Any:
        return self.state_store.create_phase3_runtime_record(
            record_type="dead_letter_dispatch_evidence_record",
            workflow_instance_id=envelope.workflow_instance_id,
            authority_wait_id=envelope.correlation_id,
            related_message_id=envelope.message_id,
            dedupe_key=envelope.message_id,
            status="dead_letter_recorded",
            payload=envelope.to_dict(),
        )

    def scan_timeouts(self, now_at: Optional[str] = None) -> TimeoutScanResult:
        now_at = now_at or datetime.now(UTC).isoformat()
        overdue_tasks = self.state_store.list_overdue_pending_tasks(now_at=now_at)
        waiting_callbacks = self.state_store.list_waiting_callbacks()
        overdue_waits = self.state_store.list_overdue_authority_wait_states(now_at=now_at)
        task_timeouts: list[Any] = []
        callback_timeouts: list[Any] = []
        authority_wait_timeouts: list[Any] = []

        for task in overdue_tasks:
            reason = self._task_timeout_reason(task, now_at)
            task_timeouts.append(
                build_protocol_envelope(
                    message_type="timeout",
                    source_agent_id=self.agent_id,
                    source_runtime_instance_id=self._runtime_instance_id,
                    source_role=self.role,
                    authority_scope="workflow.timeout",
                    payload=_summarize_timeout_payload(
                        record_type="pending_task",
                        record_id=task.task_id,
                        reason=reason,
                        context={
                            "subject": task.subject,
                            "correlation_id": task.correlation_id,
                            "workflow_id": task.workflow_id,
                        },
                    ),
                    correlation_id=task.correlation_id,
                    causation_id=task.task_id,
                )
            )

        for wait in waiting_callbacks:
            if self._callback_is_overdue(wait, now_at):
                callback_timeouts.append(
                    build_protocol_envelope(
                        message_type="timeout",
                        source_agent_id=self.agent_id,
                        source_runtime_instance_id=self._runtime_instance_id,
                        source_role=self.role,
                        authority_scope="workflow.timeout",
                        payload=_summarize_timeout_payload(
                            record_type="callback_wait",
                            record_id=wait.callback_id,
                            reason=self._callback_timeout_reason(wait, now_at),
                            context={
                                "expected_subject": wait.expected_subject,
                                "request_message_id": wait.request_message_id,
                                "task_id": wait.task_id,
                            },
                        ),
                        correlation_id=wait.correlation_id,
                        causation_id=wait.request_message_id,
                    )
                )

        for stored_wait in overdue_waits:
            wait = self._load_wait_from_store(stored_wait)
            wait, decision, abnormal = self.hitl_lifecycle.handle_no_response_timeout(wait.authority_wait_id)
            wait.status = "timed_out"
            self.state_store.create_hitl_decision_record(
                decision_id=decision.decision_id,
                authority_wait_id=decision.authority_wait_id,
                workflow_instance_id=decision.workflow_instance_id,
                checkpoint_id=decision.checkpoint_id,
                linked_gate_id=decision.linked_gate_id,
                decision_type=decision.decision_type,
                decision_value=decision.decision_value,
                responding_actor_id=decision.responding_actor_id,
                responding_actor_role=decision.responding_actor_role,
                state_transition_allowed=decision.state_transition_allowed,
                validation_status=decision.validation_status,
                created_at=decision.created_at,
                payload=asdict(decision),
            )
            if wait.due_at:
                timer = self.state_store.create_escalation_timer(
                    escalation_timer_id=f"esc-{wait.authority_wait_id}",
                    workflow_instance_id=wait.workflow_instance_id,
                    trigger_type="authority_wait_timeout",
                    due_at=wait.due_at,
                    status="triggered",
                    created_at=now_at,
                    payload={"authority_wait_id": wait.authority_wait_id},
                )
                abnormal.escalation_timer_id = timer.escalation_timer_id
            self.state_store.create_abnormal_state_record(
                abnormal_state_id=abnormal.abnormal_state_id,
                error_event_id=abnormal.error_event_id,
                workflow_instance_id=abnormal.workflow_instance_id,
                error_class=abnormal.error_class,
                abnormal_class=abnormal.abnormal_class,
                resolved=abnormal.resolved,
                notification_sent=abnormal.notification_sent,
                resolution_record_id=abnormal.resolution_record_id,
                escalation_timer_id=abnormal.escalation_timer_id,
                detected_at=abnormal.detected_at,
                resolved_at=abnormal.resolved_at,
                payload=asdict(abnormal),
            )
            self._persist_authority_wait_state(wait)
            timeout_payload = TimeoutMessagePayload(
                timeout_id=f"timeout-{wait.authority_wait_id}",
                related_message_id=stored_wait.review_task_message_id or wait.authority_wait_id,
                timeout_scope="authority_wait",
                reason="AUTHORITY_WAIT_DUE_AT_EXCEEDED",
                detected_at=abnormal.detected_at,
                context={
                    "authority_wait_id": wait.authority_wait_id,
                    "abnormal_state_id": abnormal.abnormal_state_id,
                    "decision_id": decision.decision_id,
                },
            )
            timeout_envelope = build_execution_envelope(
                message_type="Timeout_Message",
                workflow_instance_id=wait.workflow_instance_id,
                workflow_type="hitl",
                workflow_version="0.3",
                producer=self.agent_id,
                payload=timeout_payload,
                correlation_id=wait.authority_wait_id,
                causation_id=stored_wait.review_task_message_id or wait.authority_wait_id,
                source_agent_id=self.agent_id,
                source_runtime_instance_id=self._runtime_instance_id,
                source_role=self.role,
                authority_scope="workflow.timeout",
                target_agent_id=self.agent_id,
            )
            self.record_timeout_dispatch_evidence(timeout_envelope)
            authority_wait_timeouts.append(timeout_envelope)

        return TimeoutScanResult(
            task_timeout_envelopes=task_timeouts,
            callback_timeout_envelopes=callback_timeouts,
            authority_wait_timeout_envelopes=authority_wait_timeouts,
        )

    def resolve_abnormal_state(
        self,
        abnormal_state_id: str,
        resolved_by: str,
        resolution_action: str,
        evidence_refs: Optional[list[str]] = None,
        state_transition_id: Optional[str] = None,
    ) -> ResolutionRecord:
        current = next(
            (state for state in self.state_store.list_unresolved_abnormal_states() if state.abnormal_state_id == abnormal_state_id),
            None,
        )
        if current is None:
            raise KeyError(f"abnormal_state not found: {abnormal_state_id}")
        abnormal = AbnormalStateRecord(**current.payload)
        abnormal, resolution = resolve_abnormal_state(
            state=abnormal,
            resolved_by=resolved_by,
            resolution_action=resolution_action,
            workflow_instance_id=abnormal.workflow_instance_id or "",
            evidence_refs=evidence_refs,
            state_transition_id=state_transition_id,
        )
        self.state_store.create_resolution_record(
            resolution_id=resolution.resolution_id,
            abnormal_state_id=resolution.abnormal_state_id,
            error_event_id=resolution.error_event_id,
            workflow_instance_id=resolution.workflow_instance_id,
            resolved_by=resolution.resolved_by,
            resolution_action=resolution.resolution_action,
            created_at=resolution.created_at,
            payload=asdict(resolution),
        )
        self.state_store.create_abnormal_state_record(
            abnormal_state_id=abnormal.abnormal_state_id,
            error_event_id=abnormal.error_event_id,
            workflow_instance_id=abnormal.workflow_instance_id,
            error_class=abnormal.error_class,
            abnormal_class=abnormal.abnormal_class,
            resolved=abnormal.resolved,
            notification_sent=abnormal.notification_sent,
            resolution_record_id=abnormal.resolution_record_id,
            escalation_timer_id=abnormal.escalation_timer_id,
            detected_at=abnormal.detected_at,
            resolved_at=abnormal.resolved_at,
            payload=asdict(abnormal),
        )
        return resolution

    def timeout_subject(self) -> str:
        return build_ops_timeout_subject()

    def mark_intake_handler_running(self, envelope_id: str):
        return self.state_store.mark_envelope_inbox_handler_running(envelope_id)

    def record_post_ack_handler_failure(self, envelope_id: str, error: str):
        record = self.state_store.mark_envelope_inbox_handler_failure(envelope_id, error)
        if record.handler_exhausted and not record.abnormal_state_id:
            abnormal = classify_abnormal_state(
                error_event_id=f"IF-09:{envelope_id}",
                error_class="mechanism_stall",
                workflow_instance_id=record.workflow_instance_id,
            )
            self.state_store.create_abnormal_state_record(
                abnormal_state_id=abnormal.abnormal_state_id,
                error_event_id=abnormal.error_event_id,
                workflow_instance_id=abnormal.workflow_instance_id,
                error_class=abnormal.error_class,
                abnormal_class=abnormal.abnormal_class,
                resolved=abnormal.resolved,
                notification_sent=abnormal.notification_sent,
                resolution_record_id=abnormal.resolution_record_id,
                escalation_timer_id=abnormal.escalation_timer_id,
                detected_at=abnormal.detected_at,
                resolved_at=abnormal.resolved_at,
                payload=asdict(abnormal),
            )
            record = self.state_store.update_envelope_inbox_abnormal_state(
                envelope_id=envelope_id,
                abnormal_state_id=abnormal.abnormal_state_id,
            )
        return record

    def list_local_recovery_candidates(self):
        return self.state_store.list_envelope_inbox_for_local_recovery()

    def record_retryable_if04_exhaustion(self, envelope_id: str, workflow_instance_id: Optional[str], reason: str):
        abnormal = classify_abnormal_state(
            error_event_id=f"IF-04-EXHAUSTED:{envelope_id}",
            error_class="mechanism_stall",
            workflow_instance_id=workflow_instance_id,
        )
        self.state_store.create_abnormal_state_record(
            abnormal_state_id=abnormal.abnormal_state_id,
            error_event_id=abnormal.error_event_id,
            workflow_instance_id=abnormal.workflow_instance_id,
            error_class=abnormal.error_class,
            abnormal_class=abnormal.abnormal_class,
            resolved=abnormal.resolved,
            notification_sent=abnormal.notification_sent,
            resolution_record_id=abnormal.resolution_record_id,
            escalation_timer_id=abnormal.escalation_timer_id,
            detected_at=abnormal.detected_at,
            resolved_at=abnormal.resolved_at,
            payload=asdict(abnormal),
        )
        return self.state_store.mark_envelope_inbox_retry_exhausted(
            envelope_id=envelope_id,
            error=reason,
            abnormal_state_id=abnormal.abnormal_state_id,
        )

    def _intake_protocol_message(self, subject: str, envelope_dict: dict) -> RuntimeIntakeResult:
        envelope = ProtocolEnvelope.from_dict(envelope_dict)
        temporal_errors = self._validate_protocol_temporal_prerequisites(envelope)
        if temporal_errors:
            broker_action = self._broker_action_for_expired_subject(subject, None)
            terminal = self._record_terminal_intake_failure(
                subject=subject,
                raw_inbound=envelope_dict,
                normalized_envelope=envelope.to_dict(),
                errors=temporal_errors,
                failure_class="IF-04",
                failure_subclass="expired_message",
                broker_action=broker_action,
                terminal_outcome="retry" if broker_action == "NAK" else "terminal",
                anomaly_code=None if broker_action == "NAK" else self._anomaly_code_for_expiry(subject, None),
                workflow_instance_id=envelope_dict.get("workflow_instance_id"),
                message_id=envelope.message_id,
                causation_id=envelope.causation_id,
                correlation_id=envelope.correlation_id,
                source_agent_id=envelope.source_agent_id,
                target_agent_id=envelope.target_agent_id,
            )
            return RuntimeIntakeResult(
                valid=False,
                ack_allowed=False,
                errors=temporal_errors,
                envelope=envelope,
                intake_record=terminal.intake_record,
                broker_action=terminal.broker_action,
                failure_class=terminal.failure_class,
            )
        validation = self.boundary.validate_inbound_for_consumer(
            consumer_agent_id=self.agent_id,
            subject=subject,
            envelope_dict=envelope_dict,
        )
        if not validation.valid or validation.envelope is None:
            failure_class = "IF-04" if any(error == "MESSAGE_EXPIRED" for error in validation.errors) else (
                "IF-03" if self._is_authority_scope_mismatch(validation.errors) else "IF-02"
            )
            broker_action = self._broker_action_for_expired_subject(subject, None) if failure_class == "IF-04" else "REJECT"
            anomaly_code = None if broker_action == "NAK" else (
                "authority_stall" if failure_class == "IF-03" else ("schema_invalid" if failure_class == "IF-02" else self._anomaly_code_for_expiry(subject, None))
            )
            terminal = self._record_terminal_intake_failure(
                subject=subject,
                raw_inbound=envelope_dict,
                normalized_envelope=validation.envelope.to_dict() if validation.envelope is not None else None,
                errors=validation.errors,
                failure_class=failure_class,
                failure_subclass=(
                    "expired_message"
                    if failure_class == "IF-04"
                    else ("authority_scope_mismatch" if failure_class == "IF-03" else "schema_validation_failure")
                ),
                broker_action=broker_action,
                terminal_outcome="retry" if broker_action == "NAK" else "terminal",
                anomaly_code=anomaly_code,
                abnormal_error_class="authority_unresolved" if failure_class == "IF-03" else None,
                workflow_instance_id=envelope_dict.get("workflow_instance_id"),
                message_id=envelope_dict.get("message_id"),
                causation_id=envelope_dict.get("causation_id"),
                correlation_id=envelope_dict.get("correlation_id"),
                source_agent_id=envelope_dict.get("source_agent_id"),
                target_agent_id=envelope_dict.get("target_agent_id"),
            )
            return RuntimeIntakeResult(
                valid=False,
                ack_allowed=False,
                errors=validation.errors,
                envelope=validation.envelope,
                intake_record=terminal.intake_record,
                broker_action=terminal.broker_action,
                failure_class=terminal.failure_class,
            )
        envelope = validation.envelope
        existing = self.state_store.get_idempotency(envelope.idempotency_key)
        if existing is not None:
            return RuntimeIntakeResult(
                valid=True,
                ack_allowed=True,
                duplicate=True,
                envelope=envelope,
                broker_action="REJECT",
                failure_class="IF-06",
                existing_result=existing.result_detail,
            )

        intake_record = self.state_store.record_envelope_inbox(
            envelope_id=envelope.message_id,
            subject=subject,
            payload=envelope.to_dict(),
            normalized_execution_envelope=envelope.to_dict(),
            message_id=envelope.message_id,
            workflow_instance_id=envelope.correlation_id,
            causation_id=envelope.causation_id,
            correlation_id=envelope.correlation_id,
            source_agent_id=envelope.source_agent_id,
            target_agent_id=envelope.target_agent_id,
        )
        pending_task = self.state_store.create_pending_task(
            task_id=f"task-{envelope.message_id}",
            task_type=envelope.message_type,
            subject=subject,
            correlation_id=envelope.correlation_id,
            workflow_id=envelope.correlation_id,
            payload=envelope.payload,
            reply_to_subject=envelope.reply_to_subject,
            created_by=self.runtime_id,
            deadline_at=envelope.expires_at,
        )
        return RuntimeIntakeResult(
            valid=True,
            ack_allowed=True,
            duplicate=False,
            pending_task=pending_task,
            envelope=envelope,
            intake_record=intake_record,
            broker_action="ACK",
        )

    def _receive_protocol_callback(self, subject: str, envelope_dict: dict) -> CallbackReceiveResult:
        envelope = ProtocolEnvelope.from_dict(envelope_dict)
        temporal_errors = self._validate_protocol_temporal_prerequisites(envelope)
        if temporal_errors:
            broker_action = self._broker_action_for_expired_subject(subject, None)
            terminal = self._record_terminal_intake_failure(
                subject=subject,
                raw_inbound=envelope_dict,
                normalized_envelope=envelope.to_dict(),
                errors=temporal_errors,
                failure_class="IF-04",
                failure_subclass="expired_callback",
                broker_action=broker_action,
                terminal_outcome="retry" if broker_action == "NAK" else "terminal",
                anomaly_code=None if broker_action == "NAK" else self._anomaly_code_for_expiry(subject, None),
                workflow_instance_id=envelope_dict.get("workflow_instance_id"),
                message_id=envelope.message_id,
                causation_id=envelope.causation_id,
                correlation_id=envelope.correlation_id,
                source_agent_id=envelope.source_agent_id,
                target_agent_id=envelope.target_agent_id,
            )
            return CallbackReceiveResult(
                valid=False,
                ack_allowed=False,
                matched=False,
                errors=temporal_errors,
                envelope=envelope,
                intake_record=terminal.intake_record,
                broker_action=terminal.broker_action,
                failure_class=terminal.failure_class,
            )
        validation = self.boundary.validate_inbound_for_consumer(
            consumer_agent_id=self.agent_id,
            subject=subject,
            envelope_dict=envelope_dict,
        )
        if not validation.valid or validation.envelope is None:
            failure_class = "IF-04" if any(error == "MESSAGE_EXPIRED" for error in validation.errors) else (
                "IF-03" if self._is_authority_scope_mismatch(validation.errors) else "IF-02"
            )
            broker_action = self._broker_action_for_expired_subject(subject, None) if failure_class == "IF-04" else "REJECT"
            terminal = self._record_terminal_intake_failure(
                subject=subject,
                raw_inbound=envelope_dict,
                normalized_envelope=validation.envelope.to_dict() if validation.envelope is not None else None,
                errors=validation.errors,
                failure_class=failure_class,
                failure_subclass=(
                    "expired_callback"
                    if failure_class == "IF-04"
                    else ("authority_scope_mismatch" if failure_class == "IF-03" else "schema_validation_failure")
                ),
                broker_action=broker_action,
                terminal_outcome="retry" if broker_action == "NAK" else "terminal",
                anomaly_code=None if broker_action == "NAK" else (
                    "authority_stall" if failure_class == "IF-03" else ("schema_invalid" if failure_class == "IF-02" else self._anomaly_code_for_expiry(subject, None))
                ),
                abnormal_error_class="authority_unresolved" if failure_class == "IF-03" else None,
                workflow_instance_id=envelope_dict.get("workflow_instance_id"),
                message_id=envelope_dict.get("message_id"),
                causation_id=envelope_dict.get("causation_id"),
                correlation_id=envelope_dict.get("correlation_id"),
                source_agent_id=envelope_dict.get("source_agent_id"),
                target_agent_id=envelope_dict.get("target_agent_id"),
            )
            return CallbackReceiveResult(
                valid=False,
                ack_allowed=False,
                matched=False,
                errors=validation.errors,
                envelope=validation.envelope,
                intake_record=terminal.intake_record,
                broker_action=terminal.broker_action,
                failure_class=terminal.failure_class,
            )

        envelope = validation.envelope
        waits = self.state_store.list_waiting_callbacks()
        match = next(
            (
                wait
                for wait in waits
                if wait.correlation_id == envelope.correlation_id
                and wait.request_message_id == envelope.causation_id
                and wait.expected_subject == subject
                and wait.expected_source_agent_id == envelope.source_agent_id
            ),
            None,
        )
        if match is None:
            terminal = self._record_terminal_intake_failure(
                subject=subject,
                raw_inbound=envelope_dict,
                normalized_envelope=envelope.to_dict(),
                errors=[f"ORPHAN_CALLBACK: {envelope.message_id}"],
                failure_class="IF-07",
                failure_subclass="unknown_correlation_causation",
                broker_action="REJECT",
                terminal_outcome="terminal",
                anomaly_code="other",
                abnormal_error_class="other",
                workflow_instance_id=envelope_dict.get("workflow_instance_id"),
                message_id=envelope.message_id,
                causation_id=envelope.causation_id,
                correlation_id=envelope.correlation_id,
                source_agent_id=envelope.source_agent_id,
                target_agent_id=envelope.target_agent_id,
            )
            return CallbackReceiveResult(
                valid=False,
                ack_allowed=False,
                matched=False,
                errors=[f"ORPHAN_CALLBACK: {envelope.message_id}"],
                envelope=envelope,
                intake_record=terminal.intake_record,
                broker_action=terminal.broker_action,
                failure_class=terminal.failure_class,
            )

        self.state_store.record_envelope_inbox(
            envelope_id=envelope.message_id,
            subject=subject,
            payload=envelope.to_dict(),
            normalized_execution_envelope=envelope.to_dict(),
            message_id=envelope.message_id,
            workflow_instance_id=envelope_dict.get("workflow_instance_id"),
            causation_id=envelope.causation_id,
            correlation_id=envelope.correlation_id,
            source_agent_id=envelope.source_agent_id,
            target_agent_id=envelope.target_agent_id,
        )
        completed = self.state_store.complete_callback_wait(
            callback_id=match.callback_id,
            response_payload=envelope.to_dict(),
        )
        self.state_store.complete_envelope_inbox(envelope.message_id)
        return CallbackReceiveResult(
            valid=True,
            ack_allowed=True,
            matched=True,
            callback_wait=completed,
            envelope=envelope,
            broker_action="ACK",
        )

    def _intake_execution_message(self, subject: str, envelope_dict: dict) -> RuntimeIntakeResult:
        contract = validate_execution_message(envelope_dict, require_runtime_overlay=True)
        envelope = ExecutionMessageEnvelope.from_dict(envelope_dict)
        errors = list(contract.errors)

        if contract.valid and not is_transport_active(envelope.message_type):
            errors.append(f"DEFERRED_TRANSPORT_INACTIVE: {envelope.message_type}")

        if contract.valid:
            errors.extend(self._validate_execution_runtime_boundary(subject, envelope))
            errors.extend(self._validate_temporal_prerequisites(envelope))

        if errors:
            failure_class, failure_subclass, broker_action, terminal_outcome, anomaly_code, abnormal_error_class = (
                self._classify_execution_intake_failure(subject, envelope, errors)
            )
            terminal = self._record_terminal_intake_failure(
                subject=subject,
                raw_inbound=envelope_dict,
                normalized_envelope=envelope.to_dict(),
                errors=errors,
                failure_class=failure_class,
                failure_subclass=failure_subclass,
                broker_action=broker_action,
                terminal_outcome=terminal_outcome,
                anomaly_code=anomaly_code,
                abnormal_error_class=abnormal_error_class,
                workflow_instance_id=envelope.workflow_instance_id,
                message_id=envelope.message_id,
                causation_id=envelope.causation_id,
                correlation_id=envelope.correlation_id,
                source_agent_id=envelope.source_agent_id,
                target_agent_id=envelope.target_agent_id,
            )
            return RuntimeIntakeResult(
                valid=False,
                ack_allowed=False,
                errors=errors,
                envelope=envelope,
                intake_record=terminal.intake_record,
                broker_action=terminal.broker_action,
                failure_class=terminal.failure_class,
            )

        existing = self.state_store.get_idempotency(envelope.idempotency_key)
        if existing is not None:
            return RuntimeIntakeResult(
                valid=True,
                ack_allowed=True,
                duplicate=True,
                envelope=envelope,
                broker_action="REJECT",
                failure_class="IF-06",
                existing_result=existing.result_detail,
            )

        intake_record = self.state_store.record_envelope_inbox(
            envelope_id=envelope.message_id,
            subject=subject,
            payload=envelope.to_dict(),
            normalized_execution_envelope=envelope.to_dict(),
            message_id=envelope.message_id,
            workflow_instance_id=envelope.workflow_instance_id,
            causation_id=envelope.causation_id,
            correlation_id=envelope.correlation_id,
            source_agent_id=envelope.source_agent_id,
            target_agent_id=envelope.target_agent_id,
        )
        pending_task = self.state_store.create_pending_task(
            task_id=f"task-{envelope.message_id}",
            task_type=envelope.message_type,
            subject=subject,
            correlation_id=envelope.correlation_id,
            workflow_id=envelope.workflow_instance_id,
            payload=envelope.to_dict(),
            reply_to_subject=envelope.reply_to_subject,
            created_by=self.runtime_id,
            first_response_deadline=envelope.available_at or envelope.expires_at,
            completion_deadline=envelope.expires_at,
            priority=self._priority_to_int(envelope.priority),
        )
        return RuntimeIntakeResult(
            valid=True,
            ack_allowed=True,
            duplicate=False,
            pending_task=pending_task,
            envelope=envelope,
            intake_record=intake_record,
            broker_action="ACK",
        )

    def _validate_execution_runtime_boundary(
        self,
        subject: str,
        envelope: ExecutionMessageEnvelope,
    ) -> list[str]:
        errors: list[str] = []
        consumer = self.identity_store.get_agent(self.agent_id)
        if consumer is None:
            return [f"UNKNOWN_CONSUMER: {self.agent_id}"]
        if not any(subject.startswith(prefix) for prefix in consumer.trusted_subject_prefixes):
            errors.append(f"UNTRUSTED_SUBJECT: {subject}")

        sender = self.identity_store.validate_sender(
            source_agent_id=envelope.source_agent_id or "",
            source_role=envelope.source_role or "",
            authority_scope=envelope.authority_scope or "",
        )
        errors.extend(sender.errors)

        target = self.identity_store.validate_target_for_consumer(
            consumer_agent_id=self.agent_id,
            target_agent_id=envelope.target_agent_id,
        )
        errors.extend(target.errors)

        routed = route_execution_envelope_dict(envelope.to_dict())
        if routed.valid and routed.subject != subject:
            errors.append(f"SUBJECT_ROUTE_MISMATCH: expected {routed.subject}, got {subject}")
        elif not routed.valid:
            errors.extend(routed.errors or [])

        return errors

    def _classify_execution_intake_failure(
        self,
        subject: str,
        envelope: ExecutionMessageEnvelope,
        errors: list[str],
    ) -> tuple[str, str, str, str, Optional[str], Optional[str]]:
        if any(error == "MESSAGE_EXPIRED" for error in errors):
            broker_action = self._broker_action_for_expired_subject(subject, envelope.message_type)
            return (
                "IF-04",
                "expired_message",
                broker_action,
                "retry" if broker_action == "NAK" else "terminal",
                None if broker_action == "NAK" else self._anomaly_code_for_expiry(subject, envelope.message_type),
                None,
            )
        if any(error.startswith("DEFERRED_TRANSPORT_INACTIVE") for error in errors):
            return ("IF-05", "deferred_transport_inactive", "REJECT", "terminal", "other", None)
        if self._is_authority_scope_mismatch(errors):
            return ("IF-03", "authority_scope_mismatch", "REJECT", "terminal", "authority_stall", "authority_unresolved")
        return ("IF-02", "schema_validation_failure", "REJECT", "terminal", "schema_invalid", None)

    def _record_terminal_intake_failure(
        self,
        *,
        subject: str,
        raw_inbound: Any,
        errors: list[str],
        failure_class: str,
        failure_subclass: str,
        broker_action: str,
        terminal_outcome: str,
        anomaly_code: Optional[str],
        normalized_envelope: Optional[dict] = None,
        abnormal_error_class: Optional[str] = None,
        workflow_instance_id: Optional[str] = None,
        message_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        source_agent_id: Optional[str] = None,
        target_agent_id: Optional[str] = None,
    ) -> RuntimeIntakeResult:
        envelope_id = message_id or f"terminal-{uuid.uuid4().hex[:12]}"
        anomaly_id = f"anomaly-{uuid.uuid4().hex[:12]}" if anomaly_code else None
        abnormal_state_id = None
        if abnormal_error_class:
            abnormal = classify_abnormal_state(
                error_event_id=f"{failure_class}:{envelope_id}",
                error_class=abnormal_error_class,
                workflow_instance_id=workflow_instance_id,
            )
            self.state_store.create_abnormal_state_record(
                abnormal_state_id=abnormal.abnormal_state_id,
                error_event_id=abnormal.error_event_id,
                workflow_instance_id=abnormal.workflow_instance_id,
                error_class=abnormal.error_class,
                abnormal_class=abnormal.abnormal_class,
                resolved=abnormal.resolved,
                notification_sent=abnormal.notification_sent,
                resolution_record_id=abnormal.resolution_record_id,
                escalation_timer_id=abnormal.escalation_timer_id,
                detected_at=abnormal.detected_at,
                resolved_at=abnormal.resolved_at,
                payload=asdict(abnormal),
            )
            abnormal_state_id = abnormal.abnormal_state_id

        intake_record = self.state_store.record_envelope_inbox(
            envelope_id=envelope_id,
            subject=subject,
            payload=raw_inbound,
            normalized_execution_envelope=normalized_envelope,
            validation_errors=errors,
            failure_class=failure_class,
            failure_subclass=failure_subclass,
            broker_action=broker_action,
            terminal_outcome=terminal_outcome,
            anomaly_id=anomaly_id,
            abnormal_state_id=abnormal_state_id,
            workflow_instance_id=workflow_instance_id,
            message_id=message_id,
            causation_id=causation_id,
            correlation_id=correlation_id,
            source_agent_id=source_agent_id,
            target_agent_id=target_agent_id,
            state="failed" if broker_action in {"REJECT", "TERM"} else "processing",
            error="; ".join(errors) if errors else None,
        )
        if broker_action in {"REJECT", "TERM"}:
            intake_record = self.state_store.complete_envelope_inbox(
                envelope_id=intake_record.envelope_id,
                state="failed",
                error="; ".join(errors) if errors else None,
            )
        return RuntimeIntakeResult(
            valid=False,
            ack_allowed=False,
            envelope=normalized_envelope,
            intake_record=intake_record,
            broker_action=broker_action,
            failure_class=failure_class,
            errors=errors,
        )

    @staticmethod
    def _is_authority_scope_mismatch(errors: list[str]) -> bool:
        return any(any(marker in error for marker in AUTHORITY_ERROR_MARKERS) for error in errors)

    @staticmethod
    def _broker_action_for_expired_subject(subject: str, message_type: Optional[str]) -> str:
        if message_type == "Feedback_Message" or subject.startswith(RETRYABLE_EXPIRY_SUBJECT_PREFIXES):
            return "NAK"
        if subject.endswith(".callbacks"):
            return "TERM"
        if subject.endswith(".inbox") or subject == "ops.anomaly":
            return "TERM"
        return "TERM"

    @staticmethod
    def _anomaly_code_for_expiry(subject: str, message_type: Optional[str]) -> Optional[str]:
        if message_type == "Feedback_Message" or subject.startswith(RETRYABLE_EXPIRY_SUBJECT_PREFIXES):
            return None
        if subject.endswith(".callbacks"):
            return "orphan_anomaly"
        if subject.endswith(".inbox"):
            return "expired_message"
        return "expired_message"

    @staticmethod
    def _validate_temporal_prerequisites(envelope: ExecutionMessageEnvelope) -> list[str]:
        errors: list[str] = []
        now_at = datetime.now(UTC)
        available_at = _parse_iso(envelope.available_at)
        expires_at = _parse_iso(envelope.expires_at)
        if available_at and available_at > now_at:
            errors.append("MESSAGE_NOT_YET_AVAILABLE")
        if expires_at and expires_at < now_at:
            errors.append("MESSAGE_EXPIRED")
        return errors

    @staticmethod
    def _validate_protocol_temporal_prerequisites(envelope: ProtocolEnvelope) -> list[str]:
        errors: list[str] = []
        now_at = datetime.now(UTC)
        expires_at = _parse_iso(envelope.expires_at)
        if expires_at and expires_at < (now_at - timedelta(seconds=1)):
            errors.append("MESSAGE_EXPIRED")
        return errors

    def _rehydrate_hitl_state(self) -> None:
        for stored in self.state_store.list_active_authority_wait_states():
            self._load_wait_from_store(stored)

    def _require_wait(self, authority_wait_id: str) -> AuthorityWaitStateV03:
        wait = self.hitl_lifecycle._waits.get(authority_wait_id)
        if wait is None:
            raise KeyError(f"authority_wait_state not loaded: {authority_wait_id}")
        return wait

    def _load_wait_from_store(self, stored_wait) -> AuthorityWaitStateV03:
        existing = self.hitl_lifecycle._waits.get(stored_wait.authority_wait_id)
        if existing is not None:
            existing.workflow_instance_id = stored_wait.workflow_instance_id
            existing.checkpoint_id = stored_wait.checkpoint_id
            existing.gate_id = stored_wait.gate_id
            existing.evidence_package_id = stored_wait.evidence_package_id
            existing.requested_actor_role = stored_wait.requested_actor_role
            existing.status = stored_wait.status
            existing.due_at = stored_wait.due_at
            existing.responded_at = stored_wait.responded_at
            existing.resolved_at = stored_wait.resolved_at
            existing.hitl_decision_id = stored_wait.hitl_decision_id
            existing.created_at = stored_wait.created_at
            existing.payload = dict(stored_wait.payload or {})
            return existing

        wait = AuthorityWaitStateV03(
            authority_wait_id=stored_wait.authority_wait_id,
            workflow_instance_id=stored_wait.workflow_instance_id,
            checkpoint_id=stored_wait.checkpoint_id,
            gate_id=stored_wait.gate_id,
            evidence_package_id=stored_wait.evidence_package_id,
            requested_actor_role=stored_wait.requested_actor_role,
            status=stored_wait.status,
            created_at=stored_wait.created_at,
            due_at=stored_wait.due_at,
            responded_at=stored_wait.responded_at,
            resolved_at=stored_wait.resolved_at,
            hitl_decision_id=stored_wait.hitl_decision_id,
        )
        wait.payload = dict(stored_wait.payload or {})
        self.hitl_lifecycle._waits[wait.authority_wait_id] = wait
        return wait

    def _persist_authority_wait_state(self, wait: AuthorityWaitStateV03) -> None:
        payload = dict(getattr(wait, "payload", {}) or {})
        self.state_store.create_authority_wait_state(
            authority_wait_id=wait.authority_wait_id,
            workflow_instance_id=wait.workflow_instance_id,
            checkpoint_id=wait.checkpoint_id,
            gate_id=wait.gate_id,
            requested_actor_role=wait.requested_actor_role,
            status=wait.status,
            review_task_message_id=payload.get("review_task_message_id"),
            evidence_package_id=wait.evidence_package_id,
            due_at=wait.due_at,
            responded_at=wait.responded_at,
            resolved_at=wait.resolved_at,
            hitl_decision_id=wait.hitl_decision_id,
            created_at=wait.created_at,
            payload=payload,
        )

    @staticmethod
    def _priority_to_int(priority: str) -> int:
        mapping = {"low": 0, "normal": 1, "high": 2, "urgent": 3}
        return mapping.get(priority, 1)

    @staticmethod
    def _task_timeout_reason(task: PendingTaskRecord, now_at: str) -> str:
        now_dt = _parse_iso(now_at)
        first_deadline = _parse_iso(task.first_response_deadline)
        completion_deadline = _parse_iso(task.completion_deadline)
        if first_deadline and now_dt and first_deadline < now_dt:
            return "FIRST_RESPONSE_DEADLINE_EXCEEDED"
        if completion_deadline and now_dt and completion_deadline < now_dt:
            return "COMPLETION_DEADLINE_EXCEEDED"
        return "TIMEOUT"

    @staticmethod
    def _callback_is_overdue(wait: CallbackWaitRecord, now_at: str) -> bool:
        now_dt = _parse_iso(now_at)
        deadlines = [
            _parse_iso(wait.deadline),
            _parse_iso(wait.first_response_deadline),
            _parse_iso(wait.completion_deadline),
        ]
        return any(deadline is not None and now_dt is not None and deadline < now_dt for deadline in deadlines)

    @staticmethod
    def _callback_timeout_reason(wait: CallbackWaitRecord, now_at: str) -> str:
        now_dt = _parse_iso(now_at)
        first_deadline = _parse_iso(wait.first_response_deadline)
        completion_deadline = _parse_iso(wait.completion_deadline)
        hard_deadline = _parse_iso(wait.deadline)
        if first_deadline and now_dt and first_deadline < now_dt:
            return "CALLBACK_FIRST_RESPONSE_DEADLINE_EXCEEDED"
        if completion_deadline and now_dt and completion_deadline < now_dt:
            return "CALLBACK_COMPLETION_DEADLINE_EXCEEDED"
        if hard_deadline and now_dt and hard_deadline < now_dt:
            return "CALLBACK_DEADLINE_EXCEEDED"
        return "CALLBACK_TIMEOUT"
