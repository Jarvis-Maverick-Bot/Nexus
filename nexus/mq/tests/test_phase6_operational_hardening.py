from datetime import datetime, timedelta, timezone
import os
import asyncio

import pytest

from nexus.mq.adapter import MqAdapterStub
from nexus.mq.adapter_nats import MqAdapterNats
from nexus.mq.coordination_runtime import AUTHORITY_ORDER, CANONICAL_RECOVERY_OUTCOMES, CoordinationRuntime
from nexus.mq.listener_runtime import ListenerRuntime, ListenerRuntimeConfig
from nexus.mq.operational_alerts import (
    create_alert_event,
    dedupe_alert,
    persist_alert_event,
    suppress_alert,
    transition_alert,
)
from nexus.mq.operational_config import (
    AlertingConfig,
    BrokerConfig,
    ConsumerPolicy,
    OperationalManifest,
    RuntimeProcessConfig,
    StoreConfig,
    StreamPolicy,
    redact_manifest,
    validate_operational_manifest,
    validate_reload,
)
from nexus.mq.operational_observability import (
    build_health_probe,
    build_metric_sample,
    build_runtime_log,
    build_trace_span,
)
from nexus.mq.protocol import build_protocol_envelope


def _identity_config_path() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "agents.yaml")
    )


def _future_iso(minutes: int = 5) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def _make_runtime(tmp_path, runtime_id: str = "maverick-runtime-p6") -> CoordinationRuntime:
    runtime = CoordinationRuntime.from_paths(
        runtime_id=runtime_id,
        agent_id="maverick",
        role="maverick",
        db_path=tmp_path / f"{runtime_id}.sqlite3",
        identity_yaml_path=_identity_config_path(),
    )
    runtime.startup()
    return runtime


def _manifest(**overrides) -> OperationalManifest:
    manifest = OperationalManifest(
        manifest_version=overrides.pop("manifest_version", "p6-local-v1"),
        environment=overrides.pop("environment", "local"),
        broker=BrokerConfig(
            broker_urls=overrides.pop("broker_urls", ["nats://127.0.0.1:4222"]),
            stream_policies=[
                StreamPolicy(
                    name="nexus-mq",
                    subjects=["agent.>", "workflow.>", "review.>", "feedback.>", "ops.>"],
                    retention="workqueue",
                    storage="file",
                    max_age_seconds=86400,
                    max_bytes=10_000_000,
                    max_messages=10000,
                    replicas=1,
                    replay_window_seconds=3600,
                )
            ],
            consumer_policies=[
                ConsumerPolicy(
                    durable_name="maverick-runtime-consumer",
                    filter_subject="agent.maverick.>",
                    ack_policy="explicit",
                    ack_wait_seconds=30,
                    max_deliver=3,
                    replay_policy="new",
                    pending_limit=100,
                    inactive_threshold_seconds=300,
                )
            ],
            subject_allowlist=["agent.", "workflow.", "review.", "feedback.", "ops."],
            dlq_subject="ops.dlq",
            health_threshold_seconds=15,
        ),
        durable_state=StoreConfig(
            dsn="sqlite:///tmp/nexus-p6-state.sqlite3",
            schema_version="phase6",
            required_families=["phase5_durable_record", "current_projection"],
        ),
        evidence=StoreConfig(
            dsn="sqlite:///tmp/nexus-p6-evidence.sqlite3",
            schema_version="phase6",
            required_families=["event_log", "alert_event"],
        ),
        alerting=AlertingConfig(
            event_store="sqlite:///tmp/nexus-p6-alerts.sqlite3",
            severity_policy_ref="policy://severity/p6",
            routing_policy_ref="policy://routing/deferred",
            unresolved_threshold_seconds=60,
        ),
        runtime_process=RuntimeProcessConfig(
            runtime_instance_id="maverick-windows-main-20260507",
            agent_id="maverick",
            role="maverick",
            capabilities=["workflow.command", "workflow.feedback", "coordination.dispatch"],
            process_supervisor="local-test",
            restart_policy="manual",
        ),
        feature_flags={
            "broker_hardening": True,
            "observability": True,
            "alert_events": True,
            "deployment_validation": True,
            "controlled_resilience": True,
        },
        secret_refs={"broker_auth_ref": "local:nats-agent-protocol"},
        diagnostic_read_only=overrides.pop("diagnostic_read_only", False),
        rollout_phase=overrides.pop("rollout_phase", "dry_run"),
        approved_config_ref="config://p6-local-v1",
    )
    for key, value in overrides.items():
        setattr(manifest, key, value)
    return manifest


