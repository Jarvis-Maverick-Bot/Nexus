"""Focused Phase 2 durable intake and ACK boundary tests."""

from datetime import datetime, timedelta, timezone
import os

from nexus.mq.adapter import MqAdapterStub
from nexus.mq.coordination_runtime import CoordinationRuntime
from nexus.mq.listener_runtime import ListenerRuntime, ListenerRuntimeConfig
from nexus.mq.message_contracts import build_execution_envelope
from nexus.mq.payloads import (
    CommandMessagePayload,
    EvidenceWriteMessagePayload,
    FeedbackMessagePayload,
)
from nexus.mq.protocol import build_protocol_envelope
from nexus.mq.protocol_routing import (
    build_agent_callback_subject,
    build_ops_anomaly_subject,
    build_ops_timeout_subject,
    build_review_request_subject,
)


def _identity_config_path() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "agents.yaml")
    )


def _future_iso(minutes: int = 5) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def _past_iso(minutes: int = 5) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def _make_runtime(tmp_path, runtime_id="viper-runtime-phase2", agent_id="viper", role="viper"):
    runtime = CoordinationRuntime.from_paths(
        runtime_id=runtime_id,
        agent_id=agent_id,
        role=role,
        db_path=tmp_path / f"{runtime_id}.sqlite3",
        identity_yaml_path=_identity_config_path(),
    )
    runtime.startup()
    return runtime


def _make_command(**overrides):
    payload = overrides.pop(
        "payload",
        CommandMessagePayload(
            command_name="dispatch_review",
            target_handler="review.dispatch",
            input_refs=["artifact://build/1"],
            expected_outputs=["review_task"],
            allowed_side_effects=["publish_review_task"],
            completion_event_type="review_dispatched",
        ),
    )
    return build_execution_envelope(
        message_type="Command_Message",
        workflow_instance_id=overrides.pop("workflow_instance_id", "wf-phase2-001"),
        workflow_type="delivery",
        workflow_version="1.0",
        producer="phase2-test",
        payload=payload,
        source_agent_id=overrides.pop("source_agent_id", "maverick"),
        source_runtime_instance_id=overrides.pop("source_runtime_instance_id", "maverick-windows-main-20260507"),
        source_role=overrides.pop("source_role", "maverick"),
        authority_scope=overrides.pop("authority_scope", "workflow.command"),
        target_agent_id=overrides.pop("target_agent_id", "viper"),
        reply_to_subject=overrides.pop("reply_to_subject", "agent.maverick.callbacks"),
        idempotency_key=overrides.pop("idempotency_key", "idem-phase2-001"),
        correlation_id=overrides.pop("correlation_id", "corr-phase2-001"),
        **overrides,
    )


def _make_feedback(**overrides):
    payload = overrides.pop(
        "payload",
        FeedbackMessagePayload(
            feedback_id="fb-phase2-001",
            review_task_id="review-wait-phase2-001",
            authority_wait_id="wait-phase2-001",
            reviewer_actor_id="alex",
            reviewer_role="reviewer",
            action="Approve",
            submitted_at="2026-05-12T12:00:00Z",
        ),
    )
    return build_execution_envelope(
        message_type="Feedback_Message",
        workflow_instance_id=overrides.pop("workflow_instance_id", "wf-feedback-001"),
        workflow_type="hitl",
        workflow_version="0.3",
        producer="phase2-test",
        payload=payload,
        source_agent_id=overrides.pop("source_agent_id", "maverick"),
        source_runtime_instance_id=overrides.pop("source_runtime_instance_id", "maverick-windows-main-20260507"),
        source_role=overrides.pop("source_role", "maverick"),
        authority_scope=overrides.pop("authority_scope", "workflow.feedback"),
        target_agent_id=overrides.pop("target_agent_id", "maverick"),
        reply_to_subject=overrides.pop("reply_to_subject", "agent.maverick.callbacks"),
        idempotency_key=overrides.pop("idempotency_key", "idem-feedback-001"),
        correlation_id=overrides.pop("correlation_id", "wait-phase2-001"),
        causation_id=overrides.pop("causation_id", "review-wait-phase2-001"),
        **overrides,
    )


