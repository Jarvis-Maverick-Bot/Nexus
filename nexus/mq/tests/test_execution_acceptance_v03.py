from datetime import datetime, timedelta, timezone
import os

from nexus.mq.adapter import MqAdapterStub
from nexus.mq.coordination_runtime import CoordinationRuntime
from nexus.mq.listener_runtime import ListenerRuntime
from nexus.mq.message_contracts import build_execution_envelope
from nexus.mq.payloads import (
    CommandMessagePayload,
    DeadLetterMessagePayload,
    FeedbackMessagePayload,
    RetryMessagePayload,
)


def _identity_config_path() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "agents.yaml")
    )


def _future_iso(minutes: int = 5) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def _past_iso(minutes: int = 5) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def _make_listener(tmp_path, runtime_id: str, agent_id: str, role: str) -> ListenerRuntime:
    adapter = MqAdapterStub()
    runtime = CoordinationRuntime.from_paths(
        runtime_id=runtime_id,
        agent_id=agent_id,
        role=role,
        db_path=tmp_path / f"{runtime_id}.sqlite3",
        identity_yaml_path=_identity_config_path(),
    )
    listener = ListenerRuntime(adapter, runtime)
    listener.startup()
    return listener


def test_retry_message_intake_is_family_specific_and_acked(tmp_path):
    listener = _make_listener(tmp_path, "viper-runtime-retry-001", "viper", "viper")
    retry = build_execution_envelope(
        message_type="Retry_Message",
        workflow_instance_id="wf-retry-001",
        workflow_type="delivery",
        workflow_version="0.3",
        producer="maverick",
        payload=RetryMessagePayload(
            retry_id="retry-001",
            original_message_id="msg-original-001",
            original_idempotency_key="idem-original-001",
            original_message_type="Command_Message",
            target_subject="agent.viper.inbox",
            retry_count=1,
            max_retries=3,
            retry_reason="temporary_transport_error",
            last_error="timeout",
            created_at=datetime.now(timezone.utc).isoformat(),
        ),
        source_agent_id="maverick",
        source_runtime_instance_id="maverick-windows-main-20260507",
        source_role="maverick",
        authority_scope="workflow.command",
        target_agent_id="viper",
        reply_to_subject="agent.maverick.callbacks",
        expires_at=_future_iso(),
    )
    listener.adapter.publish(retry.to_dict())

    result = listener.poll_once()
    stored = listener.runtime.state_store.get_pending_task(f"task-{retry.message_id}")
    listener.close()

    assert result.status == "retry_recorded"
    assert result.acked is True
    assert stored is not None
    assert stored.task_type == "Retry_Message"


def test_dead_letter_message_intake_is_family_specific_and_acked(tmp_path):
    listener = _make_listener(tmp_path, "viper-runtime-dlq-001", "viper", "viper")
    dead_letter = build_execution_envelope(
        message_type="Dead_Letter_Message",
        workflow_instance_id="wf-dlq-001",
        workflow_type="delivery",
        workflow_version="0.3",
        producer="maverick",
        payload=DeadLetterMessagePayload(
            dead_letter_id="dlq-001",
            original_message_id="msg-original-001",
            original_message_type="Command_Message",
            original_idempotency_key="idem-original-001",
            attempts_exhausted=3,
            dead_letter_reason="retries_exhausted",
            last_error="transport_timeout",
            dead_lettered_at=datetime.now(timezone.utc).isoformat(),
        ),
        source_agent_id="maverick",
        source_runtime_instance_id="maverick-windows-main-20260507",
        source_role="maverick",
        authority_scope="workflow.command",
        target_agent_id="viper",
        reply_to_subject="agent.maverick.callbacks",
        expires_at=_future_iso(),
    )
    listener.adapter.publish(dead_letter.to_dict())

    result = listener.poll_once()
    stored = listener.runtime.state_store.get_pending_task(f"task-{dead_letter.message_id}")
    listener.close()

    assert result.status == "dead_letter_recorded"
    assert result.acked is True
    assert stored is not None
    assert stored.task_type == "Dead_Letter_Message"


def test_callback_timeout_and_authority_wait_timeout_remain_distinct(tmp_path):
    listener = _make_listener(tmp_path, "maverick-runtime-timeouts-001", "maverick", "maverick")
    runtime = listener.runtime

    command = build_execution_envelope(
        message_type="Command_Message",
        workflow_instance_id="wf-timeouts-001",
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
        correlation_id="corr-callback-timeout-001",
        expires_at=_past_iso(),
    )
    runtime.state_store.create_callback_wait(
        callback_id="wait-callback-001",
        correlation_id=command.correlation_id,
        expected_subject="agent.maverick.callbacks",
        expected_source_agent_id="viper",
        request_message_id=command.message_id,
        task_id=f"task-{command.message_id}",
        callback_type="Business_Message",
        payload=command.to_dict(),
        reply_subject="agent.maverick.callbacks",
        deadline_at=_past_iso(),
        created_by=runtime.runtime_id,
    )

    authority_wait = runtime.create_authority_wait_state(
        workflow_instance_id="wf-timeouts-001",
        checkpoint_id="checkpoint-timeouts-001",
        gate_id="gate-timeouts-001",
        requested_actor_role="reviewer",
        due_at=_past_iso(),
    )
    runtime.register_review_task_message(authority_wait.authority_wait_id, "review-msg-timeouts-001")

    timeout_result = listener.emit_timeouts_once()
    published = []
    while True:
        item = listener.adapter.consume()
        if item is None:
            break
        published.append(item)
    listener.close()

    assert timeout_result.published_count >= 2
    assert timeout_result.callback_timeouts >= 2
    assert any(
        item["envelope"].get("payload", {}).get("record_type") == "callback_wait"
        or getattr(item["envelope"].get("payload"), "timeout_scope", None) == "authority_wait"
        for item in published
    )
    assert any(
        item["envelope"].get("message_type") == "Timeout_Message"
        and item["envelope"]["payload"]["timeout_scope"] == "authority_wait"
        for item in published
        if item["envelope"].get("message_type") == "Timeout_Message"
    )


def test_stale_feedback_after_escalation_is_rejected(tmp_path):
    listener = _make_listener(tmp_path, "maverick-runtime-stale-001", "maverick", "maverick")
    runtime = listener.runtime
    wait = runtime.create_authority_wait_state(
        workflow_instance_id="wf-stale-001",
        checkpoint_id="checkpoint-stale-001",
        gate_id="gate-stale-001",
        requested_actor_role="reviewer",
        due_at=_past_iso(),
    )
    runtime.register_review_task_message(wait.authority_wait_id, "review-msg-stale-001")
    runtime.scan_timeouts()

    feedback = build_execution_envelope(
        message_type="Feedback_Message",
        workflow_instance_id="wf-stale-001",
        workflow_type="hitl",
        workflow_version="0.3",
        producer="viper",
        payload=FeedbackMessagePayload(
            feedback_id="feedback-stale-001",
            review_task_id="review-msg-stale-001",
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
        causation_id="review-msg-stale-001",
    )

    result = runtime.receive_feedback("agent.maverick.callbacks", feedback.to_dict())
    listener.close()

    assert result.valid is False
    assert result.ack_allowed is False
    assert any("FEEDBACK_STALE" in error for error in result.errors)
