"""Durable local state tests for the always-on coordination runtime."""

from datetime import datetime, timedelta, timezone

from nexus.mq.durable_state import DurableStateStore


def _future_iso(minutes: int = 5) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def _past_iso(minutes: int = 5) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def test_durable_state_initializes_and_passes_integrity_check(tmp_path):
    store = DurableStateStore(tmp_path / "mq-runtime.sqlite3")
    valid, errors = store.verify_integrity()
    store.close()

    assert valid is True
    assert errors == []


def test_pending_task_persists_across_reopen(tmp_path):
    db_path = tmp_path / "mq-runtime.sqlite3"
    store = DurableStateStore(db_path)

    record = store.create_pending_task(
        task_type="command",
        subject="agent.jarvis.inbox",
        correlation_id="corr-001",
        payload={"command": "dispatch"},
        reply_to_subject="agent.nova.callbacks",
        deadline_at=_future_iso(),
        created_by="jarvis-runtime",
    )
    store.close()

    reopened = DurableStateStore(db_path)
    restored = reopened.get_pending_task(record.task_id)
    reopened.close()

    assert restored is not None
    assert restored.task_id == record.task_id
    assert restored.payload == {"command": "dispatch"}
    assert restored.state == "PENDING"


def test_pending_task_update_and_overdue_listing(tmp_path):
    store = DurableStateStore(tmp_path / "mq-runtime.sqlite3")
    overdue = store.create_pending_task(
        task_type="command",
        subject="agent.jarvis.inbox",
        correlation_id="corr-overdue-001",
        payload={"command": "late"},
        reply_to_subject="agent.nova.callbacks",
        deadline_at=_past_iso(),
        created_by="jarvis-runtime",
    )
    active = store.create_pending_task(
        task_type="command",
        subject="agent.jarvis.inbox",
        correlation_id="corr-active-001",
        payload={"command": "ontime"},
        reply_to_subject="agent.nova.callbacks",
        deadline_at=_future_iso(),
        created_by="jarvis-runtime",
    )

    updated = store.update_pending_task(
        task_id=active.task_id,
        state="COMPLETED",
        updated_by="jarvis-runtime",
        result_payload={"status": "ok"},
        completed_at=datetime.now(timezone.utc).isoformat(),
    )
    overdue_records = store.list_overdue_pending_tasks()
    store.close()

    assert updated.state == "COMPLETED"
    assert updated.result_payload == {"status": "ok"}
    assert [record.task_id for record in overdue_records] == [overdue.task_id]


def test_callback_wait_complete_and_expire(tmp_path):
    store = DurableStateStore(tmp_path / "mq-runtime.sqlite3")
    received = store.create_callback_wait(
        correlation_id="corr-callback-001",
        expected_subject="agent.nova.callbacks",
        expected_source_agent_id="nova",
        request_message_id="msg-request-001",
        deadline_at=_future_iso(),
        created_by="jarvis-runtime",
    )
    expired = store.create_callback_wait(
        correlation_id="corr-callback-002",
        expected_subject="agent.nova.callbacks",
        expected_source_agent_id="nova",
        request_message_id="msg-request-002",
        deadline_at=_future_iso(),
        created_by="jarvis-runtime",
    )

    completed = store.complete_callback_wait(
        callback_id=received.callback_id,
        response_payload={"status": "ok"},
    )
    expired = store.expire_callback_wait(
        callback_id=expired.callback_id,
        error_summary="timeout waiting for callback",
    )
    waiting = store.list_waiting_callbacks()
    store.close()

    assert completed.state == "RECEIVED"
    assert completed.response_payload == {"status": "ok"}
    assert expired.state == "EXPIRED"
    assert expired.error_summary == "timeout waiting for callback"
    assert waiting == []


def test_outbox_reconciliation_lifecycle(tmp_path):
    store = DurableStateStore(tmp_path / "mq-runtime.sqlite3")
    record = store.create_outbox_record(
        side_effect_type="publish_result",
        target="agent.nova.callbacks",
        correlation_id="corr-outbox-001",
        payload={"status": "ok"},
        created_by="jarvis-runtime",
        message_id="msg-outbox-001",
        causation_id="msg-request-001",
    )
    pending = store.list_outbox_requiring_reconciliation()
    published = store.mark_outbox_published(record.outbox_id)
    after_publish = store.list_outbox_requiring_reconciliation()
    confirmed = store.mark_outbox_confirmed(record.outbox_id, confirmed_by="jarvis-runtime")
    final_pending = store.list_outbox_requiring_reconciliation()
    store.close()

    assert [item.outbox_id for item in pending] == [record.outbox_id]
    assert published.state == "PUBLISHED"
    assert [item.outbox_id for item in after_publish] == [record.outbox_id]
    assert confirmed.state == "CONFIRMED"
    assert final_pending == []


