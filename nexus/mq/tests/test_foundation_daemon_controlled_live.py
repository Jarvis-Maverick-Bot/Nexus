import copy

from nexus.mq.adapter import MqAdapterStub, RetryConfig
from nexus.mq.durable_state import DurableStateStore
from nexus.mq.foundation_daemon import _handle
from nexus.mq.foundation_daemon_config import validate_foundation_daemon_config
from nexus.mq.foundation_daemon_lifecycle import build_drain_result
from nexus.mq.foundation_daemon_runtime import FoundationDaemonRuntime
from nexus.mq.foundation_daemon_status import build_foundation_daemon_status
from nexus.mq.message_contracts import build_execution_envelope
from nexus.mq.protocol_routing import route_execution_envelope_dict


RUN_SCOPE = "3_5_wbs15_9_g6_20260607"
RUN_PACKET_REF = "3_5_G5_BOUNDED_CONTROLLED_INSTALL_START_UAT_RUN_PACKET_2026_06_07.md"
AUTHORITY_REF = "3_5_G7_LIVE_DAEMON_BLOCKER_RESOLUTION_PACKET_2026_06_07.md"


def _source_config():
    return {
        "manifest_version": "3.5.foundation-daemon.v1",
        "environment": "local",
        "daemon": {
            "runtime_instance_id": "layer3-foundation-daemon-local",
            "service_name": "nexus-mq-foundation-daemon",
            "default_enabled": False,
            "rollout_phase": "source_only",
            "lifecycle_timeouts": {"start_seconds": 10, "stop_seconds": 10, "drain_seconds": 10},
        },
        "broker": {
            "urls": ["nats://127.0.0.1:4222"],
            "stream": "NEXUS_MQ_FOUNDATION",
            "consumer": "nexus-mq-foundation-daemon",
            "filter_subject": "nexus.3_5.mq.inbox",
            "dlq_subject": "nexus.3_5.mq.dlq",
        },
        "subjects": {
            "allowlist": [
                "nexus.3_5.mq.inbox",
                "nexus.3_5.mq.results",
                "nexus.3_5.mq.retry",
                "nexus.3_5.mq.timeout",
                "nexus.3_5.mq.dlq",
            ]
        },
        "retry": {"max_attempts": 3, "backoff_seconds": [0, 0, 0]},
        "timeout": {"endpoint_first_response_seconds": 30, "endpoint_completion_seconds": 120},
        "stores": {
            "durable_state": {
                "dsn": "sqlite:///tmp/nexus-mq-foundation-daemon-state.sqlite3",
                "required_families": ["foundation_intake", "foundation_retry", "foundation_dlq"],
            },
            "evidence": {
                "dsn": "file://tmp/nexus-mq-foundation-daemon-evidence",
                "required_families": ["status", "intake", "ack", "result", "retry", "dlq", "cleanup"],
            },
        },
        "secret_refs": {"nats_credentials_ref": "secret-ref://local/nats"},
        "feature_flags": {
            "live_publish_enabled": False,
            "business_dispatch_enabled": False,
            "broker_setup_enabled": False,
        },
    }


def _controlled_live_config():
    data = copy.deepcopy(_source_config())
    inbox = f"nexus.3_5.test.{RUN_SCOPE}.inbox"
    data["daemon"]["rollout_phase"] = "controlled_live"
    data["broker"] = {
        "urls": ["nats://127.0.0.1:7422"],
        "stream": f"NEXUS_{RUN_SCOPE.upper()}",
        "consumer": f"nexus-foundation-daemon-{RUN_SCOPE}",
        "filter_subject": inbox,
        "dlq_subject": f"nexus.3_5.test.{RUN_SCOPE}.dlq",
    }
    data["subjects"]["allowlist"] = [
        inbox,
        f"nexus.3_5.test.{RUN_SCOPE}.results",
        f"nexus.3_5.test.{RUN_SCOPE}.retry",
        f"nexus.3_5.test.{RUN_SCOPE}.timeout",
        f"nexus.3_5.test.{RUN_SCOPE}.dlq",
    ]
    data["stores"]["durable_state"]["dsn"] = f"sqlite:///tmp/{RUN_SCOPE}/foundation.sqlite3"
    data["stores"]["evidence"]["dsn"] = f"file://tmp/{RUN_SCOPE}/evidence"
    data["feature_flags"]["live_publish_enabled"] = True
    data["controlled_live"] = {
        "run_id": RUN_SCOPE,
        "run_packet_ref": RUN_PACKET_REF,
        "authorization_ref": AUTHORITY_REF,
        "route_scope": "nexus_local_test_only",
    }
    return data