def test_if01_malformed_unparseable_envelope_is_terminal_reject(tmp_path):
    runtime = _make_runtime(tmp_path)
    result = runtime.intake_inbound_message("agent.viper.inbox", "not-json-envelope")
    runtime.close()

    assert result.valid is False
    assert result.broker_action == "REJECT"
    assert result.failure_class == "IF-01"
    assert result.intake_record is not None
    assert result.intake_record.raw_inbound_envelope == "not-json-envelope"
    assert result.intake_record.normalized_execution_envelope is None


def test_if02_schema_validation_failure_records_terminal_reject(tmp_path):
    runtime = _make_runtime(tmp_path)
    command = _make_command(
        payload=CommandMessagePayload(
            command_name="dispatch_review",
            target_handler="review.dispatch",
            completion_event_type="",
        ),
        idempotency_key="idem-if02",
        correlation_id="corr-if02",
    )
    result = runtime.intake_inbound_message("agent.viper.inbox", command.to_dict())
    runtime.close()

    assert result.valid is False
    assert result.broker_action == "REJECT"
    assert result.failure_class == "IF-02"
    assert any("MISSING_REQUIRED_PAYLOAD_FIELD: completion_event_type" in error for error in result.errors)


def test_if03_authority_scope_mismatch_creates_abnormal_state(tmp_path):
    runtime = _make_runtime(tmp_path)
    command = _make_command(
        source_role="intruder",
        idempotency_key="idem-if03",
        correlation_id="corr-if03",
    )
    result = runtime.intake_inbound_message("agent.viper.inbox", command.to_dict())
    unresolved = runtime.state_store.list_unresolved_abnormal_states(command.workflow_instance_id)
    runtime.close()

    assert result.valid is False
    assert result.broker_action == "REJECT"
    assert result.failure_class == "IF-03"
    assert result.intake_record is not None
    assert result.intake_record.abnormal_state_id is not None
    assert unresolved[0].abnormal_class == "authority_stall"


def test_if04_expired_inbox_is_terminal_ack_case(tmp_path):
    runtime = _make_runtime(tmp_path)
    command = _make_command(
        expires_at=_past_iso(),
        idempotency_key="idem-if04-inbox",
        correlation_id="corr-if04-inbox",
    )
    result = runtime.intake_inbound_message("agent.viper.inbox", command.to_dict())
    runtime.close()

    assert result.valid is False
    assert result.broker_action == "TERM"
    assert result.failure_class == "IF-04"
    assert result.intake_record is not None
    assert result.intake_record.terminal_outcome == "terminal"


def test_if04_expired_feedback_is_retryable_nak_case(tmp_path):
    runtime = _make_runtime(tmp_path, runtime_id="maverick-runtime-if04", agent_id="maverick", role="maverick")
    feedback = _make_feedback(
        expires_at=_past_iso(),
        idempotency_key="idem-if04-feedback",
        correlation_id="wait-if04-feedback",
    )
    result = runtime.receive_feedback("agent.maverick.callbacks", feedback.to_dict())
    runtime.close()

    assert result.valid is False
    assert result.broker_action == "NAK"
    assert result.failure_class == "IF-04"
    assert result.intake_record is not None
    assert result.intake_record.anomaly_id is None


def test_if04_expired_callback_subject_is_term_ack_with_orphan_anomaly(tmp_path):
    runtime = _make_runtime(tmp_path, runtime_id="maverick-runtime-if04-callback", agent_id="maverick", role="maverick")
    callback = build_protocol_envelope(
        message_type="result",
        source_agent_id="viper",
        source_runtime_instance_id="viper-windows-main-20260507",
        source_role="viper",
        authority_scope="workflow.result",
        payload={"status": "late"},
        target_agent_id="maverick",
        reply_to_subject=build_agent_callback_subject("maverick"),
        correlation_id="corr-if04-callback",
        causation_id="msg-if04-callback",
        idempotency_key="idem-if04-callback",
        expires_at=_past_iso(),
    )
    result = runtime.receive_callback(build_agent_callback_subject("maverick"), callback.to_dict())
    runtime.close()

    assert result.valid is False
    assert result.broker_action == "TERM"
    assert result.failure_class == "IF-04"
    assert result.intake_record is not None
    assert result.intake_record.anomaly_id is not None
    assert result.intake_record.abnormal_state_id is None