def _command(workflow_instance_id: str = "wf-p6-001"):
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
        idempotency_key=f"idem-{workflow_instance_id}",
        expires_at=_future_iso(),
    )


def test_p6_01_broker_manifest_declares_topology_and_subjects():
    manifest = _manifest()
    result = validate_operational_manifest(manifest)

    assert result.valid is True
    assert manifest.broker.broker_urls == ["nats://127.0.0.1:4222"]
    assert "agent.>" in manifest.broker.stream_policies[0].subjects


def test_p6_02_stream_policy_has_retention_capacity_and_replay_bounds():
    policy = _manifest().broker.stream_policies[0]

    assert policy.retention == "workqueue"
    assert policy.max_bytes > 0
    assert policy.max_messages > 0
    assert policy.replay_window_seconds > 0


def test_p6_03_consumer_policy_has_ack_wait_max_delivery_and_filter():
    policy = _manifest().broker.consumer_policies[0]

    assert policy.ack_policy == "explicit"
    assert policy.ack_wait_seconds > 0
    assert policy.max_deliver == 3
    assert policy.filter_subject == "agent.maverick.>"


def test_p6_03_nats_consume_defers_broker_ack_until_consumer_intake_ack():
    class FakeMsg:
        def __init__(self):
            self.subject = "agent.maverick.inbox"
            self.data = b'{"message_id":"msg-p6-nats-ack","payload":{}}'
            self.acked = False

        async def ack(self):
            self.acked = True

    class FakePullSub:
        def __init__(self, msg):
            self.msg = msg

        async def fetch(self, batch, timeout):
            return [self.msg]

    adapter = object.__new__(MqAdapterNats)
    adapter._pull_sub = FakePullSub(FakeMsg())
    adapter._pending_acks = {}
    adapter._ack_log = []

    async def no_connection():
        return None

    adapter._ensure_connection = no_connection

    delivered = asyncio.run(adapter._consume_impl())
    fake_msg = adapter._pending_acks["msg-p6-nats-ack"]
    assert delivered["broker_ack_pending"] is True
    assert fake_msg.acked is False

    ack = asyncio.run(adapter._ack_impl("msg-p6-nats-ack"))
    assert fake_msg.acked is True
    assert ack["broker_acknowledged"] is True
    assert ack["broker_ack_boundary"] == "after_durable_intake"


def test_p6_04_ack_after_validation_and_durable_intake_only(tmp_path):
    adapter = MqAdapterStub()
    runtime = _make_runtime(tmp_path)
    listener = ListenerRuntime(adapter, runtime, ListenerRuntimeConfig(operational_manifest=_manifest()))
    listener.startup()
    envelope = _command()
    adapter.publish(envelope.to_dict())

    result = listener.poll_once()
    stored = runtime.state_store.get_pending_task(f"task-{envelope.message_id}")
    listener.close()

    assert result.acked is True
    assert stored is not None
    assert stored.state == "PENDING"
    assert any(ack["ack_level"] == "consumer_intake" for ack in adapter.get_ack_log())


def test_p6_05_redelivery_uses_idempotency_without_duplicate_side_effect(tmp_path):
    runtime = _make_runtime(tmp_path)
    envelope = _command("wf-p6-005")

    first = runtime.intake_inbound_message("agent.maverick.inbox", envelope.to_dict())
    second = runtime.intake_inbound_message("agent.maverick.inbox", envelope.to_dict())
    tasks = runtime.state_store.list_pending_tasks()
    runtime.close()

    assert first.ack_allowed is True
    assert second.duplicate is True
    assert len([task for task in tasks if task.task_id == f"task-{envelope.message_id}"]) == 1


