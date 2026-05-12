from datetime import datetime, timedelta, timezone
import os

from nexus.mq.adapter import MqAdapterStub
from nexus.mq.coordination_runtime import CoordinationRuntime
from nexus.mq.listener_runtime import ListenerRuntime
from nexus.mq.message_contracts import build_execution_envelope
from nexus.mq.payloads import CommandMessagePayload, FeedbackMessagePayload, ReviewTaskPayload


def _identity_config_path() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "agents.yaml")
    )


def _future_iso(minutes: int = 5) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def _past_iso(minutes: int = 5) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def _make_runtime(tmp_path, runtime_id: str, agent_id: str, role: str) -> CoordinationRuntime:
    return CoordinationRuntime.from_paths(
        runtime_id=runtime_id,
        agent_id=agent_id,
        role=role,
        db_path=tmp_path / f"{runtime_id}.sqlite3",
        identity_yaml_path=_identity_config_path(),
    )


def test_execution_command_intake_persists_before_ack(tmp_path):
    adapter = MqAdapterStub()
    runtime = _make_runtime(tmp_path, "viper-runtime-001", "viper", "viper")
    listener = ListenerRuntime(adapter, runtime)
    listener.startup()

    command = build_execution_envelope(
        message_type="Command_Message",
        workflow_instance_id="wf-exec-001",
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
        expires_at=_future_iso(),
    )
    adapter.publish(command.to_dict())

    result = listener.poll_once()
    stored = runtime.state_store.get_pending_task(f"task-{command.message_id}")
    inbox = runtime.state_store.get_envelope_inbox(command.message_id)
    listener.close()

    assert result.status == "command_intake"
    assert result.acked is True
    assert stored is not None
    assert inbox is not None
    assert stored.input_payload["message_id"] == command.message_id


def test_review_task_feedback_normalization_uses_wait_state_correlation(tmp_path):
    runtime = _make_runtime(tmp_path, "maverick-runtime-001", "maverick", "maverick")
    runtime.startup()
    wait = runtime.create_authority_wait_state(
        workflow_instance_id="wf-hitl-001",
        checkpoint_id="checkpoint-001",
        gate_id="gate-001",
        requested_actor_role="reviewer",
        due_at=_future_iso(),
    )
    review_payload = runtime.hitl_lifecycle.build_review_task_payload(
        authority_wait=wait,
        review_target_ref="artifact://draft-001",
        review_type="formal_review",
        required_context_refs=["ctx://1"],
        display_summary="Please review the draft.",
    )
    review_message_id = "review-msg-001"
    runtime.register_review_task_message(wait.authority_wait_id, review_message_id)

    feedback = build_execution_envelope(
        message_type="Feedback_Message",
        workflow_instance_id="wf-hitl-001",
        workflow_type="hitl",
        workflow_version="0.3",
        producer="viper",
        payload=FeedbackMessagePayload(
            feedback_id="feedback-001",
            review_task_id=review_payload.review_task_id,
            authority_wait_id=wait.authority_wait_id,
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
        correlation_id=wait.authority_wait_id,
        causation_id=review_message_id,
    )

    result = runtime.receive_feedback("agent.maverick.callbacks", feedback.to_dict())
    stored_wait = runtime.state_store.get_authority_wait_state(wait.authority_wait_id)
    stored_decision = runtime.state_store.get_hitl_decision_record(result.decision.decision_id) if result.decision else None
    runtime.close()

    assert result.valid is True
    assert result.ack_allowed is True
    assert stored_wait is not None
    assert stored_wait.status == "responded"
    assert stored_decision is not None
    assert stored_decision.decision_type == "approve"


def test_feedback_rejects_direct_review_task_message_correlation(tmp_path):
    runtime = _make_runtime(tmp_path, "maverick-runtime-001", "maverick", "maverick")
    runtime.startup()
    wait = runtime.create_authority_wait_state(
        workflow_instance_id="wf-hitl-002",
        checkpoint_id="checkpoint-002",
        gate_id="gate-002",
        requested_actor_role="reviewer",
        due_at=_future_iso(),
    )
    runtime.register_review_task_message(wait.authority_wait_id, "review-msg-002")
    feedback = build_execution_envelope(
        message_type="Feedback_Message",
        workflow_instance_id="wf-hitl-002",
        workflow_type="hitl",
        workflow_version="0.3",
        producer="viper",
        payload=FeedbackMessagePayload(
            feedback_id="feedback-002",
            review_task_id="review-wait-002",
            authority_wait_id=wait.authority_wait_id,
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
        correlation_id="review-msg-002",
        causation_id="review-msg-002",
    )

    result = runtime.receive_feedback("agent.maverick.callbacks", feedback.to_dict())
    runtime.close()

    assert result.valid is False
    assert result.ack_allowed is False
    assert any("INVALID_FEEDBACK_CORRELATION" in error for error in result.errors)


def test_authority_wait_timeout_creates_timeout_message_and_abnormal_state(tmp_path):
    runtime = _make_runtime(tmp_path, "maverick-runtime-001", "maverick", "maverick")
    runtime.startup()
    wait = runtime.create_authority_wait_state(
        workflow_instance_id="wf-timeout-hitl-001",
        checkpoint_id="checkpoint-timeout-001",
        gate_id="gate-timeout-001",
        requested_actor_role="reviewer",
        due_at=_past_iso(),
    )
    runtime.register_review_task_message(wait.authority_wait_id, "review-msg-timeout-001")

    result = runtime.scan_timeouts()
    unresolved = runtime.state_store.list_unresolved_abnormal_states("wf-timeout-hitl-001")
    runtime.close()

    assert len(result.authority_wait_timeout_envelopes) == 1
    timeout_envelope = result.authority_wait_timeout_envelopes[0]
    assert timeout_envelope.message_type == "Timeout_Message"
    assert timeout_envelope.payload.timeout_scope == "authority_wait"
    assert len(unresolved) == 1
    assert unresolved[0].abnormal_class == "authority_stall"


def test_listener_rejects_deferred_execution_family(tmp_path):
    adapter = MqAdapterStub()
    runtime = _make_runtime(tmp_path, "viper-runtime-001", "viper", "viper")
    listener = ListenerRuntime(adapter, runtime)
    listener.startup()
    deferred = build_execution_envelope(
        message_type="Evidence_Write_Message",
        workflow_instance_id="wf-deferred-001",
        workflow_type="commit",
        workflow_version="0.3",
        producer="maverick",
        payload={
            "evidence_write_id": "ew-001",
            "workflow_instance_id": "wf-deferred-001",
            "transition_id": "transition-001",
            "evidence_ref": "evidence://1",
            "artifact_ref": "artifact://1",
            "payload_hash": "hash-001",
            "written_by": "maverick",
            "written_at": datetime.now(timezone.utc).isoformat(),
            "commit_phase": "pending",
        },
        source_agent_id="maverick",
        source_runtime_instance_id="maverick-windows-main-20260507",
        source_role="maverick",
        authority_scope="workflow.command",
        target_agent_id="viper",
    )
    adapter.publish(deferred.to_dict())

    result = listener.poll_once()
    anomaly = adapter.consume()
    listener.close()

    assert result.status == "deferred_rejected"
    assert result.acked is True
    assert anomaly is not None
    assert anomaly["subject"] == "ops.anomaly"