def test_if04_expired_review_subject_is_retryable_nak_case(tmp_path):
    runtime = _make_runtime(tmp_path, runtime_id="maverick-runtime-if04-review", agent_id="maverick", role="maverick")
    review = build_protocol_envelope(
        message_type="review",
        source_agent_id="viper",
        source_runtime_instance_id="viper-windows-main-20260507",
        source_role="viper",
        authority_scope="workflow.review.request",
        payload={"review_kind": "security", "artifact_ref": "artifact://if04-review"},
        capability="security",
        reply_to_subject=build_agent_callback_subject("viper"),
        correlation_id="corr-if04-review",
        causation_id=None,
        idempotency_key="idem-if04-review",
        expires_at=_past_iso(),
    )
    result = runtime.intake_inbound_message(build_review_request_subject("security"), review.to_dict())
    runtime.close()

    assert result.valid is False
    assert result.broker_action == "NAK"
    assert result.failure_class == "IF-04"
    assert result.intake_record is not None
    assert result.intake_record.anomaly_id is None
    assert result.intake_record.abnormal_state_id is None


def test_if04_expired_ops_timeout_is_retryable_nak_case(tmp_path):
    runtime = _make_runtime(tmp_path, runtime_id="maverick-runtime-if04-timeout", agent_id="maverick", role="maverick")
    timeout = build_protocol_envelope(
        message_type="timeout",
        source_agent_id="viper",
        source_runtime_instance_id="viper-windows-main-20260507",
        source_role="viper",
        authority_scope="workflow.timeout",
        payload={"timeout_id": "timeout-if04-ops", "record_type": "pending_task"},
        correlation_id="corr-if04-timeout",
        causation_id="task-if04-timeout",
        idempotency_key="idem-if04-timeout",
        expires_at=_past_iso(),
    )
    result = runtime.intake_inbound_message(build_ops_timeout_subject(), timeout.to_dict())
    runtime.close()

    assert result.valid is False
    assert result.broker_action == "NAK"
    assert result.failure_class == "IF-04"
    assert result.intake_record is not None
    assert result.intake_record.anomaly_id is None
    assert result.intake_record.abnormal_state_id is None


def test_if04_expired_ops_anomaly_is_term_ack_without_abnormal_state(tmp_path):
    runtime = _make_runtime(tmp_path, runtime_id="maverick-runtime-if04-anomaly", agent_id="maverick", role="maverick")
    anomaly = build_protocol_envelope(
        message_type="anomaly",
        source_agent_id="viper",
        source_runtime_instance_id="viper-windows-main-20260507",
        source_role="viper",
        authority_scope="workflow.anomaly",
        payload={"error_code": "EXPIRED_IF04"},
        correlation_id="corr-if04-anomaly",
        causation_id="msg-if04-anomaly",
        idempotency_key="idem-if04-anomaly",
        expires_at=_past_iso(),
    )
    result = runtime.intake_inbound_message(build_ops_anomaly_subject(), anomaly.to_dict())
    runtime.close()

    assert result.valid is False
    assert result.broker_action == "TERM"
    assert result.failure_class == "IF-04"
    assert result.intake_record is not None
    assert result.intake_record.abnormal_state_id is None