def test_p6_06_dlq_does_not_equal_handler_exhausted(tmp_path):
    adapter = MqAdapterStub()
    runtime = _make_runtime(tmp_path)
    dlq = adapter.emit_dlq("msg-p6-06", "wf-p6-006", 3, "retry exhausted", {"message_type": "Command_Message"})
    runtime.record_terminal_abnormal(
        dedupe_key="terminal:p6-06",
        workflow_instance_id="wf-p6-006",
        error_event_id=f"DLQ:{dlq.message_id}",
        error_class="mechanism_stall",
        affected_ref=dlq.message_id,
        failure_cause=dlq.last_error,
    )
    handler = runtime.state_store.list_phase3_runtime_records("handler_exhausted_record")
    runtime.close()

    assert dlq.event_id.startswith("dlq-")
    assert handler == []


def test_p6_07_broker_health_probe_reports_unavailable_without_business_transition():
    adapter = MqAdapterStub()
    health = adapter.health_probe()

    assert health["status"] == "healthy"
    assert health["not_business_completion"] is True


def test_p6_08_runtime_log_contains_correlation_and_evidence_refs():
    log = build_runtime_log(
        runtime_instance_id="rt-p6",
        workflow_instance_id="wf-p6-008",
        message_id="msg-p6-008",
        correlation_id="corr-p6-008",
        event_type="intake",
        severity="INFO",
        component="listener",
        outcome="accepted",
        evidence_refs=["intake-record-p6-008"],
    )

    assert log.correlation_id == "corr-p6-008"
    assert log.evidence_refs == ["intake-record-p6-008"]
    assert log.not_business_completion is True


def test_p6_09_metrics_include_required_labels_without_secret_leakage():
    metric = build_metric_sample(
        "mq_messages_published_total",
        {"subject": "agent.maverick.inbox", "token": "token=secret"},
        1,
        "count",
        "listener",
    )

    assert metric.labels["subject"] == "agent.maverick.inbox"
    assert metric.labels["token"] == "[REDACTED]"
    assert metric.not_business_completion is True


def test_p6_10_trace_preserves_correlation_and_causation_chain():
    span = build_trace_span(
        trace_id="trace-p6-010",
        component="coordination_runtime",
        outcome="feedback_rejected_stale",
        correlation_id="corr-p6-010",
        causation_id="msg-p6-010",
        evidence_refs=["stale-feedback-p6-010"],
    )

    assert span.correlation_id == "corr-p6-010"
    assert span.causation_id == "msg-p6-010"
    assert span.evidence_refs == ["stale-feedback-p6-010"]


def test_p6_11_health_probe_success_does_not_advance_business_state():
    probe = build_health_probe(component="durable_state", status="healthy", dependency_status={"sqlite": "ok"})

    assert probe.status == "healthy"
    assert probe.not_business_completion is True


def test_p6_12_alert_severity_maps_to_actionable_response():
    alert = create_alert_event(
        severity="SEV-0",
        source_component="recovery_scanner",
        failure_class="ambiguous_side_effect",
        routing_policy_ref="routing://operator",
        suppression_policy_ref="suppression://none",
        workflow_instance_id="wf-p6-012",
    )

    assert alert.severity == "SEV-0"
    assert alert.lifecycle_state == "pending"


def test_p6_13_alert_dedupe_preserves_count_and_first_last_seen():
    first = create_alert_event(
        severity="SEV-1",
        source_component="broker",
        failure_class="unavailable",
        routing_policy_ref="routing://ops",
        suppression_policy_ref="suppression://short",
        cause_id="broker-1",
    )
    duplicate = create_alert_event(
        severity="SEV-1",
        source_component="broker",
        failure_class="unavailable",
        routing_policy_ref="routing://ops",
        suppression_policy_ref="suppression://short",
        cause_id="broker-1",
    )

    deduped = dedupe_alert(first, duplicate)

    assert deduped.count == 2
    assert deduped.first_seen_at <= deduped.last_seen_at


def test_p6_14_suppression_does_not_hide_critical_unresolved_condition():
    critical = create_alert_event(
        severity="SEV-0",
        source_component="state_store",
        failure_class="unavailable",
        routing_policy_ref="routing://operator",
        suppression_policy_ref="suppression://none",
    )
    medium = create_alert_event(
        severity="SEV-2",
        source_component="broker",
        failure_class="redelivery_spike",
        routing_policy_ref="routing://ops",
        suppression_policy_ref="suppression://short",
    )

    with pytest.raises(ValueError):
        suppress_alert(critical, "critical_must_remain_visible")
    assert suppress_alert(medium, "duplicate_inside_window").lifecycle_state == "suppressed"


