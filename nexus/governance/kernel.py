from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .errors import ErrorCode
from .schemas import CommandEnvelope, validate_command_envelope


ALLOWED_TRANSITIONS: dict[tuple[str, str], str] = {
    ("not_started", "InitializeAuthority"): "authority_initialized",
    ("authority_initialized", "MarkKernelReady"): "kernel_ready",
    ("kernel_ready", "RefreshProjectionCheckpoint"): "projection_contract_ready",
    ("projection_contract_ready", "SubmitWorkspaceInitRecord"): "initiation_ready",
    ("initiation_ready", "CreateHumanReviewTask"): "monitor_review_open",
    ("monitor_review_open", "CreateHumanReviewTask"): "monitor_review_open",
    ("monitor_review_open", "SubmitHumanDecision"): "monitor_decision_recorded",
    ("monitor_decision_recorded", "CreateHumanReviewTask"): "monitor_review_open",
    ("monitor_decision_recorded", "RecordEscalation"): "monitor_escalation_open",
    ("monitor_escalation_open", "RecordEscalation"): "monitor_escalation_open",
    ("monitor_escalation_open", "SubmitHumanDecision"): "monitor_decision_recorded",
    ("initiation_ready", "SubmitImpactControlRequest"): "impact_request_recorded",
    ("monitor_decision_recorded", "SubmitImpactControlRequest"): "impact_request_recorded",
    ("impact_request_recorded", "SubmitImpactControlRequest"): "impact_request_recorded",
    ("impact_assessment_recorded", "SubmitImpactControlRequest"): "impact_request_recorded",
    ("impact_monitor_review_requested", "SubmitImpactControlRequest"): "impact_request_recorded",
    ("impact_request_recorded", "RecordImpactAssessment"): "impact_assessment_recorded",
    ("impact_assessment_recorded", "RecordImpactAssessment"): "impact_assessment_recorded",
    ("impact_monitor_review_requested", "RecordImpactAssessment"): "impact_assessment_recorded",
    ("impact_assessment_recorded", "CreateMonitorTaskForImpact"): "impact_monitor_review_requested",
    ("impact_monitor_review_requested", "CreateMonitorTaskForImpact"): "impact_monitor_review_requested",
    ("impact_monitor_review_requested", "SubmitHumanDecision"): "monitor_decision_recorded",
    ("monitor_decision_recorded", "RecordDelivery"): "delivery_recorded",
    ("delivery_recorded", "RecordDelivery"): "delivery_recorded",
    ("delivery_recorded", "RecordFeedback"): "feedback_recorded",
    ("feedback_recorded", "RecordFeedback"): "feedback_recorded",
    ("feedback_recorded", "RequestFeedbackTriageDecision"): "feedback_triage_requested",
    ("feedback_triage_requested", "RequestFeedbackTriageDecision"): "feedback_triage_requested",
    ("feedback_triage_requested", "RecordFeedbackTriageDecision"): "feedback_triage_recorded",
    ("feedback_triage_recorded", "CreateCompletionContinuityPacket"): "completion_continuity_review_requested",
    ("completion_continuity_review_requested", "CreateCompletionContinuityPacket"): "completion_continuity_review_requested",
    ("completion_continuity_review_requested", "MediateBaselineEntry"): "baseline_entry_recorded",
    ("baseline_entry_recorded", "MediateBaselineEntry"): "baseline_entry_recorded",
}


@dataclass(frozen=True)
class AggregateState:
    aggregate_id: str = "layer1-governance"
    state: str = "not_started"
    version: int = 0
    last_record_id: str | None = None
    authority_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class KernelRecord:
    record_id: str
    aggregate_id: str
    previous_version: int
    version: int
    previous_state: str
    new_state: str
    command_type: str
    payload: dict[str, Any]
    authority_refs: tuple[str, ...]
    actor_id: str