def _diagnostic_envelope(message_id="msg-controlled-live-001", idempotency_key="idem-controlled-live-001"):
    subject = f"nexus.3_5.test.{RUN_SCOPE}.inbox"
    envelope = build_execution_envelope(
        message_type="Command_Message",
        workflow_instance_id=RUN_SCOPE,
        workflow_type="controlled_3_5_uat",
        workflow_version="15.9",
        producer="thunder",
        payload={
            "command_name": "foundation_controlled_live_diagnostic",
            "target_handler": "layer3.foundation.diagnostic_loopback",
            "input_refs": [f"authority://{RUN_PACKET_REF}"],
            "expected_outputs": ["transport_evidence", "result_candidate"],
            "allowed_side_effects": [],
            "commit_pattern": "local_transactional_default",
            "completion_event_type": "controlled_live_diagnostic_result",
        },
        idempotency_key=idempotency_key,
    ).to_dict()
    envelope["message_id"] = message_id
    envelope["subject"] = subject
    return envelope


def _runtime(tmp_path):
    return FoundationDaemonRuntime(
        config=_controlled_live_config(),
        adapter=MqAdapterStub(retry_config=RetryConfig(max_attempts=3, initial_backoff_ms=0)),
        state_store=DurableStateStore(tmp_path / "controlled-live.sqlite3"),
        evidence_root=tmp_path / "evidence",
    )


def test_foundation_daemon_controlled_live_validates_named_local_test_route():
    result = validate_foundation_daemon_config(_controlled_live_config())

    assert result.valid is True
    assert result.fail_closed is False
    assert result.not_business_completion is True


def test_foundation_daemon_live_publish_without_controlled_authority_fails_closed():
    data = _source_config()
    data["feature_flags"]["live_publish_enabled"] = True

    result = validate_foundation_daemon_config(data)

    assert result.valid is False
    assert "LIVE_PUBLISH_NOT_AUTHORIZED_FOR_SOURCE_GATE" in result.errors


def test_foundation_daemon_controlled_live_rejects_openclaw_live_nats():
    data = _controlled_live_config()
    data["broker"]["urls"] = ["nats://127.0.0.1:4222"]

    result = validate_foundation_daemon_config(data)

    assert result.valid is False
    assert "CONTROLLED_LIVE_ROUTE_NOT_AUTHORIZED" in result.errors


def test_foundation_daemon_controlled_live_rejects_production_or_broad_subjects():
    data = _controlled_live_config()
    data["subjects"]["allowlist"] = ["nexus.3_5.>"]

    result = validate_foundation_daemon_config(data)

    assert result.valid is False
    assert "CONTROLLED_LIVE_SUBJECT_SCOPE_NOT_TEST_SCOPED" in result.errors


def test_foundation_daemon_controlled_live_rejects_business_dispatch():
    data = _controlled_live_config()
    data["feature_flags"]["business_dispatch_enabled"] = True

    result = validate_foundation_daemon_config(data)

    assert result.valid is False
    assert "BUSINESS_DISPATCH_OUT_OF_SCOPE" in result.errors


def test_foundation_daemon_controlled_live_readiness_reports_dependencies():
    status = build_foundation_daemon_status(
        config=_controlled_live_config(),
        broker_ready=True,
        jetstream_ready=True,
        consumer_ready=True,
        evidence_ready=True,
        state_store_ready=True,
    )

    assert status["controlled_live_authorized"] is True
    assert status["daemon_state"] == "controlled_live_ready"
    assert status["overall_ready"] is True
    assert status["business_dispatch_enabled"] is False
    assert status["broker_setup_enabled"] is False
    assert status["not_business_completion"] is True


def test_foundation_daemon_controlled_live_run_authorized_with_injected_adapter():
    payload = _handle("run", _controlled_live_config(), adapter=MqAdapterStub())

    assert payload["command"] == "run"
    assert payload["blocked"] is False
    assert payload["controlled_live"] is True
    assert payload["daemon_started"] is True
    assert payload["result"]["accepted"] is True
    assert payload["result"]["not_business_completion"] is True


class _MissingDeliveryAdapter(MqAdapterStub):
    def consume(self, timeout_ms=None):
        return None


def test_foundation_daemon_controlled_live_missing_delivery_fails_closed(tmp_path):
    runtime = FoundationDaemonRuntime(
        config=_controlled_live_config(),
        adapter=_MissingDeliveryAdapter(),
        state_store=DurableStateStore(tmp_path / "controlled-live.sqlite3"),
        evidence_root=tmp_path / "evidence",
    )

    result = runtime.run_controlled_live_diagnostic(_diagnostic_envelope())
    runtime.close()

    assert result["accepted"] is False
    assert result["action"] == "delivery_not_observed"
    assert result["errors"] == ["CONTROLLED_LIVE_DELIVERY_NOT_OBSERVED"]