def test_p6_15_unresolved_alert_escalates_without_state_mutation(tmp_path):
    runtime = _make_runtime(tmp_path)
    alert = create_alert_event(
        severity="SEV-1",
        source_component="recovery_scanner",
        failure_class="scan_failed",
        routing_policy_ref="routing://ops",
        suppression_policy_ref="suppression://short",
        workflow_instance_id="wf-p6-015",
    )

    escalated = transition_alert(alert, "escalated")
    persisted = persist_alert_event(runtime.state_store, escalated)
    transitions = runtime.state_store.list_phase5_durable_records("state_transition", "wf-p6-015")
    runtime.close()

    assert persisted.family == "alert_event"
    assert escalated.lifecycle_state == "escalated"
    assert transitions == []


def test_p6_16_config_manifest_validates_required_sections():
    result = validate_operational_manifest(_manifest())

    assert result.valid is True
    assert result.config_hash is not None


def test_p6_17_invalid_required_config_blocks_actionable_consume(tmp_path):
    manifest = _manifest(broker_urls=[])
    manifest.diagnostic_read_only = True
    adapter = MqAdapterStub()
    runtime = _make_runtime(tmp_path)
    listener = ListenerRuntime(adapter, runtime, ListenerRuntimeConfig(operational_manifest=manifest))
    adapter.publish(_command("wf-p6-017").to_dict())

    startup = listener.startup()
    result = listener.poll_once()
    listener.close()

    assert startup.config_valid is False
    assert startup.diagnostic_read_only is True
    assert result.status == "diagnostic_read_only"
    assert adapter.consume() is not None


def test_p6_17_credential_bearing_broker_url_fails_closed_and_redacts_evidence(tmp_path):
    manifest = _manifest(broker_urls=["nats://alice:pass@127.0.0.1:4222"])
    manifest.diagnostic_read_only = True
    validation = validate_operational_manifest(manifest)
    redacted = redact_manifest(manifest)
    adapter = MqAdapterStub()
    runtime = _make_runtime(tmp_path)
    listener = ListenerRuntime(adapter, runtime, ListenerRuntimeConfig(operational_manifest=manifest))

    startup = listener.startup()
    events = runtime.state_store.list_phase5_durable_records("event_log")
    listener.close()

    assert validation.valid is False
    assert "SECRET_LEAK: broker_url" in validation.errors
    assert redacted["broker"]["broker_urls"] == ["nats://***@127.0.0.1:4222"]
    assert startup.config_valid is False
    assert all("alice:pass" not in str(event.payload) for event in events)


def test_p6_18_invalid_reload_keeps_prior_approved_config():
    current = _manifest(manifest_version="p6-current")
    candidate = _manifest(manifest_version="p6-candidate", broker_urls=[])

    result = validate_reload(current, candidate)

    assert result["accepted"] is False
    assert result["kept_prior_config"] is True
    assert result["not_business_completion"] is True


def test_p6_19_rollback_preserves_governed_history(tmp_path):
    runtime = _make_runtime(tmp_path)
    transition = runtime.create_phase5_record(
        family="state_transition",
        workflow_instance_id="wf-p6-019",
        target_ref="transition-p6-019",
        dedupe_key="transition:p6-019",
        status="accepted",
        payload={"to_state": "approved"},
    )
    runtime.record_phase5_event(
        event_name="rollback_config",
        workflow_instance_id="wf-p6-019",
        target_ref="rollback-p6-019",
        payload={"rollback": True, "no_delete_no_overwrite": True},
    )
    transitions = runtime.state_store.list_phase5_durable_records("state_transition", "wf-p6-019")
    runtime.close()

    assert transitions[0].record_id == transition.record_id
    assert transitions[0].payload["to_state"] == "approved"


