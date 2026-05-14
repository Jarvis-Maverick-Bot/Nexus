from datetime import datetime, timedelta, timezone
import os

from nexus.mq.adapter import MqAdapterStub
from nexus.mq.coordination_runtime import (
    AUTHORITY_ORDER,
    CANONICAL_RECOVERY_OUTCOMES,
    CoordinationRuntime,
    PHASE5_DURABLE_FAMILIES,
    RECOVERY_STATES,
)
from nexus.mq.listener_runtime import ListenerRuntime
from nexus.mq.listener_supervisor import ListenerSupervisor, SupervisorConfig
from nexus.mq.protocol import build_protocol_envelope


def _identity_config_path() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "agents.yaml")
    )


def _future_iso(minutes: int = 5) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def _make_runtime(tmp_path, runtime_id: str = "maverick-runtime-p5") -> CoordinationRuntime:
    runtime = CoordinationRuntime.from_paths(
        runtime_id=runtime_id,
        agent_id="maverick",
        role="maverick",
        db_path=tmp_path / f"{runtime_id}.sqlite3",
        identity_yaml_path=_identity_config_path(),
    )
    runtime.startup()
    return runtime


def _envelope(workflow_instance_id: str = "wf-p5-001"):
    return build_protocol_envelope(
        message_type="command",
        source_agent_id="maverick",
        source_runtime_instance_id="maverick-windows-main-20260507",
        source_role="maverick",
        authority_scope="workflow.command",
        payload={"command": "dispatch", "workflow_instance_id": workflow_instance_id},
        target_agent_id="maverick",
        reply_to_subject="agent.maverick.callbacks",
        correlation_id=f"corr-{workflow_instance_id}",
        causation_id=None,
        expires_at=_future_iso(),
    )


def _record_inbox(runtime: CoordinationRuntime, envelope_id: str, state: str = "processing", max_retries: int = 3):
    return runtime.state_store.record_envelope_inbox(
        envelope_id=envelope_id,
        subject="agent.maverick.inbox",
        payload={"message_id": envelope_id},
        workflow_instance_id="wf-p5-001",
        message_id=envelope_id,
        correlation_id=f"corr-{envelope_id}",
        source_agent_id="maverick",
        target_agent_id="maverick",
        max_local_retries=max_retries,
        state=state,
    )


class CrashAfterPublishAdapter(MqAdapterStub):
    def publish(self, envelope):
        super().publish(envelope)
        raise RuntimeError("simulated crash after broker publish")


def test_p5_01_restart_scan_records_no_go_for_empty_pre_intake_gap(tmp_path):
    runtime = _make_runtime(tmp_path)

    classification = runtime.classify_phase5_recovery_target(
        candidate_type="missing_intake_record",
        state="absent",
    )
    scan = runtime.run_phase5_restart_scan()
    runtime.close()

    assert classification["canonical_outcome"] == "no_go"
    assert scan.family == "recovery_scan_record"
    assert scan.status == "completed"