def test_if04_retryable_families_create_mechanism_stall_after_maxdeliver_exhaustion(tmp_path):
    runtime = _make_runtime(tmp_path, runtime_id="maverick-runtime-if04-exhausted", agent_id="maverick", role="maverick")

    feedback = _make_feedback(
        expires_at=_past_iso(),
        idempotency_key="idem-if04-exhausted-feedback",
        correlation_id="wait-if04-exhausted-feedback",
    )
    feedback_result = runtime.receive_feedback(build_agent_callback_subject("maverick"), feedback.to_dict())
    exhausted_feedback = runtime.record_retryable_if04_exhaustion(
        envelope_id=feedback.message_id,
        workflow_instance_id=feedback.workflow_instance_id,
        reason="MaxDeliver exhausted for expired feedback",
    )

    review = build_protocol_envelope(
        message_type="review",
        source_agent_id="viper",
        source_runtime_instance_id="viper-windows-main-20260507",
        source_role="viper",
        authority_scope="workflow.review.request",
        payload={"review_kind": "security", "artifact_ref": "artifact://if04-review-exhausted"},
        capability="security",
        reply_to_subject=build_agent_callback_subject("viper"),
        correlation_id="corr-if04-review-exhausted",
        causation_id=None,
        idempotency_key="idem-if04-review-exhausted",
        expires_at=_past_iso(),
    )
    review_result = runtime.intake_inbound_message(build_review_request_subject("security"), review.to_dict())
    exhausted_review = runtime.record_retryable_if04_exhaustion(
        envelope_id=review.message_id,
        workflow_instance_id=None,
        reason="MaxDeliver exhausted for expired review",
    )

    timeout = build_protocol_envelope(
        message_type="timeout",
        source_agent_id="viper",
        source_runtime_instance_id="viper-windows-main-20260507",
        source_role="viper",
        authority_scope="workflow.timeout",
        payload={"timeout_id": "timeout-if04-ops-exhausted", "record_type": "pending_task"},
        correlation_id="corr-if04-timeout-exhausted",
        causation_id="task-if04-timeout-exhausted",
        idempotency_key="idem-if04-timeout-exhausted",
        expires_at=_past_iso(),
    )
    timeout_result = runtime.intake_inbound_message(build_ops_timeout_subject(), timeout.to_dict())
    exhausted_timeout = runtime.record_retryable_if04_exhaustion(
        envelope_id=timeout.message_id,
        workflow_instance_id=None,
        reason="MaxDeliver exhausted for expired ops.timeout",
    )

    unresolved = runtime.state_store.list_unresolved_abnormal_states()
    runtime.close()

    assert feedback_result.broker_action == "NAK"
    assert review_result.broker_action == "NAK"
    assert timeout_result.broker_action == "NAK"
    assert exhausted_feedback.terminal_outcome == "blocked"
    assert exhausted_review.terminal_outcome == "blocked"
    assert exhausted_timeout.terminal_outcome == "blocked"
    assert exhausted_feedback.abnormal_state_id is not None
    assert exhausted_review.abnormal_state_id is not None
    assert exhausted_timeout.abnormal_state_id is not None
    assert all(record.abnormal_class == "mechanism_stall" for record in unresolved)


def test_if05_deferred_family_is_terminal_reject_case(tmp_path):
    runtime = _make_runtime(tmp_path)
    envelope = build_execution_envelope(
        message_type="Evidence_Write_Message",
        workflow_instance_id="wf-if05-001",
        workflow_type="delivery",
        workflow_version="1.0",
        producer="phase2-test",
        payload=EvidenceWriteMessagePayload(
            evidence_write_id="ew-if05-001",
            workflow_instance_id="wf-if05-001",
            transition_id="tr-if05-001",
            evidence_ref="evidence://if05",
            artifact_ref="artifact://if05",
            payload_hash="hash-if05",
            written_by="phase2-test",
            written_at="2026-05-12T12:00:00Z",
            commit_phase="pending",
        ),
        source_agent_id="maverick",
        source_runtime_instance_id="maverick-windows-main-20260507",
        source_role="maverick",
        authority_scope="workflow.command",
        target_agent_id="viper",
        reply_to_subject="agent.maverick.callbacks",
        idempotency_key="idem-if05",
        correlation_id="corr-if05",
    )
    result = runtime.intake_inbound_message("agent.viper.inbox", envelope.to_dict())
    runtime.close()

    assert result.valid is False
    assert result.broker_action == "REJECT"
    assert result.failure_class == "IF-05"


def test_if06_duplicate_reuses_existing_result_without_terminal_record(tmp_path):
    runtime = _make_runtime(tmp_path)
    command = _make_command(idempotency_key="idem-if06", correlation_id="corr-if06")
    first = runtime.intake_inbound_message("agent.viper.inbox", command.to_dict())
    runtime.mark_task_completed(
        task_id=f"task-{command.message_id}",
        idempotency_key=command.idempotency_key,
        message_id=command.message_id,
        workflow_id=command.workflow_instance_id,
        result_payload={"status": "ok", "result_id": "existing-if06"},
    )
    duplicate = runtime.intake_inbound_message("agent.viper.inbox", command.to_dict())
    runtime.close()

    assert first.valid is True
    assert duplicate.valid is True
    assert duplicate.duplicate is True
    assert duplicate.ack_allowed is True
    assert duplicate.failure_class == "IF-06"
    assert duplicate.existing_result == {"status": "ok", "result_id": "existing-if06"}
    assert duplicate.intake_record is None