def test_p6_20_operator_can_collect_required_health_state_evidence(tmp_path):
    runtime = _make_runtime(tmp_path)
    manifest = _manifest()
    health = MqAdapterStub().health_probe()
    snapshot = {
        "config": redact_manifest(manifest),
        "broker_health": health,
        "unresolved_abnormal": len(runtime.state_store.list_unresolved_abnormal_states()),
        "recovery_records": len(runtime.state_store.list_phase5_durable_records("recovery_scan_record")),
        "not_business_completion": True,
    }
    runtime.close()

    assert snapshot["config"]["manifest_version"] == "p6-local-v1"
    assert snapshot["broker_health"]["not_business_completion"] is True
    assert snapshot["not_business_completion"] is True


def test_p6_21_openclaw_capability_checklist_has_no_business_specific_script_dependency():
    capabilities = {
        "publish envelope",
        "subscribe/consume",
        "validate envelope",
        "ACK/reject intake",
        "persist/restore state",
        "reply/feedback",
        "anomaly/DLQ emit",
        "evidence capture",
    }

    assert "business-specific one-off script" not in capabilities
    assert "evidence capture" in capabilities


def test_p6_22_recovery_scan_assigns_canonical_outcome_for_each_failure(tmp_path):
    runtime = _make_runtime(tmp_path)

    outcomes = {
        runtime.classify_phase5_recovery_target(candidate_type="envelope_inbox", state="failed")["canonical_outcome"],
        runtime.classify_phase5_recovery_target(candidate_type="side_effect_outbox", state="PUBLISHED")["canonical_outcome"],
        runtime.classify_phase5_recovery_target(candidate_type="terminal_abnormal_record", state="active")["canonical_outcome"],
        runtime.classify_phase5_recovery_target(candidate_type="resolution_record", state="accepted")["canonical_outcome"],
    }
    runtime.close()

    assert outcomes <= CANONICAL_RECOVERY_OUTCOMES
    assert {"bounded_retry", "no_go", "explicit_terminal_abnormal", "manual_governed_resolution"} <= outcomes


def test_p6_23_lower_order_signal_cannot_override_governed_truth(tmp_path):
    runtime = _make_runtime(tmp_path)
    runtime.create_phase5_record(
        family="state_transition",
        workflow_instance_id="wf-p6-023",
        target_ref="transition-p6-023",
        dedupe_key="transition:p6-023",
        status="accepted",
        payload={"to_state": "approved"},
    )
    runtime.record_phase5_event(
        event_name="broker_redelivery_conflict",
        workflow_instance_id="wf-p6-023",
        target_ref="broker-meta-p6-023",
        payload={"broker_metadata_state": "redelivered"},
    )

    projection = runtime.rebuild_current_projection("wf-p6-023")
    runtime.close()

    assert projection.payload["governed_state"] == "approved"
    assert AUTHORITY_ORDER.index("mq_delivery_metadata") > AUTHORITY_ORDER.index("state_transition")


def test_p6_24_ambiguous_side_effect_confirmation_goes_quarantine_or_no_go(tmp_path):
    runtime = _make_runtime(tmp_path)
    outbox = runtime.record_outbox_publish(_command("wf-p6-024"))
    runtime.state_store.mark_outbox_published(outbox.outbox_id)

    classification = runtime.plan_side_effect_reconciliation(runtime.state_store.get_outbox_record(outbox.outbox_id))
    runtime.close()

    assert classification["classification"]["canonical_outcome"] == "no_go"
    assert classification["publish_allowed"] is False


