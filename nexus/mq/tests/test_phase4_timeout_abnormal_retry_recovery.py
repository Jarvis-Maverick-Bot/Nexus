from datetime import datetime, timedelta, timezone
import os

from nexus.mq.coordination_runtime import CoordinationRuntime, RECOVERY_STATES
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
        runtime_id="maverick-runtime-phase4",
        agent_id="maverick",
        role="maverick",
        db_path=tmp_path / "phase4.sqlite3",
        identity_yaml_path=_identity_config_path(),
    )
    runtime.startup()
    return runtime


def _make_coordinator(tmp_path):
    runtime = _make_runtime(tmp_path)
    sink = SyntheticReviewTaskSink()
    return runtime, ExecutionLifecycleCoordinator(runtime, review_sink=sink)


def _make_command(**overrides):
    return build_execution_envelope(
        message_type="Command_Message",
        workflow_instance_id=overrides.pop("workflow_instance_id", "wf-phase4-001"),
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
        correlation_id=overrides.pop("correlation_id", "corr-phase4-command"),
        idempotency_key=overrides.pop("idempotency_key", "idem-phase4-command"),
        expires_at=_future_iso(),
    )


def _make_review_request(coordinator: ExecutionLifecycleCoordinator, due_at: str | None = None):
    return coordinator.create_review_request(
        workflow_instance_id="wf-phase4-001",
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
        workflow_instance_id="wf-phase4-001",
        workflow_type="hitl",
        workflow_version="0.3",
        producer="viper",
        payload=FeedbackMessagePayload(
            feedback_id=overrides.pop("feedback_id", "feedback-phase4-001"),
            review_task_id=review_task_id,
            authority_wait_id=authority_wait_id,
            reviewer_actor_id="viper",
            reviewer_role="viper",
            action=overrides.pop("action", "Approve"),
            feedback_text=overrides.pop("feedback_text", None),
            submitted_at=datetime.now(timezone.utc).isoformat(),
        ),
        source_agent_id="viper",
        source_runtime_instance_id="viper-windows-main-20260507",
        source_role="viper",
        authority_scope="workflow.feedback",
        target_agent_id="maverick",
        reply_to_subject="agent.maverick.callbacks",
        correlation_id=overrides.pop("correlation_id", authority_wait_id),
        causation_id=overrides.pop("causation_id", causation_id),
        expires_at=overrides.pop("expires_at", _future_iso()),
    )


def _published_review(tmp_path, due_at: str | None = None):
    runtime, coordinator = _make_coordinator(tmp_path)
    request = _make_review_request(coordinator, due_at=due_at)
    coordinator.dispatch_runtime_message(_make_command(), review_request=request, resume_from_ref="resume://checkpoint-001")
    return runtime, coordinator, request


def test_p4_01_overdue_wait_creates_one_timeout_record_idempotently(tmp_path):
    runtime, _, request = _published_review(tmp_path, due_at=_past_iso())

    first = runtime.scan_timeouts()
    second = runtime.scan_timeouts()
    timeout_records = runtime.state_store.list_phase3_runtime_records("timeout_record", request.authority_wait_id)
    dispatch_records = runtime.state_store.list_phase3_runtime_records("timeout_dispatch_evidence_record", request.authority_wait_id)
    runtime.close()

    assert len(first.authority_wait_timeout_envelopes) == 1
    assert second.authority_wait_timeout_envelopes == []
    assert len(timeout_records) == 1
    assert len(dispatch_records) == 1
    assert timeout_records[0].payload["authority_wait_id"] == request.authority_wait_id


def test_p4_02_feedback_after_timeout_is_stale_without_decision_or_resume(tmp_path):
    runtime, coordinator, request = _published_review(tmp_path, due_at=_past_iso())
    runtime.scan_timeouts()
    feedback = _make_feedback(request.authority_wait_id, request.review_payload.review_task_id, request.review_envelope.message_id)

    result = coordinator.dispatch_runtime_message(feedback)
    stale = runtime.state_store.list_phase3_runtime_records("stale_feedback_rejection_record", request.authority_wait_id)
    decisions = runtime.state_store.list_phase3_runtime_records("normalized_decision_record", request.authority_wait_id)
    resumes = runtime.state_store.list_phase3_runtime_records("bounded_resume_request_record", request.authority_wait_id)
    runtime.close()

    assert result.status == "feedback_rejected_stale"
    assert stale
    assert decisions == []
    assert resumes == []