@dataclass(frozen=True)
class TransitionResult:
    accepted: bool
    new_state: AggregateState
    error_code: ErrorCode | None = None
    record: KernelRecord | None = None
    message: str = ""

    def to_evidence(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "aggregate_id": self.new_state.aggregate_id,
            "error_code": self.error_code.value if self.error_code else None,
            "message": self.message,
            "record_id": self.record.record_id if self.record else None,
            "state": self.new_state.state,
            "version": self.new_state.version,
        }


@dataclass
class GovernanceKernel:
    state: AggregateState = field(default_factory=AggregateState)
    records: list[KernelRecord] = field(default_factory=list)
    _idempotency: dict[str, tuple[str, TransitionResult]] = field(default_factory=dict)

    def apply(self, command: CommandEnvelope) -> TransitionResult:
        validation = validate_command_envelope(command)
        if not validation.accepted:
            return self._reject(validation.error_code or ErrorCode.INVALID_TRANSITION, validation.message)

        if command.command_type == "MediateBaselineEntry" and command.payload.get("mediated_by_service") is not True:
            return self._reject(ErrorCode.NO_GO_BOUNDARY, "baseline entries must be mediated by Governance Service")

        fingerprint = _fingerprint(command)
        if command.idempotency_key in self._idempotency:
            prior_fingerprint, prior_result = self._idempotency[command.idempotency_key or ""]
            if prior_fingerprint == fingerprint:
                return prior_result
            return self._reject(ErrorCode.IDEMPOTENCY_KEY_REUSE, "idempotency key reused with different command body")

        if command.expected_version != self.state.version:
            result = self._reject(
                ErrorCode.STALE_EXPECTED_VERSION,
                f"expected version {command.expected_version}, observed {self.state.version}",
            )
            self._store_idempotency(command, fingerprint, result)
            return result

        next_state = ALLOWED_TRANSITIONS.get((self.state.state, command.command_type))
        if next_state is None:
            result = self._reject(
                ErrorCode.INVALID_TRANSITION,
                f"{command.command_type} is not legal from {self.state.state}",
            )
            self._store_idempotency(command, fingerprint, result)
            return result

        record = KernelRecord(
            record_id=f"krn-{len(self.records) + 1:06d}",
            aggregate_id=self.state.aggregate_id,
            previous_version=self.state.version,
            version=self.state.version + 1,
            previous_state=self.state.state,
            new_state=next_state,
            command_type=command.command_type,
            payload=dict(command.payload),
            authority_refs=tuple(command.authority_refs),
            actor_id=command.actor.actor_id,
        )
        self.records.append(record)
        self.state = AggregateState(
            aggregate_id=self.state.aggregate_id,
            state=next_state,
            version=record.version,
            last_record_id=record.record_id,
            authority_refs=tuple(command.authority_refs),
        )
        result = TransitionResult(True, self.state, record=record)
        self._store_idempotency(command, fingerprint, result)
        return result

    @classmethod
    def replay(cls, records: list[KernelRecord]) -> "GovernanceKernel":
        kernel = cls()
        for record in records:
            kernel.records.append(record)
            kernel.state = AggregateState(
                aggregate_id=record.aggregate_id,
                state=record.new_state,
                version=record.version,
                last_record_id=record.record_id,
                authority_refs=tuple(record.authority_refs),
            )
        return kernel

    def _reject(self, error_code: ErrorCode, message: str) -> TransitionResult:
        return TransitionResult(False, self.state, error_code=error_code, message=message)

    def _store_idempotency(self, command: CommandEnvelope, fingerprint: str, result: TransitionResult) -> None:
        if command.idempotency_key:
            self._idempotency[command.idempotency_key] = (fingerprint, result)


def _fingerprint(command: CommandEnvelope) -> str:
    return json.dumps(
        {
            "actor_id": command.actor.actor_id,
            "authority_refs": command.authority_refs,
            "command_type": command.command_type,
            "expected_version": command.expected_version,
            "payload": command.payload,
        },
        sort_keys=True,
    )
