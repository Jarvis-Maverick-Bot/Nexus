"""Bounded source implementation for the Layer 3 MQ foundation daemon."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nexus.mq.ack_policy import WorkflowStateSeparator
from nexus.mq.adapter import MqAdapterStub
from nexus.mq.durable_state import DurableStateStore
from nexus.mq.foundation_daemon_config import (
    is_controlled_live_authorized,
    subject_allowed,
    validate_foundation_daemon_config,
)
from nexus.mq.foundation_daemon_evidence import FoundationEvidenceRecorder
from nexus.mq.message_contracts import validate_execution_message


@dataclass
class PublishGuardResult:
    allowed: bool
    errors: list[str] = field(default_factory=list)
    publish_attempted: bool = False
    not_business_completion: bool = True


@dataclass
class IntakeResult:
    accepted: bool
    duplicate: bool
    action: str
    ack: dict[str, Any] | None
    evidence_ref: str | None
    progress_state: str | None = None
    errors: list[str] = field(default_factory=list)
    not_business_completion: bool = True


@dataclass
class TimeoutClassification:
    action: str
    endpoint_owned_retry: bool = False
    endpoint_owned_dlq: bool = False
    record_ref: str | None = None
    not_business_completion: bool = True


class FoundationDaemonRuntime:
    """Source-only runtime surface; it does not connect to NATS or start a daemon."""

    def __init__(
        self,
        *,
        config: dict[str, Any],
        adapter: MqAdapterStub | None = None,
        state_store: DurableStateStore | None = None,
        evidence_root: str | Path = "evidence/3.5/wbs-15.9/foundation-daemon/runtime",
    ):
        self.config = config
        self.adapter = adapter or MqAdapterStub()
        self.state_store = state_store or DurableStateStore(":memory:")
        self.evidence = FoundationEvidenceRecorder(evidence_root)
        self.state_separator = WorkflowStateSeparator()

    @property
    def evidence_available(self) -> bool:
        return self.evidence.available

    @evidence_available.setter
    def evidence_available(self, value: bool) -> None:
        self.evidence.available = value

    def close(self) -> None:
        self.state_store.close()

    def validate_publish_request(self, subject: str, envelope: dict[str, Any]) -> PublishGuardResult:
        errors: list[str] = []
        validation = validate_foundation_daemon_config(self.config)
        errors.extend(validation.errors)
        allowlist = (self.config.get("subjects", {}) or {}).get("allowlist", [])
        if not subject_allowed(subject, allowlist):
            errors.append(f"SUBJECT_NOT_ALLOWED: {subject}")
        if not self.evidence_available:
            errors.append("EVIDENCE_STORE_UNAVAILABLE")
        if self.config.get("feature_flags", {}).get("live_publish_enabled") is not True:
            errors.append("LIVE_PUBLISH_NOT_ENABLED")
        contract = validate_execution_message(envelope)
        errors.extend(contract.errors)
        return PublishGuardResult(allowed=not errors, errors=list(dict.fromkeys(errors)))

    def run_controlled_live_diagnostic(self, envelope: dict[str, Any]) -> dict[str, Any]:
        subject = str(envelope.get("subject") or (self.config.get("broker", {}) or {}).get("filter_subject", ""))
        errors = self._controlled_live_diagnostic_errors(subject, envelope)
        if errors:
            return {
                "accepted": False,
                "duplicate": False,
                "action": "blocked",
                "errors": errors,
                "not_business_completion": True,
            }

        dedupe_key = str(envelope.get("idempotency_key"))
        existing = self.state_store.find_phase5_durable_record("foundation_intake", dedupe_key)
        if existing is not None:
            action = "duplicate_inflight_reconciled" if existing.status == "inflight" else "duplicate_suppressed"
            self.evidence.write_record(
                "ack",
                str(envelope.get("message_id", "unknown")),
                {
                    "subject": subject,
                    "message_id": envelope.get("message_id"),
                    "workflow_instance_id": envelope.get("workflow_instance_id"),
                    "correlation_id": envelope.get("correlation_id"),
                    "duplicate_of_record_ref": existing.record_id,
                    "duplicate_action": action,
                    "ack_level": "consumer_intake",
                    "ack_after_duplicate_evidence": True,
                    "ack_is_not_progress": True,
                    "controlled_live": True,
                    "not_business_completion": True,
                },
            )
            ack = self.adapter.ack(str(envelope.get("message_id", "")))
            return {
                "accepted": True,
                "duplicate": True,
                "action": action,
                "intake_ack": ack,
                "evidence_ref": existing.record_id,
                "not_business_completion": True,
            }

        pre_ack_evidence_ref = self.evidence.write_record(
            "intake",
            f"{envelope.get('message_id', 'unknown')}-controlled-live-pre-ack",
            {
                "subject": subject,
                "message_id": envelope.get("message_id"),
                "workflow_instance_id": envelope.get("workflow_instance_id"),
                "correlation_id": envelope.get("correlation_id"),
                "controlled_live": True,
                "ack_emitted": False,
                "ack_after_evidence_and_durable_state": True,
                "not_business_completion": True,
            },
        )
        record = self.state_store.create_phase5_durable_record(
            family="foundation_intake",
            status="controlled_live_intake_recorded",
            workflow_instance_id=envelope.get("workflow_instance_id"),
            target_ref=subject,
            dedupe_key=dedupe_key,
            payload={
                "message_id": envelope.get("message_id"),
                "subject": subject,
                "correlation_id": envelope.get("correlation_id"),
                "ack_level": "consumer_intake",
                "ack_is_not_progress": True,
                "ack_after_evidence_and_durable_state": True,
                "controlled_live": True,
                "evidence_ref": pre_ack_evidence_ref,
                "not_business_completion": True,
            },
        )

        try:
            broker_ack = self.adapter.publish(envelope)
        except Exception as exc:
            return {
                "accepted": False,
                "duplicate": False,
                "action": "publish_blocked",
                "errors": [f"CONTROLLED_LIVE_PUBLISH_FAILED: {exc}"],
                "evidence_ref": record.record_id,
                "not_business_completion": True,
            }

        intake_ack = self.adapter.ack(str(envelope.get("message_id", "")))
        ack_evidence_ref = self.evidence.write_record(
            "ack",
            str(envelope.get("message_id", "unknown")),
            {
                "subject": subject,
                "message_id": envelope.get("message_id"),
                "workflow_instance_id": envelope.get("workflow_instance_id"),
                "correlation_id": envelope.get("correlation_id"),
                "broker_ack": broker_ack,
                "intake_ack": intake_ack,
                "durable_record_ref": record.record_id,
                "pre_ack_evidence_ref": pre_ack_evidence_ref,
                "ack_is_not_progress": True,
                "ack_after_evidence_and_durable_state": True,
                "controlled_live": True,
                "not_business_completion": True,
            },
        )
        delivery = _consume_one(self.adapter)
        if delivery is None:
            return {
                "accepted": False,
                "duplicate": False,
                "action": "delivery_not_observed",
                "broker_ack": broker_ack,
                "intake_ack": intake_ack,
                "evidence_ref": record.record_id,
                "ack_evidence_ref": ack_evidence_ref,
                "errors": ["CONTROLLED_LIVE_DELIVERY_NOT_OBSERVED"],
                "not_business_completion": True,
            }

        result_candidate = {
            "result_type": "controlled_live_diagnostic",
            "message_id": envelope.get("message_id"),
            "workflow_instance_id": envelope.get("workflow_instance_id"),
            "correlation_id": envelope.get("correlation_id"),
            "subject": subject,
            "delivery_status": delivery.get("status", "delivered"),
            "not_business_completion": True,
        }
        result_evidence_ref = self.evidence.write_record(
            "result",
            str(envelope.get("message_id", "unknown")),
            {
                "result_candidate": result_candidate,
                "controlled_live": True,
                "not_business_completion": True,
            },
        )
        self.state_store.create_phase5_durable_record(
            family="foundation_result",
            status="controlled_live_result_recorded",
            workflow_instance_id=envelope.get("workflow_instance_id"),
            target_ref=subject,
            related_record_id=record.record_id,
            dedupe_key=f"result:{dedupe_key}",
            payload={
                "message_id": envelope.get("message_id"),
                "correlation_id": envelope.get("correlation_id"),
                "result_evidence_ref": result_evidence_ref,
                "not_business_completion": True,
            },
        )
        return {
            "accepted": True,
            "duplicate": False,
            "action": "controlled_live_diagnostic_result",
            "broker_ack": broker_ack,
            "intake_ack": intake_ack,
            "delivery": delivery,
            "result_candidate": result_candidate,
            "evidence_ref": record.record_id,
            "ack_evidence_ref": ack_evidence_ref,
            "result_evidence_ref": result_evidence_ref,
            "not_business_completion": True,
        }

    def _controlled_live_diagnostic_errors(self, subject: str, envelope: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        validation = validate_foundation_daemon_config(self.config)
        errors.extend(validation.errors)
        if not is_controlled_live_authorized(self.config):
            errors.append("CONTROLLED_LIVE_NOT_AUTHORIZED")
        allowlist = (self.config.get("subjects", {}) or {}).get("allowlist", [])
        if not subject_allowed(subject, allowlist):
            errors.append(f"SUBJECT_NOT_ALLOWED: {subject}")
        if not self.evidence_available:
            errors.append("EVIDENCE_STORE_UNAVAILABLE")
        contract = validate_execution_message(envelope)
        errors.extend(contract.errors)
        errors.extend(_source_intake_scope_errors(envelope))
        return list(dict.fromkeys(errors))

    def intake_message(self, subject: str, envelope: dict[str, Any]) -> IntakeResult:
        errors: list[str] = []
        allowlist = (self.config.get("subjects", {}) or {}).get("allowlist", [])
        if not subject_allowed(subject, allowlist):
            errors.append(f"SUBJECT_NOT_ALLOWED: {subject}")
        if not self.evidence_available:
            errors.append("EVIDENCE_STORE_UNAVAILABLE")
        validation = validate_execution_message(envelope)
        errors.extend(validation.errors)
        errors.extend(_source_intake_scope_errors(envelope))
        if errors:
            return IntakeResult(
                accepted=False,
                duplicate=False,
                action="rejected",
                ack=None,
                evidence_ref=None,
                errors=list(dict.fromkeys(errors)),
            )

        dedupe_key = str(envelope.get("idempotency_key"))
        existing = self.state_store.find_phase5_durable_record("foundation_intake", dedupe_key)
        if existing is not None:
            action = "duplicate_inflight_reconciled" if existing.status == "inflight" else "duplicate_suppressed"
            self.evidence.write_record(
                "ack",
                str(envelope.get("message_id", "unknown")),
                {
                    "subject": subject,
                    "message_id": envelope.get("message_id"),
                    "workflow_instance_id": envelope.get("workflow_instance_id"),
                    "ack_level": "consumer_intake",
                    "ack_pending": True,
                    "duplicate_of_record_ref": existing.record_id,
                    "duplicate_action": action,
                    "ack_is_not_progress": True,
                    "ack_after_duplicate_evidence": True,
                    "not_business_completion": True,
                },
            )
            ack = self.adapter.ack(str(envelope.get("message_id", "")))
            return IntakeResult(
                accepted=True,
                duplicate=True,
                action=action,
                ack=ack,
                evidence_ref=existing.record_id,
            )

        evidence_ref = self.evidence.write_record(
            "intake",
            f"{envelope.get('message_id', 'unknown')}-pre-ack",
            {
                "subject": subject,
                "message_id": envelope.get("message_id"),
                "workflow_instance_id": envelope.get("workflow_instance_id"),
                "ack_emitted": False,
                "ack_after_evidence_and_durable_state": True,
            },
        )
        record = self.state_store.create_phase5_durable_record(
            family="foundation_intake",
            status="intake_recorded",
            workflow_instance_id=envelope.get("workflow_instance_id"),
            target_ref=subject,
            dedupe_key=dedupe_key,
            payload={
                "message_id": envelope.get("message_id"),
                "subject": subject,
                "ack_level": "consumer_intake",
                "ack_is_not_progress": True,
                "ack_after_evidence_and_durable_state": True,
                "evidence_ref": evidence_ref,
                "not_business_completion": True,
            },
        )
        ack = self.adapter.ack(str(envelope.get("message_id", "")))
        self.evidence.write_record(
            "ack",
            str(envelope.get("message_id", "unknown")),
            {
                "subject": subject,
                "message_id": envelope.get("message_id"),
                "workflow_instance_id": envelope.get("workflow_instance_id"),
                "ack": ack,
                "durable_record_ref": record.record_id,
                "pre_ack_evidence_ref": evidence_ref,
                "ack_is_not_progress": True,
                "ack_after_evidence_and_durable_state": True,
            },
        )
        return IntakeResult(
            accepted=True,
            duplicate=False,
            action="intake_recorded",
            ack=ack,
            evidence_ref=record.record_id,
        )

    def classify_endpoint_timeout(self, envelope: dict[str, Any], *, attempt: int) -> TimeoutClassification:
        max_attempts = int((self.config.get("retry", {}) or {}).get("max_attempts", 3))
        if attempt < max_attempts:
            record = self.state_store.create_phase5_durable_record(
                family="foundation_retry",
                status="scheduled",
                workflow_instance_id=envelope.get("workflow_instance_id"),
                related_record_id=envelope.get("message_id"),
                dedupe_key=f"retry:{envelope.get('idempotency_key')}:{attempt}",
                payload={
                    "message_id": envelope.get("message_id"),
                    "attempt": attempt,
                    "endpoint_owned_retry": False,
                    "not_business_completion": True,
                },
            )
            return TimeoutClassification(action="retry_scheduled", record_ref=record.record_id)

        record = self.state_store.create_phase5_durable_record(
            family="foundation_dlq",
            status="recorded",
            workflow_instance_id=envelope.get("workflow_instance_id"),
            related_record_id=envelope.get("message_id"),
            dedupe_key=f"dlq:{envelope.get('idempotency_key')}",
            payload={
                "message_id": envelope.get("message_id"),
                "attempt": attempt,
                "endpoint_owned_dlq": False,
                "not_business_completion": True,
            },
        )
        return TimeoutClassification(action="dlq_recorded", record_ref=record.record_id)

    def recover_after_restart(self) -> dict[str, Any]:
        intake_records = self.state_store.list_phase5_durable_records(family="foundation_intake")
        return {
            "replayed_records": len(intake_records),
            "classification": "safe_replay_no_business_execution",
            "record_refs": [record.record_id for record in intake_records],
            "not_business_completion": True,
        }


def _source_intake_scope_errors(envelope: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    message_type = str(envelope.get("message_type", ""))
    workflow_type = str(envelope.get("workflow_type", "")).lower()
    payload = envelope.get("payload") or {}
    payload_values = []
    if isinstance(payload, dict):
        payload_values.extend(str(value).lower() for value in payload.values() if isinstance(value, str))
        for value in payload.get("allowed_side_effects", []) or []:
            payload_values.append(str(value).lower())

    if message_type == "Business_Message" or "business" in workflow_type:
        errors.append("BUSINESS_MESSAGE_INTAKE_OUT_OF_SCOPE")
    if any("business_dispatch" in value or "business-dispatch" in value for value in payload_values):
        errors.append("BUSINESS_DISPATCH_OUT_OF_SCOPE")
    if any(
        "private_agent" in value or "private-agent" in value or "private.agent" in value
        for value in payload_values
    ):
        errors.append("PRIVATE_AGENT_INVOCATION_OUT_OF_SCOPE")
    return errors


def _consume_one(adapter: Any) -> dict[str, Any] | None:
    try:
        return adapter.consume(timeout_ms=5000)
    except TypeError:
        return adapter.consume()
