from datetime import datetime, timedelta, timezone
import os

import pytest

from nexus.mq.coordination_runtime import CoordinationRuntime
from nexus.mq.execution_lifecycle import ExecutionLifecycleCoordinator, SyntheticReviewTaskSink
from nexus.mq.message_contracts import build_execution_envelope
from nexus.mq.payloads import CommandMessagePayload, FeedbackMessagePayload


def _identity_config_path() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "agents.yaml")
    )


def _future_iso(minutes: int = 5) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def _past_iso(minutes: int = 5) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def _make_runtime(tmp_path) -> CoordinationRuntime:
    runtime = CoordinationRuntime.from_paths(
        runtime_id="maverick-runtime-phase3",
        agent_id="maverick",
        role="maverick",
        db_path=tmp_path / "phase3.sqlite3",
        identity_yaml_path=_identity_config_path(),
    )
    runtime.startup()
    return runtime


def _make_coordinator(tmp_path):
    runtime = _make_runtime(tmp_path)
    sink = SyntheticReviewTaskSink()
    return runtime, ExecutionLifecycleCoordinator(runtime, review_sink=sink), sink


def _make_command() -> object:
    return build_execution_envelope(
        message_type="Command_Message",
        workflow_instance_id="wf-phase3-001",
        workflow_type="delivery",
        workflow_version="0.3",
        producer="maverick",
        payload=CommandMessagePayload(
            command_name="dispatch_review",
            target_handler="review.dispatch",
            completion_event_type="review.dispatched",
            allowed_side_effects=["publish_review_task"],
        ),
        source_agent_id="maverick",
        source_runtime_instance_id="maverick-windows-main-20260507",
        source_role="maverick",
        authority_scope="workflow.command",
        target_agent_id="maverick",
        reply_to_subject="agent.maverick.callbacks",
        checkpoint_id="checkpoint-001",
        gate_id="gate-001",
        correlation_id="corr-phase3-command",
        expires_at=_future_iso(),
    )


def _make_review_request(coordinator: ExecutionLifecycleCoordinator, due_at: str | None = None):
    return coordinator.create_review_request(
        workflow_instance_id="wf-phase3-001",
        workflow_type="delivery",
        workflow_version="0.3",
        checkpoint_id="checkpoint-001",
        gate_id="gate-001",
        requested_actor_role="viper",
        review_target_ref="artifact://draft-001",
        review_type="formal_review",
        required_context_refs=["ctx://1"],
        display_summary="Review the draft before resume.",
        source_agent_id="maverick",
        source_runtime_instance_id="maverick-windows-main-20260507",
        source_role="maverick",
        authority_scope="workflow.command",
        target_agent_id="viper",
        reply_to_subject="agent.maverick.callbacks",
        evidence_package_id="evidence://pkg-001",
        due_at=due_at or _future_iso(),
    )


def _make_feedback(authority_wait_id: str, review_task_id: str, causation_id: str, **overrides):
    return build_execution_envelope(
        message_type="Feedback_Message",
        workflow_instance_id="wf-phase3-001",
        workflow_type="hitl",
        workflow_version="0.3",
        producer="viper",
        payload=FeedbackMessagePayload(
            feedback_id=overrides.pop("feedback_id", "feedback-001"),
            review_task_id=review_task_id,
            authority_wait_id=authority_wait_id,
            reviewer_actor_id=overrides.pop("reviewer_actor_id", "viper"),
            reviewer_role=overrides.pop("reviewer_role", "viper"),
            action=overrides.pop("action", "Approve"),
            feedback_text=overrides.pop("feedback_text", None),
            submitted_at=overrides.pop("submitted_at", datetime.now(timezone.utc).isoformat()),
        ),
        source_agent_id=overrides.pop("source_agent_id", "viper"),
        source_runtime_instance_id="viper-windows-main-20260507",
        source_role=overrides.pop("source_role", "viper"),
        authority_scope=overrides.pop("authority_scope", "workflow.feedback"),
        target_agent_id="maverick",
        reply_to_subject="agent.maverick.callbacks",
        correlation_id=overrides.pop("correlation_id", authority_wait_id),
        causation_id=overrides.pop("causation_id", causation_id),
        expires_at=overrides.pop("expires_at", _future_iso()),
    )