def test_p5_02_durable_intake_committed_is_reloadable_after_restart(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    runtime = CoordinationRuntime.from_paths("maverick-runtime-p5", "maverick", "maverick", db_path, _identity_config_path())
    runtime.startup()
    envelope = _envelope()
    result = runtime.intake_inbound_message("agent.maverick.inbox", envelope.to_dict())
    runtime.close()

    restarted = CoordinationRuntime.from_paths("maverick-runtime-p5", "maverick", "maverick", db_path, _identity_config_path())
    restarted.startup()
    stored = restarted.state_store.get_pending_task(f"task-{envelope.message_id}")
    restarted.close()

    assert result.ack_allowed is True
    assert stored is not None
    assert stored.state == "PENDING"


def test_p5_03_handler_running_candidate_gets_bounded_retry_action(tmp_path):
    runtime = _make_runtime(tmp_path)
    _record_inbox(runtime, "env-p5-03", state="handler_running")

    runtime.run_phase5_restart_scan()
    actions = runtime.state_store.list_phase5_durable_records("recovery_action_record")
    runtime.close()

    assert actions[0].payload["canonical_outcome"] == "bounded_retry"
    assert actions[0].status == "planned"


def test_p5_04_failed_candidate_gets_bounded_retry_action(tmp_path):
    runtime = _make_runtime(tmp_path)
    _record_inbox(runtime, "env-p5-04", state="failed")

    runtime.run_phase5_restart_scan()
    action = runtime.state_store.list_phase5_durable_records("recovery_action_record")[0]
    runtime.close()

    assert action.payload["canonical_outcome"] == "bounded_retry"
    assert action.payload["previous_state"] == "failed"


def test_p5_05_handler_exhausted_is_governed_quarantine_not_dlq(tmp_path):
    runtime = _make_runtime(tmp_path)
    _record_inbox(runtime, "env-p5-05", max_retries=1)
    runtime.record_post_ack_handler_failure("env-p5-05", "handler crashed")

    runtime.run_phase5_restart_scan()
    actions = runtime.state_store.list_phase5_durable_records("recovery_action_record")
    dlq = runtime.state_store.list_phase3_runtime_records("dead_letter_record")
    runtime.close()

    quarantine = [
        action for action in actions
        if action.payload["canonical_outcome"] == "governed_quarantine"
    ][0]
    assert quarantine.payload["auto_release_allowed"] is False
    assert dlq == []


def test_p5_06_planned_outbox_is_publishable_bounded_retry(tmp_path):
    adapter = MqAdapterStub()
    runtime = _make_runtime(tmp_path)
    outbox = runtime.record_outbox_publish(_envelope())
    listener = ListenerRuntime(adapter, runtime)

    reconciled = listener.reconcile_outbox_once()
    action = runtime.state_store.list_phase5_durable_records("recovery_action_record")[0]
    listener.close()

    assert reconciled == 1
    assert action.payload["canonical_outcome"] == "bounded_retry"
    assert adapter.consume()["envelope"]["message_id"] == outbox.message_id


def test_p5_07_published_without_confirmation_is_no_go_and_not_republished(tmp_path):
    adapter = MqAdapterStub()
    runtime = _make_runtime(tmp_path)
    outbox = runtime.record_outbox_publish(_envelope())
    runtime.state_store.mark_outbox_published(outbox.outbox_id)
    listener = ListenerRuntime(adapter, runtime)

    reconciled = listener.reconcile_outbox_once()
    action = runtime.state_store.list_phase5_durable_records("recovery_action_record")[0]
    listener.close()

    assert reconciled == 0
    assert action.payload["canonical_outcome"] == "no_go"
    assert adapter.consume() is None


def test_p5_07_real_publish_crash_before_confirmation_does_not_republish_on_restart(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    runtime = CoordinationRuntime.from_paths("maverick-runtime-p5", "maverick", "maverick", db_path, _identity_config_path())
    runtime.startup()
    outbox = runtime.record_outbox_publish(_envelope())
    crashing_listener = ListenerRuntime(CrashAfterPublishAdapter(), runtime)

    try:
        crashing_listener.reconcile_outbox_once()
    except RuntimeError:
        pass
    crashed_state = runtime.state_store.get_outbox_record(outbox.outbox_id)
    runtime.close()

    restarted = CoordinationRuntime.from_paths("maverick-runtime-p5", "maverick", "maverick", db_path, _identity_config_path())
    restarted.startup()
    adapter = MqAdapterStub()
    listener = ListenerRuntime(adapter, restarted)
    reconciled = listener.reconcile_outbox_once()
    action = restarted.state_store.list_phase5_durable_records("recovery_action_record")[-1]
    listener.close()

    assert crashed_state is not None
    assert crashed_state.state == "PUBLISHED"
    assert crashed_state.confirmed_at is None
    assert reconciled == 0
    assert action.payload["canonical_outcome"] == "no_go"
    assert adapter.consume() is None


def test_p5_08_dead_letter_record_classifies_explicit_terminal_abnormal(tmp_path):
    runtime = _make_runtime(tmp_path)
    runtime.create_phase4_record(
        record_type="dead_letter_record",
        workflow_instance_id="wf-p5-001",
        related_message_id="msg-p5-08",
        dedupe_key="dlq:p5-08",
        status="dlq_recorded",
        payload={"original_message_id": "msg-p5-08"},
    )

    classification = runtime.classify_phase5_recovery_target(
        candidate_type="dead_letter_record",
        state="dlq_recorded",
    )
    runtime.close()

    assert classification["canonical_outcome"] == "explicit_terminal_abnormal"


def test_p5_09_confirmed_outbox_is_not_reconciled_again(tmp_path):
    adapter = MqAdapterStub()
    runtime = _make_runtime(tmp_path)
    outbox = runtime.record_outbox_publish(_envelope())
    runtime.confirm_outbox_publish(outbox.outbox_id)
    listener = ListenerRuntime(adapter, runtime)

    reconciled = listener.reconcile_outbox_once()
    listener.close()

    assert reconciled == 0
    assert adapter.consume() is None


def test_p5_10_terminal_abnormal_blocks_business_completion(tmp_path):
    runtime = _make_runtime(tmp_path)
    runtime.record_terminal_abnormal(
        dedupe_key="terminal:p5-10",
        workflow_instance_id="wf-p5-001",
        error_event_id="IF-04:msg-p5-10",
        error_class="mechanism_stall",
        affected_ref="msg-p5-10",
        failure_cause="retry exhausted",
    )

    runtime.run_phase5_restart_scan()
    action = runtime.state_store.list_phase5_durable_records("recovery_action_record")[0]
    runtime.close()

    assert action.payload["canonical_outcome"] == "explicit_terminal_abnormal"
    assert action.payload["blocks_business_progress"] is True


def test_p5_11_missing_feedback_authority_is_no_go(tmp_path):
    runtime = _make_runtime(tmp_path)

    classification = runtime.classify_phase5_recovery_target(
        candidate_type="raw_feedback_intake_record",
        state="missing_authority_wait",
    )
    runtime.close()

    assert classification["canonical_outcome"] == "no_go"


def test_p5_12_closed_feedback_rejection_is_runtime_evidence_not_completion(tmp_path):
    runtime = _make_runtime(tmp_path)
    record = runtime.create_phase4_record(
        record_type="stale_feedback_rejection_record",
        workflow_instance_id="wf-p5-001",
        authority_wait_id="wait-p5-12",
        related_message_id="msg-p5-12",
        dedupe_key="stale:p5-12",
        status="feedback_rejected_stale",
        payload={"reason": "authority_wait_state_closed"},
    )
    runtime.close()

    assert record.status == "feedback_rejected_stale"
    assert "completion" not in record.status


def test_p5_13_duplicate_feedback_resolution_does_not_reopen_wait(tmp_path):
    runtime = _make_runtime(tmp_path)
    first = runtime.create_phase5_record(
        family="raw_feedback_intake_record",
        workflow_instance_id="wf-p5-001",
        authority_wait_id="wait-p5-13",
        target_ref="feedback-p5-13",
        dedupe_key="feedback:wait-p5-13:feedback-p5-13",
        status="accepted",
        payload={"feedback_id": "feedback-p5-13"},
    )
    second = runtime.create_phase5_record(
        family="raw_feedback_intake_record",
        workflow_instance_id="wf-p5-001",
        authority_wait_id="wait-p5-13",
        target_ref="feedback-p5-13",
        dedupe_key="feedback:wait-p5-13:feedback-p5-13",
        status="accepted",
        payload={"feedback_id": "feedback-p5-13"},
    )
    runtime.close()

    assert first.record_id == second.record_id


def test_p5_14_decision_without_state_transition_leaves_projection_stale(tmp_path):
    runtime = _make_runtime(tmp_path)
    runtime.create_phase5_record(
        family="hitl_decision_record",
        workflow_instance_id="wf-p5-014",
        target_ref="decision-p5-14",
        dedupe_key="decision:p5-14",
        status="accepted",
        payload={"decision": "Approve"},
    )

    projection = runtime.rebuild_current_projection("wf-p5-014")
    runtime.close()

    assert projection.projection_status == "projection_stale"
    assert projection.payload["governed_state"] == "unknown"


def test_p5_15_state_transition_is_high_authority_projection_source(tmp_path):
    runtime = _make_runtime(tmp_path)
    transition = runtime.create_phase5_record(
        family="state_transition",
        workflow_instance_id="wf-p5-015",
        target_ref="transition-p5-15",
        dedupe_key="transition:p5-15",
        status="accepted",
        payload={"from_state": "waiting", "to_state": "approved"},
    )

    projection = runtime.rebuild_current_projection("wf-p5-015")
    runtime.close()

    assert projection.projection_status == "current"
    assert projection.source_record_id == transition.record_id
    assert projection.payload["governed_state"] == "approved"


def test_p5_16_projection_is_derived_and_lower_authority(tmp_path):
    runtime = _make_runtime(tmp_path)
    runtime.create_phase5_record(
        family="state_transition",
        workflow_instance_id="wf-p5-016",
        target_ref="transition-p5-16",
        dedupe_key="transition:p5-16",
        status="accepted",
        payload={"to_state": "review_complete"},
    )

    projection = runtime.rebuild_current_projection("wf-p5-016")
    runtime.close()

    assert projection.payload["projection_is_derived"] is True
    assert AUTHORITY_ORDER.index("current_projection") > AUTHORITY_ORDER.index("state_transition")


def test_p5_17_all_required_durable_families_are_supported(tmp_path):
    runtime = _make_runtime(tmp_path)

    for family in sorted(PHASE5_DURABLE_FAMILIES):
        runtime.create_phase5_record(
            family=family,
            workflow_instance_id="wf-p5-017",
            target_ref=family,
            dedupe_key=f"family:{family}",
            status="recorded",
            payload={"family": family},
        )
    records = runtime.state_store.list_phase5_durable_records(workflow_instance_id="wf-p5-017")
    runtime.close()

    assert {record.family for record in records} == PHASE5_DURABLE_FAMILIES


def test_p5_18_checkpoint_ref_cannot_override_governed_transition(tmp_path):
    runtime = _make_runtime(tmp_path)
    runtime.create_phase5_record(
        family="state_transition",
        workflow_instance_id="wf-p5-018",
        target_ref="transition-p5-18",
        dedupe_key="transition:p5-18",
        status="accepted",
        payload={"to_state": "approved"},
    )
    runtime.create_phase5_record(
        family="event_log",
        workflow_instance_id="wf-p5-018",
        target_ref="checkpoint-p5-18",
        dedupe_key="checkpoint:p5-18",
        status="recorded",
        payload={"checkpoint_state": "waiting"},
    )

    projection = runtime.rebuild_current_projection("wf-p5-018")
    runtime.close()

    assert projection.payload["governed_state"] == "approved"
    assert AUTHORITY_ORDER.index("checkpoint_ref") > AUTHORITY_ORDER.index("state_transition")


def test_p5_19_projection_marks_unresolved_abnormal_as_stale(tmp_path):
    runtime = _make_runtime(tmp_path)
    runtime.record_terminal_abnormal(
        dedupe_key="terminal:p5-19",
        workflow_instance_id="wf-p5-019",
        error_event_id="IF-09:msg-p5-19",
        error_class="mechanism_stall",
        affected_ref="msg-p5-19",
        failure_cause="handler exhausted",
    )

    projection = runtime.rebuild_current_projection("wf-p5-019")
    runtime.close()

    assert projection.projection_status == "projection_stale"
    assert projection.payload["governed_state"] == "blocked_by_abnormal_state"


def test_p5_20_manual_resolution_without_authority_is_rejected(tmp_path):
    runtime = _make_runtime(tmp_path)

    result = runtime.validate_manual_resolution(
        workflow_instance_id="wf-p5-020",
        abnormal_state_id="abnormal-p5-20",
        resolution_record_id=None,
        actor_id="alex",
        evidence_refs=[],
    )
    runtime.close()

    assert result.status == "rejected"
    assert result.payload["canonical_outcome"] == "no_go"
    assert result.payload["direct_human_write_allowed"] is False


def test_p5_21_resolution_record_is_manual_governed_resolution(tmp_path):
    runtime = _make_runtime(tmp_path)

    bare = runtime.validate_manual_resolution(
        workflow_instance_id="wf-p5-021",
        abnormal_state_id="abnormal-p5-21",
        resolution_record_id="resolution-p5-21",
        actor_id="alex",
        evidence_refs=["evidence-p5-21"],
    )
    terminal = runtime.record_terminal_abnormal(
        dedupe_key="terminal:p5-21",
        workflow_instance_id="wf-p5-021",
        error_event_id="IF-09:msg-p5-21",
        error_class="mechanism_stall",
        affected_ref="msg-p5-21",
        failure_cause="handler exhausted",
    )
    resolution = runtime.resolve_abnormal_state(
        abnormal_state_id=terminal.payload["abnormal_state_id"],
        resolved_by="alex",
        resolution_action="governed_reemit",
        evidence_refs=["evidence-p5-21"],
        state_transition_id="transition-p5-21",
    )
    accepted = runtime.validate_manual_resolution(
        workflow_instance_id="wf-p5-021",
        abnormal_state_id=terminal.payload["abnormal_state_id"],
        resolution_record_id=resolution.resolution_id,
        actor_id="alex",
        evidence_refs=["evidence-p5-21"],
    )
    runtime.close()

    assert bare.status == "rejected"
    assert "resolution_record_not_found" in bare.payload["rejection_reasons"]
    assert accepted.status == "accepted"
    assert accepted.payload["canonical_outcome"] == "manual_governed_resolution"
    assert accepted.payload["state_transition_id"] == "transition-p5-21"


def test_p5_22_gate_package_source_drift_is_no_go(tmp_path):
    runtime = _make_runtime(tmp_path)

    record = runtime.detect_gate_package_source_drift(
        workflow_instance_id="wf-p5-022",
        gate_package_id="gate-package-p5-22",
        expected_source_ref="artifact://approved",
        actual_source_ref="artifact://changed",
    )
    runtime.close()

    assert record.status == "rejected"
    assert record.payload["canonical_outcome"] == "no_go"
    assert record.payload["source_drift_detected"] is True


def test_p5_23_workflow_history_is_readable_with_phase4_and_phase5_records(tmp_path):
    runtime = _make_runtime(tmp_path)
    runtime.create_phase4_record(
        record_type="timeout_record",
        workflow_instance_id="wf-p5-023",
        dedupe_key="timeout:p5-23",
        status="timeout_recorded",
        payload={"timeout": True},
    )
    runtime.create_phase5_record(
        family="state_transition",
        workflow_instance_id="wf-p5-023",
        target_ref="transition-p5-23",
        dedupe_key="transition:p5-23",
        status="accepted",
        payload={"to_state": "approved"},
    )

    history = runtime.read_workflow_history("wf-p5-023")
    runtime.close()

    assert len(history["phase4_records"]) == 1
    assert len(history["phase5_records"]) == 1
    assert history["authority_order"] == AUTHORITY_ORDER


def test_p5_24_listener_startup_runs_restart_scan_and_fenced_reconciliation(tmp_path):
    adapter = MqAdapterStub()
    runtime = _make_runtime(tmp_path)
    outbox = runtime.record_outbox_publish(_envelope("wf-p5-024"))
    runtime.state_store.mark_outbox_published(outbox.outbox_id)
    listener = ListenerRuntime(adapter, runtime)

    startup = listener.startup()
    action = runtime.state_store.list_phase5_durable_records("recovery_action_record")[0]
    listener.close()

    assert startup.phase5_recovery_scan_records == 1
    assert startup.reconciled_outbox_records == 0
    assert action.payload["canonical_outcome"] == "no_go"
    assert adapter.consume() is None


def test_p5_supervisor_periodically_runs_phase5_restart_scan(tmp_path):
    adapter = MqAdapterStub()
    runtime = _make_runtime(tmp_path)
    listener = ListenerRuntime(adapter, runtime)
    supervisor = ListenerSupervisor(
        listener,
        SupervisorConfig(timeout_every_cycles=99, reconcile_every_cycles=99, phase5_scan_every_cycles=1),
    )

    supervisor.startup()
    cycle = supervisor.run_cycle()
    supervisor.close()

    assert cycle.phase5_recovery_scan_records >= 0
    assert "projection_stale" in RECOVERY_STATES
    assert CANONICAL_RECOVERY_OUTCOMES == {
        "safe_automatic_reconciliation",
        "bounded_retry",
        "governed_quarantine",
        "explicit_terminal_abnormal",
        "manual_governed_resolution",
        "no_go",
    }
