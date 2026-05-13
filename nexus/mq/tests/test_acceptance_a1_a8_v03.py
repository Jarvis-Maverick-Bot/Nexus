from datetime import datetime, timedelta, timezone
import os

from nexus.mq.adapter import MqAdapterStub
from nexus.mq.coordination_runtime import CoordinationRuntime
from nexus.mq.execution_lifecycle import ExecutionLifecycleCoordinator
from nexus.mq.listener_runtime import ListenerRuntime
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


def _make_runtime(tmp_path, runtime_id: str, agent_id: str, role: str, db_name: str | None = None) -> CoordinationRuntime:
    runtime = CoordinationRuntime.from_paths(
        runtime_id=runtime_id,
        agent_id=agent_id,
        role=role,
        db_path=tmp_path / (db_name or f"{runtime_id}.sqlite3"),
        identity_yaml_path=_identity_config_path(),
    )
    runtime.startup()
    return runtime


def _make_command(
    workflow_instance_id: str,
    source_agent_id: str,
    source_runtime_instance_id: str,
    source_role: str,
    target_agent_id: str,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> object:
    return build_execution_envelope(
        message_type="Command_Message",
        workflow_instance_id=workflow_instance_id,
        workflow_type="delivery",
        workflow_version="0.3",
        producer=source_agent_id,
        payload=CommandMessagePayload(
            command_name="dispatch",
            target_handler="runtime.dispatch",
            completion_event_type="command.dispatched",
        ),
        source_agent_id=source_agent_id,
        source_runtime_instance_id=source_runtime_instance_id,
        source_role=source_role,
        authority_scope="workflow.command",
        target_agent_id=target_agent_id,
        reply_to_subject=f"agent.{source_agent_id}.callbacks",
        expires_at=_future_iso(),
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )


def test_a1_direct_command_to_business_progress(tmp_path):
    runtime = _make_runtime(tmp_path, "viper-runtime-a1", "viper", "viper")
    coordinator = ExecutionLifecycleCoordinator(runtime)
    command = _make_command(
        workflow_instance_id="wf-a1-001",
        source_agent_id="maverick",
        source_runtime_instance_id="maverick-windows-main-20260507",
        source_role="maverick",
        target_agent_id="viper",
    )

    intake = runtime.intake_inbound_message("agent.viper.inbox", command.to_dict())
    runtime.mark_task_completed(
        task_id=f"task-{command.message_id}",
        idempotency_key=command.idempotency_key,
        message_id=command.message_id,
        workflow_id=command.workflow_instance_id,
        result_payload={"status": "ok"},
    )
    success = coordinator.finalize_success(
        command_envelope=command,
        evidence_refs=["evidence://a1"],
        previous_state="queued",
        new_state="processing",
    )
    runtime.close()

    assert intake.valid is True
    assert intake.ack_allowed is True
    assert success.business_envelope.message_type == "Business_Message"
    assert success.business_envelope.causation_id == command.message_id


def test_a2_feedback_approve_routes_to_transition_ready(tmp_path):
    runtime = _make_runtime(tmp_path, "maverick-runtime-a2", "maverick", "maverick")
    coordinator = ExecutionLifecycleCoordinator(runtime)
    review = coordinator.create_review_request(
        workflow_instance_id="wf-a2-001",
        workflow_type="delivery",
        workflow_version="0.3",
        checkpoint_id="checkpoint-a2",
        gate_id="gate-a2",
        requested_actor_role="reviewer",
        review_target_ref="artifact://a2",
        review_type="formal_review",
        required_context_refs=["ctx://a2"],
        display_summary="approve this",
        source_agent_id="maverick",
        source_runtime_instance_id="maverick-windows-main-20260507",
        source_role="maverick",
        authority_scope="workflow.review.request",
        target_agent_id="viper",
        reply_to_subject="agent.maverick.callbacks",
    )
    coordinator.publish_review_request(review, resume_from_ref="resume://a2")
    feedback = build_execution_envelope(
        message_type="Feedback_Message",
        workflow_instance_id="wf-a2-001",
        workflow_type="hitl",
        workflow_version="0.3",
        producer="viper",
        payload=FeedbackMessagePayload(
            feedback_id="fb-a2",
            review_task_id=review.review_payload.review_task_id,
            authority_wait_id=review.authority_wait_id,
            reviewer_actor_id="viper",
            reviewer_role="viper",
            action="Approve",
            submitted_at=datetime.now(timezone.utc).isoformat(),
        ),
        source_agent_id="viper",
        source_runtime_instance_id="viper-windows-main-20260507",
        source_role="viper",
        authority_scope="workflow.feedback",
        target_agent_id="maverick",
        reply_to_subject="agent.maverick.callbacks",
        correlation_id=review.authority_wait_id,
        causation_id=review.review_envelope.message_id,
    )
    receive = runtime.receive_feedback("agent.maverick.callbacks", feedback.to_dict())
    outcome = coordinator.evaluate_hitl_outcome(
        authority_wait_id=review.authority_wait_id,
        workflow_id="workflow-a2",
        workflow_version="0.3",
        artifact_ref="artifact://a2",
        artifact_version="1",
        judgment_actor_id="maverick",
        judgment_actor_role="maverick",
        authority_basis_ref="authority://a2",
        evidence_package_id="pkg://a2",
        current_state="in_review",
    )
    runtime.close()

    assert receive.valid is True
    assert outcome.judgment.outcome == "pass"
    assert outcome.route.state_transition_request is not None


def test_a3_feedback_revise_routes_to_return_package(tmp_path):
    runtime = _make_runtime(tmp_path, "maverick-runtime-a3", "maverick", "maverick")
    coordinator = ExecutionLifecycleCoordinator(runtime)
    review = coordinator.create_review_request(
        workflow_instance_id="wf-a3-001",
        workflow_type="delivery",
        workflow_version="0.3",
        checkpoint_id="checkpoint-a3",
        gate_id="gate-a3",
        requested_actor_role="reviewer",
        review_target_ref="artifact://a3",
        review_type="formal_review",
        required_context_refs=["ctx://a3"],
        display_summary="revise this",
        source_agent_id="maverick",
        source_runtime_instance_id="maverick-windows-main-20260507",
        source_role="maverick",
        authority_scope="workflow.review.request",
        target_agent_id="viper",
        reply_to_subject="agent.maverick.callbacks",
    )
    coordinator.publish_review_request(review, resume_from_ref="resume://a3")
    feedback = build_execution_envelope(
        message_type="Feedback_Message",
        workflow_instance_id="wf-a3-001",
        workflow_type="hitl",
        workflow_version="0.3",
        producer="viper",
        payload=FeedbackMessagePayload(
            feedback_id="fb-a3",
            review_task_id=review.review_payload.review_task_id,
            authority_wait_id=review.authority_wait_id,
            reviewer_actor_id="viper",
            reviewer_role="viper",
            action="Revise",
            feedback_text="needs updates",
            submitted_at=datetime.now(timezone.utc).isoformat(),
        ),
        source_agent_id="viper",
        source_runtime_instance_id="viper-windows-main-20260507",
        source_role="viper",
        authority_scope="workflow.feedback",
        target_agent_id="maverick",
        reply_to_subject="agent.maverick.callbacks",
        correlation_id=review.authority_wait_id,
        causation_id=review.review_envelope.message_id,
    )
    runtime.receive_feedback("agent.maverick.callbacks", feedback.to_dict())
    outcome = coordinator.evaluate_hitl_outcome(
        authority_wait_id=review.authority_wait_id,
        workflow_id="workflow-a3",
        workflow_version="0.3",
        artifact_ref="artifact://a3",
        artifact_version="1",
        judgment_actor_id="maverick",
        judgment_actor_role="maverick",
        authority_basis_ref="authority://a3",
        evidence_package_id="pkg://a3",
        current_state="in_review",
    )
    runtime.close()

    assert outcome.judgment.outcome == "revise"
    assert outcome.route.gate_return_package is not None


def test_a4_feedback_reject_routes_to_blocked_return_package(tmp_path):
    runtime = _make_runtime(tmp_path, "maverick-runtime-a4", "maverick", "maverick")
    coordinator = ExecutionLifecycleCoordinator(runtime)
    review = coordinator.create_review_request(
        workflow_instance_id="wf-a4-001",
        workflow_type="delivery",
        workflow_version="0.3",
        checkpoint_id="checkpoint-a4",
        gate_id="gate-a4",
        requested_actor_role="reviewer",
        review_target_ref="artifact://a4",
        review_type="formal_review",
        required_context_refs=["ctx://a4"],
        display_summary="reject this",
        source_agent_id="maverick",
        source_runtime_instance_id="maverick-windows-main-20260507",
        source_role="maverick",
        authority_scope="workflow.review.request",
        target_agent_id="viper",
        reply_to_subject="agent.maverick.callbacks",
    )
    coordinator.publish_review_request(review, resume_from_ref="resume://a4")
    feedback = build_execution_envelope(
        message_type="Feedback_Message",
        workflow_instance_id="wf-a4-001",
        workflow_type="hitl",
        workflow_version="0.3",
        producer="viper",
        payload=FeedbackMessagePayload(
            feedback_id="fb-a4",
            review_task_id=review.review_payload.review_task_id,
            authority_wait_id=review.authority_wait_id,
            reviewer_actor_id="viper",
            reviewer_role="viper",
            action="Reject",
            submitted_at=datetime.now(timezone.utc).isoformat(),
        ),
        source_agent_id="viper",
        source_runtime_instance_id="viper-windows-main-20260507",
        source_role="viper",
        authority_scope="workflow.feedback",
        target_agent_id="maverick",
        reply_to_subject="agent.maverick.callbacks",
        correlation_id=review.authority_wait_id,
        causation_id=review.review_envelope.message_id,
    )
    runtime.receive_feedback("agent.maverick.callbacks", feedback.to_dict())
    outcome = coordinator.evaluate_hitl_outcome(
        authority_wait_id=review.authority_wait_id,
        workflow_id="workflow-a4",
        workflow_version="0.3",
        artifact_ref="artifact://a4",
        artifact_version="1",
        judgment_actor_id="maverick",
        judgment_actor_role="maverick",
        authority_basis_ref="authority://a4",
        evidence_package_id="pkg://a4",
        current_state="in_review",
    )
    runtime.close()

    assert outcome.judgment.outcome == "blocked"
    assert outcome.route.gate_return_package is not None


def test_a5_duplicate_delivery_is_deduped(tmp_path):
    runtime = _make_runtime(tmp_path, "viper-runtime-a5", "viper", "viper")
    command = _make_command(
        workflow_instance_id="wf-a5-001",
        source_agent_id="maverick",
        source_runtime_instance_id="maverick-windows-main-20260507",
        source_role="maverick",
        target_agent_id="viper",
        correlation_id="corr-a5",
        idempotency_key="idem-a5",
    )
    first = runtime.intake_inbound_message("agent.viper.inbox", command.to_dict())
    runtime.mark_task_completed(
        task_id=f"task-{command.message_id}",
        idempotency_key=command.idempotency_key,
        message_id=command.message_id,
        workflow_id=command.workflow_instance_id,
        result_payload={"status": "ok"},
    )
    duplicate = runtime.intake_inbound_message("agent.viper.inbox", command.to_dict())
    runtime.close()

    assert first.valid is True and first.duplicate is False
    assert duplicate.valid is True and duplicate.duplicate is True
    assert duplicate.ack_allowed is True


def test_a6_timeout_and_no_response_escalation(tmp_path):
    runtime = _make_runtime(tmp_path, "maverick-runtime-a6", "maverick", "maverick")
    wait = runtime.create_authority_wait_state(
        workflow_instance_id="wf-a6-001",
        checkpoint_id="checkpoint-a6",
        gate_id="gate-a6",
        requested_actor_role="reviewer",
        due_at=_past_iso(),
    )
    runtime.register_review_task_message(wait.authority_wait_id, "review-msg-a6")
    result = runtime.scan_timeouts()
    runtime.close()

    assert len(result.authority_wait_timeout_envelopes) == 1
    assert result.authority_wait_timeout_envelopes[0].payload.timeout_scope == "authority_wait"


def test_a7_restart_recovery_rehydrates_wait_and_reconciles_outbox(tmp_path):
    db_name = "shared-a7.sqlite3"
    runtime = _make_runtime(tmp_path, "maverick-runtime-a7", "maverick", "maverick", db_name=db_name)
    wait = runtime.create_authority_wait_state(
        workflow_instance_id="wf-a7-001",
        checkpoint_id="checkpoint-a7",
        gate_id="gate-a7",
        requested_actor_role="reviewer",
        due_at=_future_iso(),
    )
    runtime.register_review_task_message(wait.authority_wait_id, "review-msg-a7")
    command = _make_command(
        workflow_instance_id="wf-a7-001",
        source_agent_id="maverick",
        source_runtime_instance_id="maverick-windows-main-20260507",
        source_role="maverick",
        target_agent_id="viper",
    )
    outbox = runtime.record_outbox_publish(command)
    runtime.close()

    adapter = MqAdapterStub()
    listener = ListenerRuntime.from_paths(
        adapter=adapter,
        runtime_id="maverick-runtime-a7b",
        agent_id="maverick",
        role="maverick",
        db_path=tmp_path / db_name,
        identity_yaml_path=_identity_config_path(),
    )
    startup = listener.startup()
    replayed = adapter.consume()
    stored_wait = listener.runtime.state_store.get_authority_wait_state(wait.authority_wait_id)
    listener.close()

    assert startup.runtime_status == "ACTIVE"
    assert startup.recovered_callback_waits >= 0
    assert startup.recovered_pending_tasks >= 0
    assert replayed is not None
    assert stored_wait is not None
    assert stored_wait.review_task_message_id == "review-msg-a7"


def test_a8_consumer_rejects_wrong_target_even_if_subject_seen(tmp_path):
    runtime = _make_runtime(tmp_path, "viper-runtime-a8", "viper", "viper")
    command = _make_command(
        workflow_instance_id="wf-a8-001",
        source_agent_id="maverick",
        source_runtime_instance_id="maverick-windows-main-20260507",
        source_role="maverick",
        target_agent_id="maverick",
    )
    result = runtime.intake_inbound_message("agent.viper.inbox", command.to_dict())
    runtime.close()

    assert result.valid is False
    assert result.ack_allowed is False
    assert any("INVALID_TARGET_AGENT" in error for error in result.errors)