def test_hitl_01_wait_persists_before_publication_and_uniqueness_holds(tmp_path):
    runtime, coordinator, sink = _make_coordinator(tmp_path)
    command = _make_command()
    request = _make_review_request(coordinator)

    stored_wait = runtime.state_store.get_authority_wait_state(request.authority_wait_id)
    active_wait_records = runtime.state_store.list_phase3_runtime_records("active_wait_record", request.authority_wait_id)
    dispatch = coordinator.dispatch_runtime_message(
        command,
        review_request=request,
        resume_from_ref="resume://checkpoint-001",
    )

    assert stored_wait is not None
    assert active_wait_records
    assert dispatch.status == "published"
    assert sink.published[0].message_type == "Review_Task"
    with pytest.raises(ValueError, match="ACTIVE_WAIT_UNIQUENESS_CONFLICT"):
        runtime.create_authority_wait_state(
            workflow_instance_id="wf-phase3-001",
            checkpoint_id="checkpoint-001",
            gate_id="gate-001",
            requested_actor_role="viper",
            due_at=_future_iso(),
        )
    runtime.close()


def test_hitl_02_accepted_feedback_persists_raw_normalized_resume_and_closure(tmp_path):
    runtime, coordinator, _ = _make_coordinator(tmp_path)
    request = _make_review_request(coordinator)
    coordinator.dispatch_runtime_message(_make_command(), review_request=request, resume_from_ref="resume://checkpoint-001")
    feedback = _make_feedback(
        request.authority_wait_id,
        request.review_payload.review_task_id,
        request.review_envelope.message_id,
    )

    result = coordinator.dispatch_runtime_message(feedback)
    closures = runtime.state_store.list_phase3_runtime_records("wait_closure_record", request.authority_wait_id)

    assert result.status == "feedback_accepted"
    assert result.feedback.raw_feedback_record is not None
    assert result.feedback.normalized_decision_record is not None
    assert result.feedback.resume_request_record is not None
    assert closures[0].payload["close_reason"] == "accepted_feedback"
    runtime.close()


def test_hitl_03_feedback_for_stale_wait_is_rejected_without_resume(tmp_path):
    runtime, coordinator, _ = _make_coordinator(tmp_path)
    request = _make_review_request(coordinator)
    coordinator.dispatch_runtime_message(_make_command(), review_request=request, resume_from_ref="resume://checkpoint-001")
    wait = runtime._require_wait(request.authority_wait_id)
    wait.status = "stale"
    runtime._persist_authority_wait_state(wait)
    feedback = _make_feedback(
        request.authority_wait_id,
        request.review_payload.review_task_id,
        request.review_envelope.message_id,
        feedback_id="feedback-stale-001",
    )

    result = coordinator.dispatch_runtime_message(feedback)
    resumes = runtime.state_store.list_phase3_runtime_records("bounded_resume_request_record", request.authority_wait_id)

    assert result.status == "feedback_rejected_stale"
    assert resumes == []
    runtime.close()


def test_hitl_04_feedback_for_closed_wait_is_rejected_without_new_decision(tmp_path):
    runtime, coordinator, _ = _make_coordinator(tmp_path)
    request = _make_review_request(coordinator)
    coordinator.dispatch_runtime_message(_make_command(), review_request=request, resume_from_ref="resume://checkpoint-001")
    accepted = _make_feedback(
        request.authority_wait_id,
        request.review_payload.review_task_id,
        request.review_envelope.message_id,
        feedback_id="feedback-close-001",
    )
    coordinator.dispatch_runtime_message(accepted)
    feedback = _make_feedback(
        request.authority_wait_id,
        request.review_payload.review_task_id,
        request.review_envelope.message_id,
        feedback_id="feedback-close-002",
    )

    result = coordinator.dispatch_runtime_message(feedback)
    decisions = runtime.state_store.list_phase3_runtime_records("normalized_decision_record", request.authority_wait_id)

    assert result.status == "feedback_rejected_closed"
    assert len(decisions) == 1
    runtime.close()


def test_hitl_05_invalid_actor_scope_or_linkage_is_rejected(tmp_path):
    runtime, coordinator, _ = _make_coordinator(tmp_path)
    request = _make_review_request(coordinator)
    coordinator.dispatch_runtime_message(_make_command(), review_request=request, resume_from_ref="resume://checkpoint-001")
    feedback = _make_feedback(
        request.authority_wait_id,
        "review-task-mismatch",
        request.review_envelope.message_id,
        reviewer_role="unauthorized-role",
        feedback_id="feedback-invalid-001",
    )

    result = coordinator.dispatch_runtime_message(feedback)

    assert result.status == "feedback_rejected_invalid"
    assert any("INVALID_REVIEW_TASK_LINKAGE" in error or "INVALID_FEEDBACK_ACTOR_SCOPE" in error for error in result.feedback.errors)
    runtime.close()


