"""Disabled-by-default Codex worker surfaces for WBS 7.19.13."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from nexus.mq.agent_registry import AgentRegistryRecord
from nexus.mq.agent_registry_events import secret_material_errors
from nexus.mq.runtime_adapter_contract import RuntimeAdapterEvent


CODEX_EXECUTION_EVENT_SCHEMA_VERSION = "4.19.codex.execution_event.v1"
CODEX_RESULT_CANDIDATE_SCHEMA_VERSION = "4.19.codex.result_candidate.v1"


@dataclass
class CodexWorkerPolicy:
    worker_enabled: bool = False
    live_nats_enabled: bool = False
    business_execution_enabled: bool = False


@dataclass
class CodexWorkerStartDecision:
    accepted: bool
    errors: list[str] = field(default_factory=list)
    live_worker_started: bool = False
    nats_listener_started: bool = False
    not_business_completion: bool = True


@dataclass
class CodexExecutionEvent:
    event_id: str
    run_id: str
    assignment_id: str
    task_id: str
    runtime_instance_id: str
    event_type: str
    event_time: str
    evidence_ref: str
    step_ref: Optional[str] = None
    command_ref: Optional[str] = None
    command_exit_code: Optional[int] = None
    error_code: Optional[str] = None
    schema_version: str = CODEX_EXECUTION_EVENT_SCHEMA_VERSION
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CodexResultCandidate:
    result_id: str
    run_id: str
    assignment_id: str
    task_id: str
    runtime_instance_id: str
    status: str
    changed_file_refs: list[str]
    evidence_refs: list[str]
    emitted_at: str
    diff_ref: Optional[str] = None
    command_result_refs: list[str] = field(default_factory=list)
    test_result_refs: list[str] = field(default_factory=list)
    telemetry_refs: list[str] = field(default_factory=list)
    blocker_summary_ref: Optional[str] = None
    no_go_violation_detected: bool = False
    disallowed_write_detected: bool = False
    schema_version: str = CODEX_RESULT_CANDIDATE_SCHEMA_VERSION
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CodexWorkerDaemon:
    def __init__(self, *, adapter_id: str, record: AgentRegistryRecord, policy: CodexWorkerPolicy):
        self.adapter_id = adapter_id
        self.record = record
        self.policy = policy

    def evaluate_start(self) -> CodexWorkerStartDecision:
        errors: list[str] = []
        if not self.policy.worker_enabled:
            errors.append("CODEX_WORKER_DISABLED")
        if self.policy.live_nats_enabled:
            errors.append("CODEX_LIVE_NATS_NOT_AUTHORIZED")
        if self.policy.business_execution_enabled:
            errors.append("CODEX_BUSINESS_EXECUTION_NOT_AUTHORIZED")
        if errors:
            return CodexWorkerStartDecision(False, errors=_dedupe(errors))
        return CodexWorkerStartDecision(True)

    def build_heartbeat_event(self, *, now_at: str) -> RuntimeAdapterEvent:
        return self._event(
            event_type="heartbeat",
            payload={
                "presence_state": self.record.presence_state,
                "runtime_provider": self.record.runtime_provider,
                "accepting_new_work": self.record.accepting_new_work,
                "event_time": now_at,
            },
        )

    def build_drain_event(self, *, now_at: str, reason_ref: str) -> RuntimeAdapterEvent:
        return self._event(
            event_type="anomaly",
            payload={
                "presence_state": "draining",
                "accepting_new_work": False,
                "reason_ref": reason_ref,
                "event_time": now_at,
            },
        )

    def build_offline_event(self, *, now_at: str, reason_ref: str) -> RuntimeAdapterEvent:
        return self._event(
            event_type="anomaly",
            payload={
                "presence_state": "offline",
                "accepting_new_work": False,
                "reason_ref": reason_ref,
                "event_time": now_at,
            },
        )

    def _event(self, *, event_type: str, payload: dict[str, Any]) -> RuntimeAdapterEvent:
        return RuntimeAdapterEvent(
            adapter_id=self.adapter_id,
            adapter_type="codex_worker",
            protocol_version="4.19.runtime_adapter.v1",
            event_type=event_type,
            agent_id=self.record.agent_id,
            runtime_instance_id=self.record.runtime_instance_id,
            message_id=None,
            correlation_id=None,
            assignment_id=None,
            payload=payload,
            evidence_refs=[],
        )


def build_codex_execution_event(
    *,
    event_id: str,
    run_id: str,
    assignment_id: str,
    task_id: str,
    runtime_instance_id: str,
    event_type: str,
    event_time: str,
    evidence_ref: str,
    step_ref: Optional[str] = None,
    command_ref: Optional[str] = None,
    command_exit_code: Optional[int] = None,
    error_code: Optional[str] = None,
) -> CodexExecutionEvent:
    event = CodexExecutionEvent(
        event_id=event_id,
        run_id=run_id,
        assignment_id=assignment_id,
        task_id=task_id,
        runtime_instance_id=runtime_instance_id,
        event_type=event_type,
        event_time=event_time,
        evidence_ref=evidence_ref,
        step_ref=step_ref,
        command_ref=command_ref,
        command_exit_code=command_exit_code,
        error_code=error_code,
    )
    errors = validate_codex_execution_event(event)
    if errors:
        raise ValueError("; ".join(errors))
    return event


def validate_codex_execution_event(event: CodexExecutionEvent) -> list[str]:
    errors: list[str] = []
    if event.schema_version != CODEX_EXECUTION_EVENT_SCHEMA_VERSION:
        errors.append("UNSUPPORTED_CODEX_EXECUTION_EVENT_SCHEMA")
    if event.not_business_completion is not True:
        errors.append("CODEX_EXECUTION_EVENT_CANNOT_BE_BUSINESS_COMPLETION")
    if event.event_type not in {
        "accepted",
        "started",
        "step_started",
        "step_finished",
        "file_changed",
        "command_started",
        "command_finished",
        "checkpointed",
        "interrupted",
        "failed",
        "completed_execution",
    }:
        errors.append(f"UNSUPPORTED_CODEX_EXECUTION_EVENT_TYPE: {event.event_type}")
    if not event.evidence_ref:
        errors.append("MISSING_CODEX_EXECUTION_EVENT_EVIDENCE")
    errors.extend(secret_material_errors(event.to_dict(), path="codex_execution_event"))
    return _dedupe(errors)


def build_codex_result_candidate(
    *,
    result_id: str,
    run_id: str,
    assignment_id: str,
    task_id: str,
    runtime_instance_id: str,
    status: str,
    changed_file_refs: list[str],
    evidence_refs: list[str],
    emitted_at: str,
    diff_ref: Optional[str] = None,
    command_result_refs: Optional[list[str]] = None,
    test_result_refs: Optional[list[str]] = None,
    telemetry_refs: Optional[list[str]] = None,
    blocker_summary_ref: Optional[str] = None,
    no_go_violation_detected: bool = False,
    disallowed_write_detected: bool = False,
) -> CodexResultCandidate:
    candidate = CodexResultCandidate(
        result_id=result_id,
        run_id=run_id,
        assignment_id=assignment_id,
        task_id=task_id,
        runtime_instance_id=runtime_instance_id,
        status=status,
        changed_file_refs=list(changed_file_refs),
        evidence_refs=list(evidence_refs),
        emitted_at=emitted_at,
        diff_ref=diff_ref,
        command_result_refs=list(command_result_refs or []),
        test_result_refs=list(test_result_refs or []),
        telemetry_refs=list(telemetry_refs or []),
        blocker_summary_ref=blocker_summary_ref,
        no_go_violation_detected=no_go_violation_detected,
        disallowed_write_detected=disallowed_write_detected,
    )
    errors = validate_codex_result_candidate(candidate)
    if errors:
        raise ValueError("; ".join(errors))
    return candidate


def validate_codex_result_candidate(candidate: CodexResultCandidate) -> list[str]:
    errors: list[str] = []
    if candidate.schema_version != CODEX_RESULT_CANDIDATE_SCHEMA_VERSION:
        errors.append("UNSUPPORTED_CODEX_RESULT_CANDIDATE_SCHEMA")
    if candidate.not_business_completion is not True:
        errors.append("CODEX_RESULT_CANDIDATE_CANNOT_BE_BUSINESS_COMPLETION")
    if candidate.status not in {"completed_execution", "blocked", "failed", "interrupted", "quarantined"}:
        errors.append(f"UNSUPPORTED_CODEX_RESULT_CANDIDATE_STATUS: {candidate.status}")
    if not candidate.evidence_refs:
        errors.append("MISSING_CODEX_RESULT_CANDIDATE_EVIDENCE")
    errors.extend(secret_material_errors(candidate.to_dict(), path="codex_result_candidate"))
    return _dedupe(errors)


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error and error not in deduped:
            deduped.append(error)
    return deduped