def test_foundation_daemon_controlled_live_cli_missing_delivery_fails_closed(tmp_path):
    config = _controlled_live_config()
    config["stores"]["durable_state"]["dsn"] = f"sqlite:///{tmp_path.as_posix()}/{RUN_SCOPE}/foundation.sqlite3"
    config["stores"]["evidence"]["dsn"] = f"file://{tmp_path.as_posix()}/{RUN_SCOPE}/evidence"

    payload = _handle("run", config, adapter=_MissingDeliveryAdapter())

    assert payload["blocked"] is True
    assert payload["daemon_started"] is False
    assert payload["cycles_completed"] == 0
    assert payload["block_reason"] == "CONTROLLED_LIVE_DELIVERY_NOT_OBSERVED"
    assert payload["result"]["accepted"] is False


def test_foundation_daemon_controlled_live_rejects_out_of_scope_test_route():
    envelope = _diagnostic_envelope()
    envelope["subject"] = "nexus.3_5.test.other_scope.inbox"

    result = route_execution_envelope_dict(envelope)

    assert result.valid is False
    assert "UNAUTHORIZED_CONTROLLED_3_5_UAT_SUBJECT_SCOPE" in result.errors


def test_foundation_daemon_controlled_live_diagnostic_publish_consume_result(tmp_path):
    runtime = _runtime(tmp_path)

    result = runtime.run_controlled_live_diagnostic(_diagnostic_envelope())
    health = runtime.adapter.health_probe()
    runtime.close()

    assert result["accepted"] is True
    assert result["duplicate"] is False
    assert result["broker_ack"]["ack_level"] == "broker_received"
    assert result["intake_ack"]["ack_level"] == "consumer_intake"
    assert result["result_candidate"]["result_type"] == "controlled_live_diagnostic"
    assert result["not_business_completion"] is True
    assert health["queued_messages"] == 1


def test_foundation_daemon_controlled_live_ack_after_evidence_state_commit(tmp_path):
    runtime = _runtime(tmp_path)
    envelope = _diagnostic_envelope()

    result = runtime.run_controlled_live_diagnostic(envelope)
    records = runtime.state_store.list_phase5_durable_records(family="foundation_intake")
    ack_evidence = tmp_path / "evidence" / "ack" / f"{envelope['message_id']}.json"
    runtime.close()

    assert result["intake_ack"]["ack_level"] == "consumer_intake"
    assert records[0].payload["ack_after_evidence_and_durable_state"] is True
    assert ack_evidence.exists()


def test_foundation_daemon_controlled_live_evidence_failure_blocks_ack_and_publish(tmp_path):
    runtime = _runtime(tmp_path)
    runtime.evidence_available = False

    result = runtime.run_controlled_live_diagnostic(_diagnostic_envelope())
    ack_log = runtime.adapter.get_ack_log()
    health = runtime.adapter.health_probe()
    runtime.close()

    assert result["accepted"] is False
    assert "EVIDENCE_STORE_UNAVAILABLE" in result["errors"]
    assert ack_log == []
    assert health["queued_messages"] == 0


def test_foundation_daemon_controlled_live_duplicate_suppressed(tmp_path):
    runtime = _runtime(tmp_path)

    first = runtime.run_controlled_live_diagnostic(_diagnostic_envelope(message_id="msg-live-1"))
    second = runtime.run_controlled_live_diagnostic(_diagnostic_envelope(message_id="msg-live-2"))
    health = runtime.adapter.health_probe()
    runtime.close()

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert second["action"] == "duplicate_suppressed"
    assert health["queued_messages"] == 1


def test_foundation_daemon_controlled_live_retry_dlq_recovery_evidenced(tmp_path):
    runtime = _runtime(tmp_path)
    envelope = _diagnostic_envelope()

    retry = runtime.classify_endpoint_timeout(envelope, attempt=1)
    dlq = runtime.classify_endpoint_timeout(envelope, attempt=3)
    recovery = runtime.recover_after_restart()
    retry_records = runtime.state_store.list_phase5_durable_records(family="foundation_retry")
    dlq_records = runtime.state_store.list_phase5_durable_records(family="foundation_dlq")
    runtime.close()

    assert retry.action == "retry_scheduled"
    assert dlq.action == "dlq_recorded"
    assert retry_records[0].payload["endpoint_owned_retry"] is False
    assert dlq_records[0].payload["endpoint_owned_dlq"] is False
    assert recovery["not_business_completion"] is True


def test_foundation_daemon_controlled_live_drain_stop_cleanup_evidenced():
    from nexus.mq.foundation_daemon_lifecycle import build_stop_result

    drain = build_drain_result(inflight_count=0, run_id=RUN_SCOPE, controlled_live=True)
    stop = build_stop_result(run_id=RUN_SCOPE, controlled_live=True, timeout_seconds=10)

    assert drain["cleanup_evidenced"] is True
    assert drain["offline_ready"] is True
    assert stop["cleanup_evidenced"] is True
    assert stop["offline"] is True
    assert stop["not_business_completion"] is True