def test_p4_03_feedback_after_closed_or_superseded_wait_does_not_reopen_state(tmp_path):
    runtime, coordinator, request = _published_review(tmp_path)
    wait = runtime._require_wait(request.authority_wait_id)
    wait.status = "superseded"
    runtime._persist_authority_wait_state(wait)
    feedback = _make_feedback(request.authority_wait_id, request.review_payload.review_task_id, request.review_envelope.message_id)

    result = coordinator.dispatch_runtime_message(feedback)
    stored = runtime.state_store.get_authority_wait_state(request.authority_wait_id)
    stale = runtime.state_store.list_phase3_runtime_records("stale_feedback_rejection_record", request.authority_wait_id)
    runtime.close()

    assert result.status == "feedback_rejected_stale"
    assert stored is not None
    assert stored.status == "superseded"
    assert stale[0].payload["reason"] == "authority_wait_state_superseded"


def test_p4_04_retry_policy_separates_broker_local_and_application_paths(tmp_path):
    runtime = _make_runtime(tmp_path)

    broker = runtime.evaluate_retry_policy(
        failure_class="IF-04",
        message_family="Feedback_Message",
        attempt_count=1,
        max_attempts=3,
        retry_actor="broker_pre_ack",
    )
    local = runtime.evaluate_retry_policy(
        failure_class="mechanism_stall",
        message_family="Command_Message",
        attempt_count=1,
        max_attempts=3,
        retry_actor="local_post_ack",
    )
    app = runtime.evaluate_retry_policy(
        failure_class="mechanism_stall",
        message_family="Command_Message",
        attempt_count=1,
        max_attempts=3,
        retry_actor="application_retry_message",
    )
    runtime.close()

    assert broker["path"] == "broker_retry"
    assert local["path"] == "local_recovery"
    assert app["path"] == "application_retry_message"


def test_p4_05_retry_attempt_limits_are_enforced(tmp_path):
    runtime = _make_runtime(tmp_path)

    decision = runtime.record_retry_decision(
        original_message_id="msg-retry-limit-001",
        original_idempotency_key="idem-retry-limit-001",
        workflow_instance_id="wf-phase4-001",
        message_family="Timeout_Message",
        failure_class="IF-04",
        attempt_count=3,
        max_attempts=3,
        retry_actor="application_retry_message",
        failure_cause="timeout exhausted",
    )
    dlq = runtime.state_store.list_phase3_runtime_records("dead_letter_record")
    retry_outbox = runtime.state_store.list_phase3_runtime_records("retry_outbox_record")
    runtime.close()

    assert decision.status == "dlq_recorded"
    assert len(dlq) == 1
    assert retry_outbox == []


def test_p4_06_dlq_eligible_failure_creates_durable_dlq_evidence(tmp_path):
    runtime, coordinator = _make_coordinator(tmp_path)
    command = _make_command(idempotency_key="idem-dlq-001")
    dead = coordinator.build_dead_letter_message(
        original_envelope=command,
        attempts_exhausted=3,
        dead_letter_reason="bounded_phase4_test",
        last_error="retry exhausted",
    )

    result = coordinator.dispatch_runtime_message(dead)
    dlq = runtime.state_store.list_phase3_runtime_records("dead_letter_record")
    dispatch = runtime.state_store.list_phase3_runtime_records("dead_letter_dispatch_evidence_record")
    runtime.close()

    assert result.status == "dead_letter_recorded"
    assert len(dlq) == 1
    assert len(dispatch) == 1
    assert dlq[0].status == "dlq_recorded"


def test_p4_07_terminal_abnormal_records_use_taxonomy_and_block_progress(tmp_path):
    runtime = _make_runtime(tmp_path)

    runtime.record_terminal_abnormal(
        dedupe_key="terminal:test:001",
        workflow_instance_id="wf-phase4-001",
        error_event_id="P4-07:msg-001",
        error_class="mechanism_stall",
        affected_ref="msg-001",
        failure_cause="retry exhausted",
    )
    terminal = runtime.state_store.list_phase3_runtime_records("terminal_abnormal_record")
    unresolved = runtime.state_store.list_unresolved_abnormal_states("wf-phase4-001")
    runtime.close()

    assert terminal[0].payload["abnormal_class"] == "mechanism_stall"
    assert terminal[0].payload["blocking_expectation"] == "blocks_business_progress_while_active"
    assert unresolved[0].abnormal_class == "mechanism_stall"