def test_hitl_06_review_task_cannot_publish_before_wait_persistence(tmp_path):
    runtime, coordinator, _ = _make_coordinator(tmp_path)

    with pytest.raises(KeyError):
        runtime.record_review_task_publication(
            authority_wait_id="wait-missing-001",
            review_task_message_id="review-msg-missing-001",
            review_task_id="review-task-missing-001",
            resume_from_ref="resume://missing",
        )
    runtime.close()


def test_hitl_07_publication_failure_records_durable_failure_evidence(tmp_path):
    runtime, coordinator, sink = _make_coordinator(tmp_path)
    sink.fail_next = "synthetic publish failure"
    request = _make_review_request(coordinator)

    result = coordinator.dispatch_runtime_message(
        request.review_envelope,
        review_request=request,
        resume_from_ref="resume://checkpoint-001",
    )
    stored_wait = runtime.state_store.get_authority_wait_state(request.authority_wait_id)

    assert result.status == "publication_failed"
    assert stored_wait is not None
    assert stored_wait.status == "publication_failed"
    runtime.close()


def test_hitl_08_duplicate_feedback_returns_prior_decision_without_second_resume(tmp_path):
    runtime, coordinator, _ = _make_coordinator(tmp_path)
    request = _make_review_request(coordinator)
    coordinator.dispatch_runtime_message(_make_command(), review_request=request, resume_from_ref="resume://checkpoint-001")
    feedback = _make_feedback(
        request.authority_wait_id,
        request.review_payload.review_task_id,
        request.review_envelope.message_id,
        feedback_id="feedback-dup-001",
    )
    first = coordinator.dispatch_runtime_message(feedback)
    duplicate = _make_feedback(
        request.authority_wait_id,
        request.review_payload.review_task_id,
        request.review_envelope.message_id,
        feedback_id="feedback-dup-001",
    )

    second = coordinator.dispatch_runtime_message(duplicate)
    resumes = runtime.state_store.list_phase3_runtime_records("bounded_resume_request_record", request.authority_wait_id)

    assert first.feedback.decision is not None
    assert second.status == "feedback_accepted_duplicate"
    assert second.feedback.decision.decision_id == first.feedback.decision.decision_id
    assert len(resumes) == 1
    runtime.close()


def test_hitl_09_timeout_dispatch_records_evidence_and_deactivates_wait(tmp_path):
    runtime, coordinator, _ = _make_coordinator(tmp_path)
    request = _make_review_request(coordinator, due_at=_past_iso())
    coordinator.dispatch_runtime_message(_make_command(), review_request=request, resume_from_ref="resume://checkpoint-001")

    result = runtime.scan_timeouts()
    stored_wait = runtime.state_store.get_authority_wait_state(request.authority_wait_id)
    evidence = runtime.state_store.list_phase3_runtime_records("timeout_dispatch_evidence_record", request.authority_wait_id)

    assert len(result.authority_wait_timeout_envelopes) == 1
    assert evidence
    assert stored_wait is not None
    assert stored_wait.status == "timed_out"
    assert runtime.state_store.find_active_authority_wait("wf-phase3-001", "checkpoint-001", "gate-001") is None
    runtime.close()


def test_hitl_10_retry_dispatch_records_bounded_intent_and_linkage(tmp_path):
    runtime, coordinator, _ = _make_coordinator(tmp_path)
    command = _make_command()
    retry = coordinator.build_retry_message(
        original_envelope=command,
        target_subject="agent.maverick.inbox",
        retry_count=1,
        max_retries=3,
        retry_reason="bounded_phase3_test",
        last_error="synthetic",
    )

    result = coordinator.dispatch_runtime_message(retry)
    assert result.status == "retry_recorded"
    runtime.close()


def test_hitl_11_dead_letter_dispatch_records_reviewable_evidence(tmp_path):
    runtime, coordinator, _ = _make_coordinator(tmp_path)
    command = _make_command()
    dead = coordinator.build_dead_letter_message(
        original_envelope=command,
        attempts_exhausted=3,
        dead_letter_reason="bounded_phase3_test",
        last_error="synthetic",
    )

    result = coordinator.dispatch_runtime_message(dead)
    assert result.status == "dead_letter_recorded"
    runtime.close()