def test_envelope_inbox_and_idempotency_are_durable(tmp_path):
    db_path = tmp_path / "mq-runtime.sqlite3"
    store = DurableStateStore(db_path)
    envelope = store.record_envelope_inbox(
        envelope_id="env-001",
        subject="agent.jarvis.inbox",
        payload={"message_id": "env-001"},
    )
    store.complete_envelope_inbox(envelope_id=envelope.envelope_id)
    idempotency = store.record_idempotency(
        idempotency_key="idem-001",
        message_id="msg-001",
        workflow_id="wf-001",
        result_detail={"status": "committed"},
    )
    store.close()

    reopened = DurableStateStore(db_path)
    restored_envelope = reopened.get_envelope_inbox("env-001")
    restored_idempotency = reopened.get_idempotency("idem-001")
    reopened.close()

    assert restored_envelope is not None
    assert restored_envelope.state == "completed"
    assert restored_idempotency is not None
    assert restored_idempotency.message_id == idempotency.message_id
    assert restored_idempotency.result_detail == {"status": "committed"}


def test_envelope_inbox_preserves_raw_and_normalized_intake_contract(tmp_path):
    store = DurableStateStore(tmp_path / "mq-runtime.sqlite3")
    record = store.record_envelope_inbox(
        envelope_id="env-phase2-001",
        subject="agent.viper.inbox",
        payload='{"raw":"payload"}',
        normalized_execution_envelope={"message_id": "env-phase2-001", "payload": {"command": "dispatch"}},
        validation_errors=["SCHEMA_WARNING"],
        failure_class="IF-02",
        failure_subclass="schema_validation_failure",
        broker_action="REJECT",
        terminal_outcome="terminal",
        anomaly_id="anomaly-001",
        workflow_instance_id="wf-phase2-001",
        message_id="env-phase2-001",
        correlation_id="corr-phase2-001",
        source_agent_id="maverick",
        target_agent_id="viper",
    )
    restored = store.get_envelope_inbox("env-phase2-001")
    store.close()

    assert restored is not None
    assert restored.record_id == record.record_id
    assert restored.raw_inbound_envelope == '{"raw":"payload"}'
    assert restored.normalized_execution_envelope == {"message_id": "env-phase2-001", "payload": {"command": "dispatch"}}
    assert restored.validation_errors == ["SCHEMA_WARNING"]
    assert restored.failure_class == "IF-02"
    assert restored.broker_action == "REJECT"
    assert restored.target_agent_id == "viper"


def test_envelope_inbox_local_recovery_exhaustion_blocks_redispatch(tmp_path):
    store = DurableStateStore(tmp_path / "mq-runtime.sqlite3")
    store.record_envelope_inbox(
        envelope_id="env-if09-001",
        subject="agent.viper.inbox",
        payload={"message_id": "env-if09-001"},
        normalized_execution_envelope={"message_id": "env-if09-001"},
        workflow_instance_id="wf-if09-001",
        message_id="env-if09-001",
        max_local_retries=3,
    )

    first = store.mark_envelope_inbox_handler_failure("env-if09-001", "dispatch failed #1")
    second = store.mark_envelope_inbox_handler_failure("env-if09-001", "dispatch failed #2")
    third = store.mark_envelope_inbox_handler_failure("env-if09-001", "dispatch failed #3")
    recovery = store.list_envelope_inbox_for_local_recovery()
    store.close()

    assert first.state == "failed"
    assert second.local_retry_count == 2
    assert third.state == "handler_exhausted"
    assert third.handler_exhausted is True
    assert third.broker_action == "QUARANTINE"
    assert [record.envelope_id for record in recovery] == []


def test_runtime_status_quarantine_and_recovery_state(tmp_path):
    store = DurableStateStore(tmp_path / "mq-runtime.sqlite3")
    active = store.set_runtime_status(
        runtime_id="jarvis-runtime-001",
        agent_id="jarvis",
        status="ACTIVE",
    )
    quarantined = store.quarantine_runtime(
        runtime_id="jarvis-runtime-001",
        agent_id="jarvis",
        reason="corrupt callback wait record",
    )
    restored = store.get_runtime_status("jarvis-runtime-001")
    store.close()

    assert active.status == "ACTIVE"
    assert quarantined.status == "QUARANTINED"
    assert restored is not None
    assert restored.status == "QUARANTINED"
    assert restored.reason == "corrupt callback wait record"