def test_p4_08_handler_exhausted_is_governed_quarantine_not_broker_dlq(tmp_path):
    runtime = _make_runtime(tmp_path)
    command = _make_command(idempotency_key="idem-handler-exhausted-001")
    runtime.intake_inbound_message("agent.maverick.inbox", command.to_dict())

    runtime.record_post_ack_handler_failure(command.message_id, "dispatch failure 1")
    runtime.record_post_ack_handler_failure(command.message_id, "dispatch failure 2")
    exhausted = runtime.record_post_ack_handler_failure(command.message_id, "dispatch failure 3")
    handler_records = runtime.state_store.list_phase3_runtime_records("handler_exhausted_record")
    dlq = runtime.state_store.list_phase3_runtime_records("dead_letter_record")
    runtime.close()

    assert exhausted.state == "handler_exhausted"
    assert handler_records[0].payload["dlq_subject_involved"] is False
    assert dlq == []


def test_p4_09_startup_reconciliation_records_recoverable_candidates_idempotently(tmp_path):
    runtime = _make_runtime(tmp_path)
    command = _make_command(idempotency_key="idem-recovery-001")
    runtime.intake_inbound_message("agent.maverick.inbox", command.to_dict())
    runtime.mark_intake_handler_running(command.message_id)

    first = runtime.reconcile_phase4_recovery()
    second = runtime.reconcile_phase4_recovery()
    actions = runtime.state_store.list_phase3_runtime_records("recovery_action_record")
    runtime.close()

    assert first.status == "recovery_unresolved"
    assert second.record_id == first.record_id
    assert len(actions) == 1
    assert actions[0].payload["recovery_state"] == "handler_running"


def test_p4_10_startup_reconciliation_does_not_release_handler_exhausted(tmp_path):
    runtime = _make_runtime(tmp_path)
    command = _make_command(idempotency_key="idem-recovery-exhausted-001")
    runtime.intake_inbound_message("agent.maverick.inbox", command.to_dict())
    runtime.record_post_ack_handler_failure(command.message_id, "dispatch failure 1")
    runtime.record_post_ack_handler_failure(command.message_id, "dispatch failure 2")
    runtime.record_post_ack_handler_failure(command.message_id, "dispatch failure 3")

    runtime.reconcile_phase4_recovery()
    inbox = runtime.state_store.get_envelope_inbox(command.message_id)
    actions = runtime.state_store.list_phase3_runtime_records("recovery_action_record")
    runtime.close()

    assert inbox is not None
    assert inbox.state == "handler_exhausted"
    assert actions == []


def test_p4_11_integrated_path_preserves_evidence_without_false_business_completion(tmp_path):
    runtime, coordinator, request = _published_review(tmp_path, due_at=_past_iso())
    runtime.scan_timeouts()
    feedback = _make_feedback(request.authority_wait_id, request.review_payload.review_task_id, request.review_envelope.message_id)
    coordinator.dispatch_runtime_message(feedback)
    retry = coordinator.build_retry_message(
        original_envelope=_make_command(idempotency_key="idem-integrated-original"),
        target_subject="agent.maverick.inbox",
        retry_count=1,
        max_retries=3,
        retry_reason="timeout_retry",
        last_error="timeout",
    )
    coordinator.dispatch_runtime_message(retry)

    timeout_records = runtime.state_store.list_phase3_runtime_records("timeout_record", request.authority_wait_id)
    stale_records = runtime.state_store.list_phase3_runtime_records("stale_feedback_rejection_record", request.authority_wait_id)
    retry_records = runtime.state_store.list_phase3_runtime_records("retry_decision_record")
    business_records = runtime.state_store.list_phase3_runtime_records("business_completion_record")
    runtime.close()

    assert timeout_records
    assert stale_records
    assert retry_records[0].status == "retry_queued"
    assert business_records == []
    assert "handler_exhausted" in RECOVERY_STATES
