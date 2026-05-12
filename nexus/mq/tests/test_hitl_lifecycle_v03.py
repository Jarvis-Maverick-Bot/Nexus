"""V0.3 HITL lifecycle and abnormal-state helper tests."""

from nexus.mq.abnormal_state import (
    classify_abnormal_state,
    has_blocking_abnormal_state,
    resolve_abnormal_state,
    should_notify,
)
from nexus.mq.hitl_lifecycle import HitlExecutionLifecycle, RequiredCorrection
from nexus.mq.payloads import FeedbackMessagePayload


def test_feedback_correlation_uses_wait_state_not_review_task_message_id():
    lifecycle = HitlExecutionLifecycle()
    wait = lifecycle.create_authority_wait_state(
        workflow_instance_id="wf-001",
        checkpoint_id="ckpt-001",
        gate_id="gate-001",
        requested_actor_role="reviewer",
    )

    result = lifecycle.validate_feedback_correlation(
        authority_wait_id=wait.authority_wait_id,
        correlation_id="review-task-msg-001",
        review_task_message_id="review-task-msg-001",
        causation_id="review-task-msg-001",
    )

    assert result.valid is False
    assert "INVALID_FEEDBACK_CORRELATION: correlation_id must equal authority_wait_id" in result.errors


def test_normalize_feedback_updates_wait_and_creates_decision():
    lifecycle = HitlExecutionLifecycle()
    wait = lifecycle.create_authority_wait_state(
        workflow_instance_id="wf-001",
        checkpoint_id="ckpt-001",
        gate_id="gate-001",
        requested_actor_role="reviewer",
        evidence_package_id="pkg-001",
    )
    payload = FeedbackMessagePayload(
        feedback_id="fb-001",
        review_task_id="review-001",
        authority_wait_id=wait.authority_wait_id,
        reviewer_actor_id="alex",
        reviewer_role="reviewer",
        action="Approve",
        submitted_at="2026-05-08T12:00:00Z",
        reviewed_evidence_refs=["evidence://pkg-001"],
    )

    result, decision = lifecycle.normalize_feedback(
        feedback_payload=payload,
        workflow_instance_id="wf-001",
        checkpoint_id="ckpt-001",
        gate_id="gate-001",
        checkpoint_class="mandatory_authority",
        scope_boundary="gate-001",
    )

    assert result.valid is True
    assert decision is not None
    assert decision.decision_type == "approve"
    assert decision.state_transition_allowed is True
    assert lifecycle._waits[wait.authority_wait_id].status == "responded"


def test_gate_judgment_pass_is_blocked_when_abnormal_state_active():
    lifecycle = HitlExecutionLifecycle()
    wait = lifecycle.create_authority_wait_state(
        workflow_instance_id="wf-001",
        checkpoint_id="ckpt-001",
        gate_id="gate-001",
        requested_actor_role="reviewer",
    )
    payload = FeedbackMessagePayload(
        feedback_id="fb-001",
        review_task_id="review-001",
        authority_wait_id=wait.authority_wait_id,
        reviewer_actor_id="alex",
        reviewer_role="reviewer",
        action="Approve",
        submitted_at="2026-05-08T12:00:00Z",
    )
    _, decision = lifecycle.normalize_feedback(
        feedback_payload=payload,
        workflow_instance_id="wf-001",
        checkpoint_id="ckpt-001",
        gate_id="gate-001",
        checkpoint_class="mandatory_authority",
        scope_boundary="gate-001",
    )
    abnormal = classify_abnormal_state(
        error_event_id="err-001",
        error_class="authority_unresolved",
        workflow_instance_id="wf-001",
    )

    judgment = lifecycle.evaluate_gate_judgment(
        workflow_instance_id="wf-001",
        workflow_id="workflow",
        workflow_version="1.0",
        gate_id="gate-001",
        gate_version="1.0",
        checkpoint_id="ckpt-001",
        artifact_ref="artifact://build/1",
        artifact_version="1",
        judgment_actor_id="alex",
        judgment_actor_role="reviewer",
        authority_basis_ref="authority://gate-001",
        decision=decision,
        evidence_package_id="pkg-001",
        active_abnormal_states=[abnormal],
    )

    assert judgment.outcome == "blocked"
    assert has_blocking_abnormal_state([abnormal]) is True


def test_route_outcome_revise_returns_gate_return_package():
    lifecycle = HitlExecutionLifecycle()
    correction = RequiredCorrection(
        finding_ref="finding-001",
        correction_type="evidence_gap",
        required_action="Add missing evidence",
        target_owner="nova",
        target_node_id="node-qa",
        target_artifact_ref="artifact://qa/1",
        target_artifact_version="1",
        acceptance_check="Evidence package refreshed",
    )
    judgment = lifecycle.evaluate_gate_judgment(
        workflow_instance_id="wf-001",
        workflow_id="workflow",
        workflow_version="1.0",
        gate_id="gate-001",
        gate_version="1.0",
        checkpoint_id="ckpt-001",
        artifact_ref="artifact://build/1",
        artifact_version="1",
        judgment_actor_id="alex",
        judgment_actor_role="reviewer",
        authority_basis_ref="authority://gate-001",
        decision=lifecycle.normalize_feedback(
            feedback_payload=FeedbackMessagePayload(
                feedback_id="fb-001",
                review_task_id="review-001",
                authority_wait_id=lifecycle.create_authority_wait_state(
                    workflow_instance_id="wf-001",
                    checkpoint_id="ckpt-001",
                    gate_id="gate-001",
                    requested_actor_role="reviewer",
                ).authority_wait_id,
                reviewer_actor_id="alex",
                reviewer_role="reviewer",
                action="Revise",
                feedback_text="Need correction",
                submitted_at="2026-05-08T12:00:00Z",
            ),
            workflow_instance_id="wf-001",
            checkpoint_id="ckpt-001",
            gate_id="gate-001",
            checkpoint_class="mandatory_authority",
            scope_boundary="gate-001",
        )[1],
        evidence_package_id="pkg-001",
    )

    route = lifecycle.route_outcome(
        judgment=judgment,
        current_state="in_review",
        required_corrections=[correction],
    )

    assert route.outcome == "revise"
    assert route.gate_return_package is not None
    assert route.gate_return_package.required_corrections[0].target_owner == "nova"


def test_no_response_timeout_creates_authority_stall_abnormal_state():
    lifecycle = HitlExecutionLifecycle()
    wait = lifecycle.create_authority_wait_state(
        workflow_instance_id="wf-001",
        checkpoint_id="ckpt-001",
        gate_id="gate-001",
        requested_actor_role="reviewer",
    )

    updated_wait, decision, abnormal = lifecycle.handle_no_response_timeout(wait.authority_wait_id)

    assert updated_wait.status == "escalated"
    assert decision.decision_type == "no_response_escalated"
    assert abnormal.abnormal_class == "authority_stall"
    assert should_notify(abnormal.abnormal_class) is True


def test_abnormal_state_requires_resolution_record_to_resolve():
    abnormal = classify_abnormal_state(
        error_event_id="err-001",
        error_class="transport",
        workflow_instance_id="wf-001",
    )

    resolved_state, resolution = resolve_abnormal_state(
        state=abnormal,
        resolved_by="ops",
        resolution_action="restarted listener runtime",
        workflow_instance_id="wf-001",
        evidence_refs=["evidence://ops/1"],
    )

    validation = resolved_state.validate()

    assert resolution.resolution_id == resolved_state.resolution_record_id
    assert resolved_state.resolved is True
    assert validation.valid is True