def test_if07_unknown_correlation_causation_records_other_abnormal(tmp_path):
    runtime = _make_runtime(tmp_path, runtime_id="maverick-runtime-if07", agent_id="maverick", role="maverick")
    orphan = build_protocol_envelope(
        message_type="result",
        source_agent_id="viper",
        source_runtime_instance_id="viper-windows-main-20260507",
        source_role="viper",
        authority_scope="workflow.result",
        payload={"status": "ok"},
        target_agent_id="maverick",
        reply_to_subject="agent.maverick.callbacks",
        correlation_id="corr-if07",
        causation_id="missing-request-if07",
        idempotency_key="idem-if07",
    )
    result = runtime.receive_callback("agent.maverick.callbacks", orphan.to_dict())
    unresolved = runtime.state_store.list_unresolved_abnormal_states()
    runtime.close()

    assert result.valid is False
    assert result.broker_action == "REJECT"
    assert result.failure_class == "IF-07"
    assert unresolved[0].abnormal_class == "other"


def test_if08_invalid_hitl_callback_creates_authority_abnormal(tmp_path):
    runtime = _make_runtime(tmp_path, runtime_id="maverick-runtime-if08", agent_id="maverick", role="maverick")
    feedback = _make_feedback(
        idempotency_key="idem-if08",
        correlation_id="wait-if08",
        causation_id="review-if08",
    )
    result = runtime.receive_feedback("agent.maverick.callbacks", feedback.to_dict())
    unresolved = runtime.state_store.list_unresolved_abnormal_states()
    runtime.close()

    assert result.valid is False
    assert result.broker_action == "REJECT"
    assert result.failure_class == "IF-08"
    assert result.intake_record is not None
    assert result.intake_record.anomaly_id is not None
    assert unresolved[0].abnormal_class == "authority_stall"


def test_if09_post_ack_handler_failure_exhaustion_quarantines_record(tmp_path):
    runtime = _make_runtime(tmp_path)
    command = _make_command(idempotency_key="idem-if09", correlation_id="corr-if09")
    intake = runtime.intake_inbound_message("agent.viper.inbox", command.to_dict())

    first = runtime.record_post_ack_handler_failure(command.message_id, "dispatch failure 1")
    second = runtime.record_post_ack_handler_failure(command.message_id, "dispatch failure 2")
    third = runtime.record_post_ack_handler_failure(command.message_id, "dispatch failure 3")
    recovery = runtime.list_local_recovery_candidates()
    unresolved = runtime.state_store.list_unresolved_abnormal_states(command.workflow_instance_id)
    runtime.close()

    assert intake.valid is True
    assert intake.ack_allowed is True
    assert first.state == "failed"
    assert second.local_retry_count == 2
    assert third.state == "handler_exhausted"
    assert third.broker_action == "QUARANTINE"
    assert third.abnormal_state_id is not None
    assert recovery == []
    assert unresolved[0].abnormal_class == "mechanism_stall"


def test_listener_acks_terminal_reject_and_naks_retryable_expiry(tmp_path):
    adapter = MqAdapterStub()
    runtime = _make_runtime(tmp_path, runtime_id="listener-runtime-phase2", agent_id="maverick", role="maverick")
    listener = ListenerRuntime(
        adapter=adapter,
        coordination_runtime=runtime,
        config=ListenerRuntimeConfig(emit_anomaly_on_invalid=False),
    )

    malformed_message = {
        "subject": "agent.maverick.inbox",
        "envelope": "not-json-envelope",
    }
    adapter._messages.append(malformed_message)
    rejected = listener.poll_once()

    expired_feedback = _make_feedback(
        expires_at=_past_iso(),
        idempotency_key="idem-listener-if04",
        correlation_id="wait-listener-if04",
    )
    adapter._messages.append(
        {
            "subject": "agent.maverick.callbacks",
            "envelope": expired_feedback.to_dict(),
        }
    )
    retried = listener.poll_once()
    ack_levels = [item["ack_level"] for item in adapter.get_ack_log()]
    listener.close()

    assert rejected.acked is True
    assert retried.acked is False
    assert "consumer_intake" in ack_levels
    assert "consumer_nak" in ack_levels
