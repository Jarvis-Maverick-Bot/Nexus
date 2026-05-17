"""Typed payload contracts for V0.3 MQ/HITL message families."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from nexus.mq.taxonomy import ABNORMAL_CLASSES, HITL_ACTIONS


@dataclass
class PayloadValidationResult:
    valid: bool
    errors: list[str]


class PayloadContract:
    @classmethod
    def from_dict(cls, payload: dict):
        return cls(**payload)

    def validate(self) -> PayloadValidationResult:
        return PayloadValidationResult(valid=True, errors=[])

    @staticmethod
    def _require_non_empty(value: Optional[str], field_name: str, errors: list[str]) -> None:
        if not value:
            errors.append(f"MISSING_REQUIRED_PAYLOAD_FIELD: {field_name}")

    @staticmethod
    def _is_bounded_text(value: Optional[str]) -> bool:
        if not isinstance(value, str):
            return False
        normalized = " ".join(value.strip().lower().split())
        if len(normalized) < 8:
            return False
        unbounded_markers = {
            "any",
            "anything",
            "as needed",
            "best effort",
            "do it",
            "everything",
            "figure it out",
            "tbd",
            "unknown",
            "whatever",
        }
        return normalized not in unbounded_markers

    @staticmethod
    def _has_bounded_list(values: Optional[list[Any]]) -> bool:
        if not isinstance(values, list) or not values:
            return False
        unbounded_markers = {"*", "all", "any", "anything", "everything", "unbounded", "unknown"}
        for value in values:
            if value is None:
                return False
            if isinstance(value, str) and " ".join(value.strip().lower().split()) in unbounded_markers:
                return False
        return True


@dataclass
class CommandMessagePayload(PayloadContract):
    command_name: str = ""
    target_handler: str = ""
    context_package_ref: Optional[str] = None
    input_refs: list[Any] = field(default_factory=list)
    expected_outputs: list[Any] = field(default_factory=list)
    allowed_side_effects: list[Any] = field(default_factory=list)
    commit_pattern: str = "local_transactional_default"
    recovery_ref: Optional[str] = None
    completion_event_type: str = ""

    def validate(self) -> PayloadValidationResult:
        errors: list[str] = []
        self._require_non_empty(self.command_name, "command_name", errors)
        self._require_non_empty(self.target_handler, "target_handler", errors)
        self._require_non_empty(self.completion_event_type, "completion_event_type", errors)
        if self.commit_pattern not in {"local_transactional_default", "coordinator_distributed_with_outbox"}:
            errors.append(f"INVALID_COMMIT_PATTERN: {self.commit_pattern}")
        return PayloadValidationResult(valid=len(errors) == 0, errors=errors)


@dataclass
class GoalDrivenCommandPayload(PayloadContract):
    command_name: str = "Goal_Driven_Command"
    goal_statement: str = ""
    measurable_done_condition: str = ""
    constraints: Optional[list[Any]] = None
    allowed_write_scope: Optional[list[Any]] = None
    allowed_tool_scope: Optional[list[Any]] = None
    forbidden_actions: list[Any] = field(default_factory=list)
    source_authority_refs: Optional[list[Any]] = None
    source_authority_gap: Optional[str] = None
    validation_commands_or_checks: Optional[list[Any]] = None
    required_evidence_refs: Optional[list[Any]] = None
    stop_conditions: Optional[list[Any]] = None
    escalation_route_ref: str = ""
    progress_record_ref: Optional[str] = None

    def validate(self) -> PayloadValidationResult:
        errors: list[str] = []
        if self.command_name != "Goal_Driven_Command":
            errors.append(f"INVALID_GOAL_COMMAND_NAME: {self.command_name}")
        if not self._is_bounded_text(self.goal_statement):
            errors.append("GOAL_STATEMENT_UNBOUNDED")
        if not self._is_bounded_text(self.measurable_done_condition):
            errors.append("DONE_CONDITION_MISSING")
        if not self._has_bounded_list(self.constraints):
            errors.append("GOAL_SCOPE_UNBOUNDED")
        if not self._has_bounded_scope():
            errors.append("GOAL_SCOPE_UNBOUNDED")
        if not self._has_source_authority_or_declared_gap():
            errors.append("SOURCE_AUTHORITY_UNDECLARED")
        if not self._has_bounded_list(self.validation_commands_or_checks) or not self._has_bounded_list(self.required_evidence_refs):
            errors.append("VALIDATION_CONTRACT_MISSING")
        if not self._has_bounded_list(self.stop_conditions) or not self._is_bounded_text(self.escalation_route_ref):
            errors.append("ESCALATION_ROUTE_MISSING")
        deduped_errors = list(dict.fromkeys(errors))
        return PayloadValidationResult(valid=len(deduped_errors) == 0, errors=deduped_errors)

    def _has_bounded_scope(self) -> bool:
        if isinstance(self.allowed_write_scope, list):
            return self._write_scope_is_bounded()
        return self._has_bounded_list(self.allowed_tool_scope)

    def _write_scope_is_bounded(self) -> bool:
        if self.allowed_write_scope == []:
            return True
        return self._has_bounded_list(self.allowed_write_scope)

    def _has_source_authority_or_declared_gap(self) -> bool:
        if self._has_bounded_list(self.source_authority_refs):
            return True
        return self._is_bounded_text(self.source_authority_gap)


@dataclass
class ReviewTaskPayload(PayloadContract):
    review_task_id: str = ""
    authority_wait_id: str = ""
    review_target_ref: str = ""
    review_type: str = ""
    allowed_actions: list[str] = field(default_factory=list)
    required_context_refs: list[Any] = field(default_factory=list)
    evidence_package_ref: Optional[str] = None
    due_at: Optional[str] = None
    display_summary: str = ""

    def validate(self) -> PayloadValidationResult:
        errors: list[str] = []
        self._require_non_empty(self.review_task_id, "review_task_id", errors)
        self._require_non_empty(self.authority_wait_id, "authority_wait_id", errors)
        self._require_non_empty(self.review_target_ref, "review_target_ref", errors)
        self._require_non_empty(self.review_type, "review_type", errors)
        self._require_non_empty(self.display_summary, "display_summary", errors)
        if not self.allowed_actions:
            errors.append("MISSING_REQUIRED_PAYLOAD_FIELD: allowed_actions")
        elif tuple(self.allowed_actions) != HITL_ACTIONS:
            errors.append(f"INVALID_ALLOWED_ACTIONS: {self.allowed_actions}")
        return PayloadValidationResult(valid=len(errors) == 0, errors=errors)


@dataclass
class FeedbackMessagePayload(PayloadContract):
    feedback_id: str = ""
    review_task_id: str = ""
    authority_wait_id: str = ""
    reviewer_actor_id: str = ""
    reviewer_role: str = ""
    action: str = ""
    feedback_text: Optional[str] = None
    source_message_ref: Optional[str] = None
    submitted_at: str = ""
    reviewed_artifact_refs: list[Any] = field(default_factory=list)
    reviewed_evidence_refs: list[Any] = field(default_factory=list)

    def validate(self) -> PayloadValidationResult:
        errors: list[str] = []
        self._require_non_empty(self.feedback_id, "feedback_id", errors)
        self._require_non_empty(self.review_task_id, "review_task_id", errors)
        self._require_non_empty(self.authority_wait_id, "authority_wait_id", errors)
        self._require_non_empty(self.reviewer_actor_id, "reviewer_actor_id", errors)
        self._require_non_empty(self.reviewer_role, "reviewer_role", errors)
        self._require_non_empty(self.submitted_at, "submitted_at", errors)
        if self.action not in HITL_ACTIONS:
            errors.append(f"INVALID_FEEDBACK_ACTION: {self.action}")
        if self.action == "Revise" and not self.feedback_text:
            errors.append("INVALID_REVISE_FEEDBACK_TEXT: Revise requires non-empty feedback_text")
        return PayloadValidationResult(valid=len(errors) == 0, errors=errors)


@dataclass
class BusinessMessagePayload(PayloadContract):
    business_event_type: str = ""
    transition_id: str = ""
    previous_state: str = ""
    new_state: str = ""
    validation_result: str = ""
    evidence_refs: list[Any] = field(default_factory=list)
    artifact_refs: list[Any] = field(default_factory=list)
    decision_refs: list[Any] = field(default_factory=list)

    def validate(self) -> PayloadValidationResult:
        errors: list[str] = []
        self._require_non_empty(self.business_event_type, "business_event_type", errors)
        self._require_non_empty(self.transition_id, "transition_id", errors)
        self._require_non_empty(self.previous_state, "previous_state", errors)
        self._require_non_empty(self.new_state, "new_state", errors)
        if self.validation_result not in {"accepted", "rejected"}:
            errors.append(f"INVALID_VALIDATION_RESULT: {self.validation_result}")
        return PayloadValidationResult(valid=len(errors) == 0, errors=errors)


@dataclass
class TimeoutMessagePayload(PayloadContract):
    timeout_id: str = ""
    related_message_id: str = ""
    timeout_scope: str = ""
    reason: str = ""
    detected_at: str = ""
    context: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> PayloadValidationResult:
        errors: list[str] = []
        self._require_non_empty(self.timeout_id, "timeout_id", errors)
        self._require_non_empty(self.related_message_id, "related_message_id", errors)
        self._require_non_empty(self.timeout_scope, "timeout_scope", errors)
        self._require_non_empty(self.reason, "reason", errors)
        self._require_non_empty(self.detected_at, "detected_at", errors)
        return PayloadValidationResult(valid=len(errors) == 0, errors=errors)


@dataclass
class RetryMessagePayload(PayloadContract):
    retry_id: str = ""
    original_message_id: str = ""
    original_idempotency_key: str = ""
    original_message_type: str = ""
    target_subject: str = ""
    retry_count: int = 0
    max_retries: int = 0
    retry_reason: str = ""
    last_error: str = ""
    created_at: str = ""

    def validate(self) -> PayloadValidationResult:
        errors: list[str] = []
        self._require_non_empty(self.retry_id, "retry_id", errors)
        self._require_non_empty(self.original_message_id, "original_message_id", errors)
        self._require_non_empty(self.original_idempotency_key, "original_idempotency_key", errors)
        self._require_non_empty(self.original_message_type, "original_message_type", errors)
        self._require_non_empty(self.target_subject, "target_subject", errors)
        self._require_non_empty(self.retry_reason, "retry_reason", errors)
        self._require_non_empty(self.last_error, "last_error", errors)
        self._require_non_empty(self.created_at, "created_at", errors)
        if self.retry_count < 0:
            errors.append(f"INVALID_RETRY_COUNT: {self.retry_count}")
        if self.max_retries < 1:
            errors.append(f"INVALID_MAX_RETRIES: {self.max_retries}")
        return PayloadValidationResult(valid=len(errors) == 0, errors=errors)


@dataclass
class DeadLetterMessagePayload(PayloadContract):
    dead_letter_id: str = ""
    original_message_id: str = ""
    original_message_type: str = ""
    original_idempotency_key: str = ""
    attempts_exhausted: int = 0
    dead_letter_reason: str = ""
    last_error: str = ""
    dead_lettered_at: str = ""

    def validate(self) -> PayloadValidationResult:
        errors: list[str] = []
        self._require_non_empty(self.dead_letter_id, "dead_letter_id", errors)
        self._require_non_empty(self.original_message_id, "original_message_id", errors)
        self._require_non_empty(self.original_message_type, "original_message_type", errors)
        self._require_non_empty(self.original_idempotency_key, "original_idempotency_key", errors)
        self._require_non_empty(self.dead_letter_reason, "dead_letter_reason", errors)
        self._require_non_empty(self.last_error, "last_error", errors)
        self._require_non_empty(self.dead_lettered_at, "dead_lettered_at", errors)
        if self.attempts_exhausted < 1:
            errors.append(f"INVALID_ATTEMPTS_EXHAUSTED: {self.attempts_exhausted}")
        return PayloadValidationResult(valid=len(errors) == 0, errors=errors)


@dataclass
class EvidenceWriteMessagePayload(PayloadContract):
    evidence_write_id: str = ""
    workflow_instance_id: str = ""
    transition_id: str = ""
    evidence_ref: str = ""
    artifact_ref: str = ""
    payload_hash: str = ""
    written_by: str = ""
    written_at: str = ""
    commit_phase: str = ""
    rejection_reason: Optional[str] = None

    def validate(self) -> PayloadValidationResult:
        errors: list[str] = []
        for field_name in (
            "evidence_write_id",
            "workflow_instance_id",
            "transition_id",
            "evidence_ref",
            "artifact_ref",
            "payload_hash",
            "written_by",
            "written_at",
        ):
            self._require_non_empty(getattr(self, field_name), field_name, errors)
        if self.commit_phase not in {"pending", "accepted", "rejected"}:
            errors.append(f"INVALID_COMMIT_PHASE: {self.commit_phase}")
        return PayloadValidationResult(valid=len(errors) == 0, errors=errors)


@dataclass
class StateTransitionMessagePayload(PayloadContract):
    state_transition_id: str = ""
    workflow_instance_id: str = ""
    transition_id: str = ""
    previous_state: str = ""
    requested_state: str = ""
    validation_result: str = ""
    written_by: str = ""
    written_at: str = ""
    commit_phase: str = ""
    rejection_reason: Optional[str] = None

    def validate(self) -> PayloadValidationResult:
        errors: list[str] = []
        for field_name in (
            "state_transition_id",
            "workflow_instance_id",
            "transition_id",
            "previous_state",
            "requested_state",
            "written_by",
            "written_at",
        ):
            self._require_non_empty(getattr(self, field_name), field_name, errors)
        if self.validation_result not in {"accepted", "rejected"}:
            errors.append(f"INVALID_VALIDATION_RESULT: {self.validation_result}")
        if self.commit_phase not in {"pending", "accepted", "rejected"}:
            errors.append(f"INVALID_COMMIT_PHASE: {self.commit_phase}")
        return PayloadValidationResult(valid=len(errors) == 0, errors=errors)


@dataclass
class AbnormalStateRecord(PayloadContract):
    abnormal_state_id: str = ""
    error_event_id: str = ""
    workflow_instance_id: Optional[str] = None
    error_class: str = ""
    abnormal_class: str = ""
    detected_at: str = ""
    resolved_at: Optional[str] = None
    resolved: bool = False
    resolution_record_id: Optional[str] = None
    notification_sent: bool = False
    escalation_timer_id: Optional[str] = None

    def validate(self) -> PayloadValidationResult:
        errors: list[str] = []
        self._require_non_empty(self.abnormal_state_id, "abnormal_state_id", errors)
        self._require_non_empty(self.error_event_id, "error_event_id", errors)
        self._require_non_empty(self.error_class, "error_class", errors)
        self._require_non_empty(self.abnormal_class, "abnormal_class", errors)
        self._require_non_empty(self.detected_at, "detected_at", errors)
        if self.abnormal_class not in ABNORMAL_CLASSES:
            errors.append(f"INVALID_ABNORMAL_CLASS: {self.abnormal_class}")
        return PayloadValidationResult(valid=len(errors) == 0, errors=errors)