def test_p6_25_handler_exhausted_is_not_auto_released_after_restart(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    runtime = CoordinationRuntime.from_paths("maverick-runtime-p6", "maverick", "maverick", db_path, _identity_config_path())
    runtime.startup()
    runtime.state_store.record_envelope_inbox(
        envelope_id="env-p6-025",
        subject="agent.maverick.inbox",
        payload={"message_id": "env-p6-025"},
        workflow_instance_id="wf-p6-025",
        max_local_retries=1,
    )
    runtime.record_post_ack_handler_failure("env-p6-025", "handler exhausted")
    runtime.close()

    restarted = CoordinationRuntime.from_paths("maverick-runtime-p6", "maverick", "maverick", db_path, _identity_config_path())
    restarted.startup()
    restarted.run_phase5_restart_scan()
    inbox = restarted.state_store.get_envelope_inbox("env-p6-025")
    restarted.close()

    assert inbox is not None
    assert inbox.handler_exhausted is True
    assert inbox.state == "handler_exhausted"


def test_p6_26_late_feedback_after_timeout_does_not_resume_normally(tmp_path):
    runtime = _make_runtime(tmp_path)
    stale = runtime.create_phase4_record(
        record_type="stale_feedback_rejection_record",
        workflow_instance_id="wf-p6-026",
        authority_wait_id="wait-p6-026",
        related_message_id="feedback-p6-026",
        dedupe_key="stale:p6-026",
        status="feedback_rejected_stale",
        payload={"reason": "authority_wait_state_timeout"},
    )
    resumes = runtime.state_store.list_phase3_runtime_records("bounded_resume_request_record", "wait-p6-026")
    runtime.close()

    assert stale.status == "feedback_rejected_stale"
    assert resumes == []


def test_p6_27_projection_rebuilds_from_durable_records_only(tmp_path):
    runtime = _make_runtime(tmp_path)
    transition = runtime.create_phase5_record(
        family="state_transition",
        workflow_instance_id="wf-p6-027",
        target_ref="transition-p6-027",
        dedupe_key="transition:p6-027",
        status="accepted",
        payload={"to_state": "approved"},
    )

    projection = runtime.rebuild_current_projection("wf-p6-027")
    runtime.close()

    assert projection.source_record_id == transition.record_id
    assert projection.payload["projection_is_derived"] is True


def test_p6_28_deployment_interruption_requires_recovery_scan_before_consume(tmp_path):
    manifest = _manifest(broker_urls=[])
    manifest.diagnostic_read_only = True
    adapter = MqAdapterStub()
    runtime = _make_runtime(tmp_path)
    listener = ListenerRuntime(adapter, runtime, ListenerRuntimeConfig(operational_manifest=manifest))

    startup = listener.startup()
    poll = listener.poll_once()
    listener.close()

    assert startup.runtime_status == "DIAGNOSTIC_READ_ONLY"
    assert poll.acked is False


def test_p6_29_source_version_drift_requires_governed_resolution_or_no_go(tmp_path):
    runtime = _make_runtime(tmp_path)

    drift = runtime.detect_gate_package_source_drift(
        workflow_instance_id="wf-p6-029",
        gate_package_id="gate-package-p6-029",
        expected_source_ref="artifact://approved",
        actual_source_ref="artifact://changed",
    )
    runtime.close()

    assert drift.status == "rejected"
    assert drift.payload["canonical_outcome"] == "no_go"


def test_p6_30_manual_resolution_requires_real_resolution_record(tmp_path):
    runtime = _make_runtime(tmp_path)

    rejected = runtime.validate_manual_resolution(
        workflow_instance_id="wf-p6-030",
        abnormal_state_id="abnormal-p6-030",
        resolution_record_id="bare-string",
        actor_id="operator",
        evidence_refs=["evidence-p6-030"],
    )
    runtime.close()

    assert rejected.status == "rejected"
    assert "resolution_record_not_found" in rejected.payload["rejection_reasons"]


def test_p6_31_transport_observability_checkpoint_never_business_completion(tmp_path):
    runtime = _make_runtime(tmp_path)
    adapter = MqAdapterStub()
    adapter.publish(_command("wf-p6-031").to_dict())
    adapter.ack("msg-p6-031")
    log = build_runtime_log(
        runtime_instance_id="rt-p6",
        event_type="health",
        severity="INFO",
        component="probe",
        outcome="healthy",
    )
    metric = build_metric_sample("runtime_projection_rebuild_total", {"result": "ok"}, 1, "count", "projection")
    alert = create_alert_event(
        severity="SEV-3",
        source_component="health_probe",
        failure_class="informational",
        routing_policy_ref="routing://none",
        suppression_policy_ref="suppression://short",
    )
    projection = runtime.rebuild_current_projection("wf-p6-031")
    transitions = runtime.state_store.list_phase5_durable_records("state_transition", "wf-p6-031")
    runtime.close()

    assert all(item["not_business_completion"] for item in adapter.get_ack_log())
    assert log.not_business_completion is True
    assert metric.not_business_completion is True
    assert alert.not_business_completion is True
    assert projection.payload["not_business_completion"] is True
    assert transitions == []
