"""Higher-level V0.3 execution lifecycle skeleton wiring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from nexus.mq.abnormal_state import AbnormalStateRecord
from nexus.mq.business_message import BusinessMessageEmitter
from nexus.mq.commit_boundary import CommitBoundary, CommitResult
from nexus.mq.coordination_runtime import CoordinationRuntime
from nexus.mq.hitl_lifecycle import GateReturnPackage, GateJudgmentRecord, HitlRouteResult
from nexus.mq.message_contracts import ExecutionMessageEnvelope, build_execution_envelope
from nexus.mq.payloads import (
    BusinessMessagePayload,
    CommandMessagePayload,
    DeadLetterMessagePayload,
    ReviewTaskPayload,
    RetryMessagePayload,
)


@dataclass
class ReviewRequestResult:
    authority_wait_id: str
    review_envelope: ExecutionMessageEnvelope
    review_payload: ReviewTaskPayload


@dataclass
class FinalizeSuccessResult:
    commit_result: CommitResult
    business_envelope: ExecutionMessageEnvelope


@dataclass
class FinalizeHitlResult:
    judgment: GateJudgmentRecord
    route: HitlRouteResult


@dataclass
class DispatchResult:
    family: str
    status: str
    review_request: Optional[ReviewRequestResult] = None
    feedback: Optional[object] = None
    evidence_record: Optional[object] = None


class SyntheticReviewTaskSink:
    """Fixture sink for bounded Review_Task publication."""

    def __init__(self):
        self.published: list[ExecutionMessageEnvelope] = []
        self.fail_next: Optional[str] = None

    def publish(self, envelope: ExecutionMessageEnvelope) -> None:
        if self.fail_next:
            error = self.fail_next
            self.fail_next = None
            raise RuntimeError(error)
        self.published.append(envelope)


class ExecutionLifecycleCoordinator:
    """
    Skeleton execution lifecycle coordinator.

    Scope:
    - build Review_Task after durable authority-wait persistence
    - finalize successful command execution into Business_Message after commit
    - evaluate HITL decision records into pass/return outcomes
    - build Retry_Message / Dead_Letter_Message contracts as higher-level outputs
    """

    def __init__(
        self,
        runtime: CoordinationRuntime,
        commit_boundary: Optional[CommitBoundary] = None,
        business_emitter: Optional[BusinessMessageEmitter] = None,
        review_sink: Optional[SyntheticReviewTaskSink] = None,
    ):
        self.runtime = runtime
        self.commit_boundary = commit_boundary or CommitBoundary()
        self.business_emitter = business_emitter or BusinessMessageEmitter()
        self.review_sink = review_sink or SyntheticReviewTaskSink()

    def create_review_request(
        self,
        workflow_instance_id: str,
        workflow_type: str,
        workflow_version: str,
        checkpoint_id: str,
        gate_id: str,
        requested_actor_role: str,
        review_target_ref: str,
        review_type: str,
        required_context_refs: list[str],
        display_summary: str,
        source_agent_id: str,
        source_runtime_instance_id: str,
        source_role: str,
        authority_scope: str,
        target_agent_id: str,
        reply_to_subject: str,
        evidence_package_id: Optional[str] = None,
        due_at: Optional[str] = None,
    ) -> ReviewRequestResult:
        wait = self.runtime.create_authority_wait_state(
            workflow_instance_id=workflow_instance_id,
            checkpoint_id=checkpoint_id,
            gate_id=gate_id,
            requested_actor_role=requested_actor_role,
            evidence_package_id=evidence_package_id,
            due_at=due_at,
        )
        review_payload = self.runtime.hitl_lifecycle.build_review_task_payload(
            authority_wait=wait,
            review_target_ref=review_target_ref,
            review_type=review_type,
            required_context_refs=required_context_refs,
            display_summary=display_summary,
        )
        review_envelope = build_execution_envelope(
            message_type="Review_Task",
            workflow_instance_id=workflow_instance_id,
            workflow_type=workflow_type,
            workflow_version=workflow_version,
            producer=source_agent_id,
            payload=review_payload,
            source_agent_id=source_agent_id,
            source_runtime_instance_id=source_runtime_instance_id,
            source_role=source_role,
            authority_scope=authority_scope,
            target_agent_id=target_agent_id,
            reply_to_subject=reply_to_subject,
            checkpoint_id=checkpoint_id,
            gate_id=gate_id,
            actor_role=requested_actor_role,
            expires_at=due_at,
            correlation_id=wait.authority_wait_id,
        )
        self.runtime.register_review_task_message(
            wait.authority_wait_id,
            review_envelope.message_id,
            review_task_id=review_payload.review_task_id,
            managed=True,
        )
        return ReviewRequestResult(
            authority_wait_id=wait.authority_wait_id,
            review_envelope=review_envelope,
            review_payload=review_payload,
        )

    def publish_review_request(self, request: ReviewRequestResult, resume_from_ref: Optional[str]) -> object:
        try:
            self.review_sink.publish(request.review_envelope)
        except RuntimeError as exc:
            return self.runtime.record_review_task_publication_failure(
                authority_wait_id=request.authority_wait_id,
                review_task_message_id=request.review_envelope.message_id,
                review_task_id=request.review_payload.review_task_id,
                error=str(exc),
            )
        return self.runtime.record_review_task_publication(
            authority_wait_id=request.authority_wait_id,
            review_task_message_id=request.review_envelope.message_id,
            review_task_id=request.review_payload.review_task_id,
            resume_from_ref=resume_from_ref,
        )

    def dispatch_runtime_message(
        self,
        envelope: ExecutionMessageEnvelope,
        *,
        review_request: Optional[ReviewRequestResult] = None,
        resume_from_ref: Optional[str] = None,
    ) -> DispatchResult:
        family = envelope.message_type
        if family == "Command_Message":
            if review_request is None:
                return DispatchResult(family=family, status="command_recorded")
            evidence = self.publish_review_request(review_request, resume_from_ref=resume_from_ref)
            status = evidence.status if hasattr(evidence, "status") else "review_dispatched"
            return DispatchResult(
                family=family,
                status=status,
                review_request=review_request,
                evidence_record=evidence,
            )
        if family == "Review_Task":
            if review_request is None:
                raise ValueError("REVIEW_REQUEST_REQUIRED")
            evidence = self.publish_review_request(review_request, resume_from_ref=resume_from_ref)
            status = evidence.status if hasattr(evidence, "status") else "review_dispatched"
            return DispatchResult(family=family, status=status, review_request=review_request, evidence_record=evidence)
        if family == "Feedback_Message":
            feedback = self.runtime.receive_feedback(
                envelope.reply_to_subject or "agent.maverick.callbacks",
                envelope.to_dict(),
            )
            return DispatchResult(family=family, status=feedback.outcome or ("feedback_accepted" if feedback.valid else "feedback_rejected"), feedback=feedback)
        if family == "Timeout_Message":
            evidence = self.runtime.record_timeout_dispatch_evidence(envelope)
            return DispatchResult(family=family, status=evidence.status, evidence_record=evidence)
        if family == "Retry_Message":
            evidence = self.runtime.record_retry_dispatch_evidence(envelope)
            return DispatchResult(family=family, status=evidence.status, evidence_record=evidence)
        if family == "Dead_Letter_Message":
            evidence = self.runtime.record_dead_letter_dispatch_evidence(envelope)
            return DispatchResult(family=family, status=evidence.status, evidence_record=evidence)
        raise ValueError(f"UNSUPPORTED_PHASE3_FAMILY: {family}")

    def finalize_success(
        self,
        command_envelope: ExecutionMessageEnvelope,
        evidence_refs: list[str],
        previous_state: str,
        new_state: str,
        artifact_refs: Optional[list[str]] = None,
        decision_refs: Optional[list[str]] = None,
    ) -> FinalizeSuccessResult:
        commit_result = self.commit_boundary.try_commit(
            workflow_instance_id=command_envelope.workflow_instance_id,
            evidence_refs=evidence_refs,
            state_transition={"new_state": new_state},
        )
        if not commit_result.accepted:
            raise ValueError(f"COMMIT_REJECTED: {commit_result.error}")

        business_message = self.business_emitter.emit(
            commit_result=commit_result,
            business_event_type=command_envelope.payload.completion_event_type
            if isinstance(command_envelope.payload, CommandMessagePayload)
            else "workflow.progressed",
            previous_state=previous_state,
        )
        business_payload = BusinessMessagePayload(
            business_event_type=business_message.business_event_type,
            transition_id=business_message.transition_id,
            previous_state=business_message.previous_state,
            new_state=business_message.new_state,
            validation_result=business_message.validation_result,
            evidence_refs=list(business_message.evidence_refs),
            artifact_refs=list(artifact_refs or []),
            decision_refs=list(decision_refs or []),
        )
        business_envelope = build_execution_envelope(
            message_type="Business_Message",
            workflow_instance_id=command_envelope.workflow_instance_id,
            workflow_type=command_envelope.workflow_type,
            workflow_version=command_envelope.workflow_version,
            producer=self.runtime.agent_id,
            payload=business_payload,
            source_agent_id=self.runtime.agent_id,
            source_runtime_instance_id=self.runtime.identity_store.get_agent(self.runtime.agent_id).runtime_instance_id,
            source_role=self.runtime.role,
            authority_scope="workflow.result",
            target_agent_id=command_envelope.source_agent_id,
            reply_to_subject=command_envelope.reply_to_subject,
            correlation_id=command_envelope.correlation_id,
            causation_id=command_envelope.message_id,
            checkpoint_id=command_envelope.checkpoint_id,
            gate_id=command_envelope.gate_id,
            artifact_refs=list(artifact_refs or []),
            evidence_refs=list(evidence_refs),
        )
        return FinalizeSuccessResult(commit_result=commit_result, business_envelope=business_envelope)

    def evaluate_hitl_outcome(
        self,
        authority_wait_id: str,
        workflow_id: str,
        workflow_version: str,
        artifact_ref: str,
        artifact_version: str,
        judgment_actor_id: str,
        judgment_actor_role: str,
        authority_basis_ref: str,
        evidence_package_id: str,
        current_state: str,
    ) -> FinalizeHitlResult:
        stored_wait = self.runtime.state_store.get_authority_wait_state(authority_wait_id)
        if stored_wait is None or not stored_wait.hitl_decision_id:
            raise KeyError(f"HITL_DECISION_NOT_READY: {authority_wait_id}")
        stored_decision = self.runtime.state_store.get_hitl_decision_record(stored_wait.hitl_decision_id)
        if stored_decision is None:
            raise KeyError(f"HITL_DECISION_NOT_FOUND: {stored_wait.hitl_decision_id}")
        decision = self.runtime.hitl_lifecycle._decisions.get(stored_decision.decision_id)
        if decision is None:
            raise KeyError(f"HITL_DECISION_NOT_LOADED: {stored_decision.decision_id}")

        unresolved = self.runtime.state_store.list_unresolved_abnormal_states(stored_wait.workflow_instance_id)
        payload_states = [AbnormalStateRecord(**record.payload) for record in unresolved]

        judgment = self.runtime.hitl_lifecycle.evaluate_gate_judgment(
            workflow_instance_id=stored_wait.workflow_instance_id,
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            gate_id=stored_wait.gate_id,
            gate_version=workflow_version,
            checkpoint_id=stored_wait.checkpoint_id,
            artifact_ref=artifact_ref,
            artifact_version=artifact_version,
            judgment_actor_id=judgment_actor_id,
            judgment_actor_role=judgment_actor_role,
            authority_basis_ref=authority_basis_ref,
            decision=decision,
            evidence_package_id=evidence_package_id,
            active_abnormal_states=payload_states,
        )
        route = self.runtime.hitl_lifecycle.route_outcome(
            judgment=judgment,
            current_state=current_state,
        )
        return FinalizeHitlResult(judgment=judgment, route=route)

    def build_retry_message(
        self,
        original_envelope: ExecutionMessageEnvelope,
        target_subject: str,
        retry_count: int,
        max_retries: int,
        retry_reason: str,
        last_error: str,
    ) -> ExecutionMessageEnvelope:
        return build_execution_envelope(
            message_type="Retry_Message",
            workflow_instance_id=original_envelope.workflow_instance_id,
            workflow_type=original_envelope.workflow_type,
            workflow_version=original_envelope.workflow_version,
            producer=self.runtime.agent_id,
            payload=RetryMessagePayload(
                retry_id=f"retry-{original_envelope.message_id}",
                original_message_id=original_envelope.message_id,
                original_idempotency_key=original_envelope.idempotency_key,
                original_message_type=original_envelope.message_type,
                target_subject=target_subject,
                retry_count=retry_count,
                max_retries=max_retries,
                retry_reason=retry_reason,
                last_error=last_error,
                created_at=original_envelope.created_at,
            ),
            source_agent_id=self.runtime.agent_id,
            source_runtime_instance_id=self.runtime.identity_store.get_agent(self.runtime.agent_id).runtime_instance_id,
            source_role=self.runtime.role,
            authority_scope="workflow.command",
            target_agent_id=original_envelope.target_agent_id,
            reply_to_subject=original_envelope.reply_to_subject,
            correlation_id=original_envelope.correlation_id,
            causation_id=original_envelope.message_id,
        )

    def build_dead_letter_message(
        self,
        original_envelope: ExecutionMessageEnvelope,
        attempts_exhausted: int,
        dead_letter_reason: str,
        last_error: str,
    ) -> ExecutionMessageEnvelope:
        return build_execution_envelope(
            message_type="Dead_Letter_Message",
            workflow_instance_id=original_envelope.workflow_instance_id,
            workflow_type=original_envelope.workflow_type,
            workflow_version=original_envelope.workflow_version,
            producer=self.runtime.agent_id,
            payload=DeadLetterMessagePayload(
                dead_letter_id=f"dlq-{original_envelope.message_id}",
                original_message_id=original_envelope.message_id,
                original_message_type=original_envelope.message_type,
                original_idempotency_key=original_envelope.idempotency_key,
                attempts_exhausted=attempts_exhausted,
                dead_letter_reason=dead_letter_reason,
                last_error=last_error,
                dead_lettered_at=original_envelope.created_at,
            ),
            source_agent_id=self.runtime.agent_id,
            source_runtime_instance_id=self.runtime.identity_store.get_agent(self.runtime.agent_id).runtime_instance_id,
            source_role=self.runtime.role,
            authority_scope="workflow.command",
            target_agent_id=original_envelope.target_agent_id,
            reply_to_subject=original_envelope.reply_to_subject,
            correlation_id=original_envelope.correlation_id,
            causation_id=original_envelope.message_id,
        )
