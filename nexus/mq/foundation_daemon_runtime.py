"""Bounded source implementation for the Layer 3 MQ foundation daemon."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nexus.mq.ack_policy import WorkflowStateSeparator
from nexus.mq.adapter import MqAdapterStub
from nexus.mq.durable_state import DurableStateStore
from nexus.mq.foundation_daemon_config import subject_allowed, validate_foundation_daemon_config
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

    def intake_message(self, subject: str, envelope: dict[str, Any]) -> IntakeResult:
        errors: list[str] = []
        allowlist = (self.config.get("subjects", {}) or {}).get("allowlist", [])
        if not subject_allowed(subject, allowlist):
            errors.append(f"SUBJECT_NOT_ALLOWED: {subject}")
        validation = validate_execution_message(envelope)
        errors.extend(validation.errors)
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
            ack = self.adapter.ack(str(envelope.get("message_id", "")))
            action = "duplicate_inflight_reconciled" if existing.status == "inflight" else "duplicate_suppressed"
            return IntakeResult(
                accepted=True,
                duplicate=True,
                action=action,
                ack=ack,
                evidence_ref=existing.record_id,
            )

        ack = self.adapter.ack(str(envelope.get("message_id", "")))
        evidence_ref = self.evidence.write_record(
            "intake",
            str(envelope.get("message_id", "unknown")),
            {
                "subject": subject,
                "message_id": envelope.get("message_id"),
                "workflow_instance_id": envelope.get("workflow_instance_id"),
                "ack": ack,
                "ack_is_not_progress": True,
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
                "ack": ack,
                "ack_is_not_progress": True,
                "evidence_ref": evidence_ref,
                "not_business_completion": True,
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
