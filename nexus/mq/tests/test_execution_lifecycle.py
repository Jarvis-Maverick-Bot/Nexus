from datetime import datetime, timedelta, timezone
import os

from nexus.mq.coordination_runtime import CoordinationRuntime
from nexus.mq.execution_lifecycle import ExecutionLifecycleCoordinator
from nexus.mq.message_contracts import build_execution_envelope
from nexus.mq.payloads import CommandMessagePayload, FeedbackMessagePayload


def _identity_config_path() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "agents.yaml")
    )


def _future_iso(minutes: int = 5) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def _make_runtime(tmp_path, runtime_id: str, agent_id: str, role: str) -> CoordinationRuntime:
    runtime = CoordinationRuntime.from_paths(
        runtime_id=runtime_id,
        agent_id=agent_id,
        role=role,
        db_path=tmp_path / f"{runtime_id}.sqlite3",
        identity_yaml_path=_identity_config_path(),
    )
    runtime.startup()
    return runtime


def test_create_review_request_persists_wait_and_builds_review_message(tmp_path):
    runtime = _make_runtime(tmp_path, "maverick-runtime-001", "maverick", "maverick")
    coordinator = ExecutionLifecycleCoordinator(runtime)

    result = coordinator.create_review_request(
        workflow_instance_id="wf-review-001",
        workflow_type="delivery",
        workflow_version="0.3",
        checkpoint_id="checkpoint-001",
        gate_id="gate-001",
        requested_actor_role="reviewer",
        review_target_ref="artifact://draft-001",
        review_type="formal_review",
        required_context_refs=["ctx://1"],
        display_summary="Please review this draft.",
        source_agent_id="maverick",
        source_runtime_instance_id="maverick-windows-main-20260507",
        source_role="maverick",
        authority_scope="workflow.review.request",
        target_agent_id="viper",
        reply_to_subject="agent.maverick.callbacks",
        evidence_package_id="pkg-001",
        due_at=_future_iso(),
    )
    stored_wait = runtime.state_store.get_authority_wait_state(result.authority_wait_id)
    runtime.close()

    assert result.review_envelope.message_type == "Review_Task"
    assert result.review_envelope.correlation_id == result.authority_wait_id
    assert stored_wait is not None
    assert stored_wait.review_task_message_id == result.review_envelope.message_id


def test_finalize_success_emits_business_message_after_commit(tmp_path):
    runtime = _make_runtime(tmp_path, "maverick-runtime-002", "maverick", "maverick")
    coordinator = ExecutionLifecycleCoordinator(runtime)
    command = build_execution_envelope(
        message_type="Command_Message",
        workflow_instance_id="wf-success-001",
        workflow_type="delivery",
        workflow_version="0.3",
        producer="maverick",
        payload=CommandMessagePayload(
            command_name="dispatch",
            target_handler="runtime.dispatch",
            completion_event_type="command.dispatched",
        ),
        source_agent_id="maverick",
        source_runtime_instance_id="maverick-windows-main-20260507",
        source_role="maverick",
        authority_scope="workflow.command",
        target_agent_id="viper",
        reply_to_subject="agent.maverick.callbacks",
    )

    result = coordinator.finalize_success(
        command_envelope=command,
        evidence_refs=["evidence://dispatch-001"],
        previous_state="queued",
        new_state="processing",
        artifact_refs=["artifact://dispatch-plan-001"],
    )
    runtime.close()

    assert result.commit_result.accepted is True
    assert result.business_envelope.message_type == "Business_Message"
    assert result.business_envelope.causation_id == command.message_id
    assert result.business_envelope.payload.new_state == "processing"


def test_evaluate_hitl_outcome_routes_revise_to_return_package(tmp_path):
    runtime = _make_runtime(tmp_path, "maverick-runtime-003", "maverick", "maverick")
    coordinator = ExecutionLifecycleCoordinator(runtime)
    review = coordinator.create_review_request(
        workflow_instance_id="wf-hitl-003",
        workflow_type="delivery",
        workflow_version="0.3",
        checkpoint_id="checkpoint-003",
        gate_id="gate-003",
        requested_actor_role="reviewer",
        review_target_ref="artifact://draft-003",
        review_type="formal_review",
        required_context_refs=["ctx://3"],
        display_summary="Review gate 003",
        source_agent_id="maverick",
        source_runtime_instance_id="maverick-windows-main-20260507",
        source_role="maverick",
        authority_scope="workflow.review.request",
        target_agent_id="viper",
        reply_to_subject="agent.maverick.callbacks",
        evidence_package_id="pkg-003",
        due_at=_future_iso(),
    )
    feedback = build_execution_envelope(
        message_type="Feedback_Message",
        workflow_instance_id="wf-hitl-003",
        workflow_type="hitl",
        workflow_version="0.3",
        producer="viper",
        payload=FeedbackMessagePayload(
            feedback_id="feedback-003",
            review_task_id=review.review_payload.review_task_id,
            authority_wait_id=review.authority_wait_id,
            reviewer_actor_id="viper",
            reviewer_role="viper",
            action="Revise",
            feedback_text="Need more evidence.",
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
    result = coordinator.evaluate_hitl_outcome(
        authority_wait_id=review.authority_wait_id,
        workflow_id="workflow-hitl-003",
        workflow_version="0.3",
        artifact_ref="artifact://draft-003",
        artifact_version="1",
        judgment_actor_id="maverick",
        judgment_actor_role="maverick",
        authority_basis_ref="authority://gate-003",
        evidence_package_id="pkg-003",
        current_state="in_review",
    )
    runtime.close()

    assert receive.valid is True
    assert result.judgment.outcome == "revise"
    assert result.route.gate_return_package is not None
    assert result.route.state_transition_request is None


def test_build_retry_and_dead_letter_messages_keep_correlation_chain(tmp_path):
    runtime = _make_runtime(tmp_path, "maverick-runtime-004", "maverick", "maverick")
    coordinator = ExecutionLifecycleCoordinator(runtime)
    command = build_execution_envelope(
        message_type="Command_Message",
        workflow_instance_id="wf-retry-dlq-004",
        workflow_type="delivery",
        workflow_version="0.3",
        producer="maverick",
        payload=CommandMessagePayload(
            command_name="dispatch",
            target_handler="runtime.dispatch",
            completion_event_type="command.dispatched",
        ),
        source_agent_id="maverick",
        source_runtime_instance_id="maverick-windows-main-20260507",
        source_role="maverick",
        authority_scope="workflow.command",
        target_agent_id="viper",
        reply_to_subject="agent.maverick.callbacks",
    )
    retry = coordinator.build_retry_message(
        original_envelope=command,
        target_subject="agent.viper.inbox",
        retry_count=1,
        max_retries=3,
        retry_reason="temporary_transport_error",
        last_error="timeout",
    )
    dead_letter = coordinator.build_dead_letter_message(
        original_envelope=command,
        attempts_exhausted=3,
        dead_letter_reason="retries_exhausted",
        last_error="timeout",
    )
    runtime.close()

    assert retry.correlation_id == command.correlation_id
    assert retry.causation_id == command.message_id
    assert dead_letter.correlation_id == command.correlation_id
    assert dead_letter.causation_id == command.message_id
