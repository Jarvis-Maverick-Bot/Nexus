"""V0.3 HITL execution lifecycle helpers for Nexus MQ/HITL skeleton."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid

from nexus.mq.abnormal_state import AbnormalStateRecord, classify_abnormal_state, has_blocking_abnormal_state
from nexus.mq.payloads import FeedbackMessagePayload, ReviewTaskPayload
from nexus.mq.taxonomy import DECISION_TYPES, GATE_OUTCOMES


UTC = timezone.utc
WAIT_STATES = (
    "created",
    "waiting",
    "publication_failed",
    "feedback_received",
    "validated",
    "resumed",
    "timed_out",
    "stale",
    "closed",
    "responded",
    "resolved",
    "superseded",
)


@dataclass
class HitlValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


@dataclass
class AuthorityWaitStateV03:
    authority_wait_id: str = field(default_factory=lambda: f"wait-{uuid.uuid4().hex[:12]}")
    workflow_instance_id: str = ""
    checkpoint_id: str = ""
    gate_id: str = ""
    evidence_package_id: Optional[str] = None
    requested_actor_role: str = ""
    status: str = "created"
    notification_request_id: Optional[str] = None
    hitl_decision_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    due_at: Optional[str] = None
    responded_at: Optional[str] = None
    resolved_at: Optional[str] = None


@dataclass
class RawHumanResponseRecord:
    source_record_id: str = field(default_factory=lambda: f"raw-hitl-{uuid.uuid4().hex[:12]}")
    authority_wait_id: str = ""
    source_message_ref: str = ""
    captured_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    raw_action: Optional[str] = None
    raw_text: Optional[str] = None


@dataclass
class HitlDecisionRecordV03:
    decision_id: str = field(default_factory=lambda: f"decision-{uuid.uuid4().hex[:12]}")
    workflow_instance_id: str = ""
    checkpoint_id: str = ""
    linked_gate_id: str = ""
    checkpoint_class: str = ""
    requested_actor_role: str = ""
    responding_actor_id: str = ""
    responding_actor_role: str = ""
    decision_type: str = ""
    decision_value: str = ""
    rationale: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    source_message_refs: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    valid_for_steps: int = 1
    scope_boundary: str = ""
    state_transition_allowed: bool = False
    validation_status: str = "valid"
    validation_findings: list[str] = field(default_factory=list)
    authority_wait_id: str = ""


@dataclass
class GateJudgmentRecord:
    judgment_id: str = field(default_factory=lambda: f"judgment-{uuid.uuid4().hex[:12]}")
    workflow_instance_id: str = ""
    workflow_id: str = ""
    workflow_version: str = ""
    gate_id: str = ""
    gate_version: str = ""
    checkpoint_id: str = ""
    artifact_ref: str = ""
    artifact_version: str = ""
    outcome: str = ""
    judgment_actor_id: str = ""
    judgment_actor_role: str = ""
    authority_basis_ref: str = ""
    hitl_decision_ref: str = ""
    evidence_package_id: str = ""
    review_finding_refs: list[str] = field(default_factory=list)
    metric_snapshot_refs: list[str] = field(default_factory=list)
    conditions: list[dict] = field(default_factory=list)
    rationale: str = ""
    state_transition_allowed: bool = False
    next_required_action: str = ""
    validation_status: str = "valid"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class RequiredCorrection:
    correction_id: str = field(default_factory=lambda: f"corr-{uuid.uuid4().hex[:12]}")
    finding_ref: str = ""
    correction_type: str = ""
    required_action: str = ""
    target_owner: str = ""
    target_node_id: str = ""
    target_artifact_ref: str = ""
    target_artifact_version: str = ""
    acceptance_check: str = ""


@dataclass
class GateReturnPackage:
    return_package_id: str = field(default_factory=lambda: f"return-{uuid.uuid4().hex[:12]}")
    judgment_id: str = ""
    outcome: str = ""
    rejection_source: str = ""
    required_corrections: list[RequiredCorrection] = field(default_factory=list)
    restart_scope: str = "same_gate"
    reentry_gate_id: str = ""
    reentry_gate_version: str = ""
    status: str = "pending"


@dataclass
class HitlRouteResult:
    outcome: str
    state_transition_request: Optional[dict] = None
    gate_return_package: Optional[GateReturnPackage] = None
    hold_reason: Optional[str] = None


class HitlExecutionLifecycle:
    """Deterministic helper for the V0.3 12-step HITL control loop."""

    def __init__(self):
        self._waits: dict[str, AuthorityWaitStateV03] = {}
        self._decisions: dict[str, HitlDecisionRecordV03] = {}
        self._judgments: dict[str, GateJudgmentRecord] = {}

    def create_authority_wait_state(
        self,
        workflow_instance_id: str,
        checkpoint_id: str,
        gate_id: str,
        requested_actor_role: str,
        evidence_package_id: Optional[str] = None,
        due_at: Optional[str] = None,
    ) -> AuthorityWaitStateV03:
        wait = AuthorityWaitStateV03(
            workflow_instance_id=workflow_instance_id,
            checkpoint_id=checkpoint_id,
            gate_id=gate_id,
            evidence_package_id=evidence_package_id,
            requested_actor_role=requested_actor_role,
            status="waiting",
            due_at=due_at,
        )
        self._waits[wait.authority_wait_id] = wait
        return wait

    def build_review_task_payload(
        self,
        authority_wait: AuthorityWaitStateV03,
        review_target_ref: str,
        review_type: str,
        required_context_refs: list[str],
        display_summary: str,
    ) -> ReviewTaskPayload:
        return ReviewTaskPayload(
            review_task_id=f"review-{authority_wait.authority_wait_id}",
            authority_wait_id=authority_wait.authority_wait_id,
            review_target_ref=review_target_ref,
            review_type=review_type,
            allowed_actions=["Approve", "Reject", "Revise"],
            required_context_refs=required_context_refs,
            evidence_package_ref=authority_wait.evidence_package_id,
            due_at=authority_wait.due_at,
            display_summary=display_summary,
        )

    def capture_raw_response(
        self,
        authority_wait_id: str,
        source_message_ref: str,
        raw_action: Optional[str] = None,
        raw_text: Optional[str] = None,
    ) -> RawHumanResponseRecord:
        return RawHumanResponseRecord(
            authority_wait_id=authority_wait_id,
            source_message_ref=source_message_ref,
            raw_action=raw_action,
            raw_text=raw_text,
        )

    def normalize_feedback(
        self,
        feedback_payload: FeedbackMessagePayload,
        workflow_instance_id: str,
        checkpoint_id: str,
        gate_id: str,
        checkpoint_class: str,
        scope_boundary: str,
    ) -> tuple[HitlValidationResult, Optional[HitlDecisionRecordV03]]:
        payload_validation = feedback_payload.validate()
        if not payload_validation.valid:
            return HitlValidationResult(valid=False, errors=payload_validation.errors), None

        wait = self._waits.get(feedback_payload.authority_wait_id)
        if wait is None:
            return HitlValidationResult(valid=False, errors=["FEEDBACK_STALE: authority_wait_state not found"]), None
        if wait.status in {"resolved", "superseded", "timed_out", "stale", "closed", "escalated"}:
            return HitlValidationResult(valid=False, errors=[f"FEEDBACK_STALE: authority_wait_state is {wait.status}"]), None

        decision_type = feedback_payload.action.lower()
        if decision_type not in DECISION_TYPES:
            return HitlValidationResult(valid=False, errors=[f"INVALID_DECISION_TYPE: {decision_type}"]), None

        decision = HitlDecisionRecordV03(
            workflow_instance_id=workflow_instance_id,
            checkpoint_id=checkpoint_id,
            linked_gate_id=gate_id,
            checkpoint_class=checkpoint_class,
            requested_actor_role=wait.requested_actor_role,
            responding_actor_id=feedback_payload.reviewer_actor_id,
            responding_actor_role=feedback_payload.reviewer_role,
            decision_type=decision_type,
            decision_value=feedback_payload.action,
            rationale=feedback_payload.feedback_text or feedback_payload.action,
            evidence_refs=list(feedback_payload.reviewed_evidence_refs),
            source_message_refs=[ref for ref in [feedback_payload.source_message_ref] if ref],
            valid_for_steps=1,
            scope_boundary=scope_boundary,
            state_transition_allowed=decision_type in {"approve", "override", "resume"},
            authority_wait_id=wait.authority_wait_id,
        )
        self._decisions[decision.decision_id] = decision
        wait.status = "responded"
        wait.responded_at = datetime.now(UTC).isoformat()
        wait.hitl_decision_id = decision.decision_id
        return HitlValidationResult(valid=True), decision

    def validate_feedback_correlation(
        self,
        authority_wait_id: str,
        correlation_id: str,
        review_task_message_id: str,
        causation_id: Optional[str],
    ) -> HitlValidationResult:
        errors: list[str] = []
        if correlation_id != authority_wait_id:
            errors.append("INVALID_FEEDBACK_CORRELATION: correlation_id must equal authority_wait_id")
        if causation_id != review_task_message_id:
            errors.append("INVALID_FEEDBACK_CAUSATION: causation_id must equal Review_Task.message_id")
        return HitlValidationResult(valid=len(errors) == 0, errors=errors)

    def evaluate_gate_judgment(
        self,
        workflow_instance_id: str,
        workflow_id: str,
        workflow_version: str,
        gate_id: str,
        gate_version: str,
        checkpoint_id: str,
        artifact_ref: str,
        artifact_version: str,
        judgment_actor_id: str,
        judgment_actor_role: str,
        authority_basis_ref: str,
        decision: HitlDecisionRecordV03,
        evidence_package_id: str,
        active_abnormal_states: Optional[list[AbnormalStateRecord]] = None,
        review_finding_refs: Optional[list[str]] = None,
        metric_snapshot_refs: Optional[list[str]] = None,
    ) -> GateJudgmentRecord:
        abnormal_states = active_abnormal_states or []
        blocking = has_blocking_abnormal_state(abnormal_states)
        outcome = self._decision_to_outcome(decision.decision_type)
        if outcome == "pass" and blocking:
            outcome = "blocked"

        judgment = GateJudgmentRecord(
            workflow_instance_id=workflow_instance_id,
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            gate_id=gate_id,
            gate_version=gate_version,
            checkpoint_id=checkpoint_id,
            artifact_ref=artifact_ref,
            artifact_version=artifact_version,
            outcome=outcome,
            judgment_actor_id=judgment_actor_id,
            judgment_actor_role=judgment_actor_role,
            authority_basis_ref=authority_basis_ref,
            hitl_decision_ref=decision.decision_id,
            evidence_package_id=evidence_package_id,
            review_finding_refs=review_finding_refs or [],
            metric_snapshot_refs=metric_snapshot_refs or [],
            rationale=decision.rationale,
            state_transition_allowed=outcome in {"pass", "conditional_pass", "waived"},
            next_required_action=self._outcome_to_next_action(outcome),
            validation_status="valid",
        )
        self._judgments[judgment.judgment_id] = judgment
        return judgment

    def route_outcome(
        self,
        judgment: GateJudgmentRecord,
        current_state: str,
        required_corrections: Optional[list[RequiredCorrection]] = None,
    ) -> HitlRouteResult:
        if judgment.outcome in {"pass", "conditional_pass", "waived"}:
            new_state = "approved" if judgment.outcome == "pass" else "approved_with_conditions"
            return HitlRouteResult(
                outcome=judgment.outcome,
                state_transition_request={
                    "transition_type": "gate_passed",
                    "previous_state": current_state,
                    "new_state": new_state,
                    "gate_judgment_id": judgment.judgment_id,
                },
            )

        if judgment.outcome in {"revise", "blocked", "defer"}:
            return HitlRouteResult(
                outcome=judgment.outcome,
                gate_return_package=GateReturnPackage(
                    judgment_id=judgment.judgment_id,
                    outcome=judgment.outcome,
                    rejection_source=judgment.hitl_decision_ref,
                    required_corrections=required_corrections or [],
                    restart_scope="same_gate",
                    reentry_gate_id=judgment.gate_id,
                    reentry_gate_version=judgment.gate_version,
                    status="pending",
                ),
                hold_reason=judgment.next_required_action,
            )

        return HitlRouteResult(outcome=judgment.outcome, hold_reason="unsupported_outcome")

    def handle_no_response_timeout(self, authority_wait_id: str) -> tuple[AuthorityWaitStateV03, HitlDecisionRecordV03, AbnormalStateRecord]:
        wait = self._waits[authority_wait_id]
        wait.status = "timed_out"
        decision = HitlDecisionRecordV03(
            workflow_instance_id=wait.workflow_instance_id,
            checkpoint_id=wait.checkpoint_id,
            linked_gate_id=wait.gate_id,
            checkpoint_class="mandatory_authority",
            requested_actor_role=wait.requested_actor_role,
            responding_actor_id="system",
            responding_actor_role="system",
            decision_type="no_response_escalated",
            decision_value="no_response_escalated",
            rationale="Review task due_at passed without valid human response.",
            source_message_refs=[],
            valid_for_steps=1,
            scope_boundary=wait.gate_id,
            state_transition_allowed=False,
            authority_wait_id=wait.authority_wait_id,
        )
        self._decisions[decision.decision_id] = decision
        wait.hitl_decision_id = decision.decision_id
        abnormal = classify_abnormal_state(
            error_event_id=f"authority-timeout:{wait.authority_wait_id}",
            error_class="authority_unresolved",
            workflow_instance_id=wait.workflow_instance_id,
        )
        wait.status = "escalated"
        return wait, decision, abnormal

    def supersede_wait_state(self, authority_wait_id: str) -> AuthorityWaitStateV03:
        wait = self._waits[authority_wait_id]
        wait.status = "superseded"
        wait.resolved_at = datetime.now(UTC).isoformat()
        return wait

    @staticmethod
    def _decision_to_outcome(decision_type: str) -> str:
        mapping = {
            "approve": "pass",
            "reject": "blocked",
            "revise": "revise",
            "defer": "defer",
            "override": "waived",
            "resume": "pass",
            "stop": "blocked",
            "no_response_escalated": "blocked",
        }
        return mapping.get(decision_type, "defer")

    @staticmethod
    def _outcome_to_next_action(outcome: str) -> str:
        mapping = {
            "pass": "advance_workflow",
            "conditional_pass": "advance_with_conditions",
            "waived": "advance_with_waiver",
            "revise": "route_to_correction",
            "blocked": "block_and_escalate",
            "defer": "hold_pending_clarification",
        }
        return mapping.get(outcome, "manual_review")
