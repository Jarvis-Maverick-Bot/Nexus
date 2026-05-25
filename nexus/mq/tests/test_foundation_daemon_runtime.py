import json
import subprocess
import sys

from nexus.mq.adapter import MqAdapterStub, RetryConfig
from nexus.mq.durable_state import DurableStateStore
from nexus.mq.foundation_daemon_config import load_foundation_daemon_config
from nexus.mq.foundation_daemon_runtime import FoundationDaemonRuntime
from nexus.mq.foundation_daemon_status import build_foundation_daemon_status
from nexus.mq.message_contracts import build_execution_envelope


def _command(message_id="msg-foundation-001", idempotency_key="idem-foundation-001"):
    envelope = build_execution_envelope(
        message_type="Command_Message",
        workflow_instance_id="wf-foundation-001",
        workflow_type="layer3_mq_foundation",
        workflow_version="15.9",
        producer="thunder",
        payload={
            "command_name": "foundation_intake_probe",
            "target_handler": "layer3.foundation.intake",
            "input_refs": ["authority://wbs15.9/source"],
            "expected_outputs": ["transport_evidence"],
            "allowed_side_effects": [],
            "commit_pattern": "local_transactional_default",
            "completion_event_type": "foundation_intake_recorded",
        },
        idempotency_key=idempotency_key,
    )
    data = envelope.to_dict()
    data["message_id"] = message_id
    data["subject"] = "nexus.3_5.mq.inbox"
    return data


def _business_message():
    envelope = build_execution_envelope(
        message_type="Business_Message",
        workflow_instance_id="wf-foundation-001",
        workflow_type="layer3_mq_foundation",
        workflow_version="15.9",
        producer="thunder",
        payload={
            "business_event_type": "state_accepted",
            "transition_id": "transition-001",
            "previous_state": "pending",
            "new_state": "accepted",
            "validation_result": "accepted",
            "evidence_refs": ["evidence://business"],
        },
        idempotency_key="idem-business-001",
    )
    data = envelope.to_dict()
    data["message_id"] = "msg-business-001"
    data["subject"] = "nexus.3_5.mq.inbox"
    return data


def _runtime(tmp_path, *, adapter=None):
    config = load_foundation_daemon_config("config/mq/foundation_daemon.example.yaml")
    state_store = DurableStateStore(tmp_path / "foundation.sqlite3")
    return FoundationDaemonRuntime(
        config=config,
        adapter=adapter or MqAdapterStub(retry_config=RetryConfig(max_attempts=3, initial_backoff_ms=0)),
        state_store=state_store,
        evidence_root=tmp_path / "evidence",
    )


def test_foundation_daemon_ack_is_not_progress(tmp_path):
    runtime = _runtime(tmp_path)

    result = runtime.intake_message("nexus.3_5.mq.inbox", _command())
    records = runtime.state_store.list_phase5_durable_records(family="foundation_intake")
    runtime.close()

    assert result.ack["ack_level"] == "consumer_intake"
    assert result.progress_state is None
    assert result.not_business_completion is True
    assert records[0].status == "intake_recorded"
    assert records[0].payload["ack_is_not_progress"] is True


def test_foundation_daemon_rejects_business_message_intake_without_ack(tmp_path):
    runtime = _runtime(tmp_path)

    result = runtime.intake_message("nexus.3_5.mq.inbox", _business_message())
    records = runtime.state_store.list_phase5_durable_records(family="foundation_intake")
    ack_log = runtime.adapter.get_ack_log()
    runtime.close()

    assert result.accepted is False
    assert "BUSINESS_MESSAGE_INTAKE_OUT_OF_SCOPE" in result.errors
    assert result.ack is None
    assert records == []
    assert ack_log == []


def test_foundation_daemon_rejects_private_agent_like_dispatch_without_ack(tmp_path):
    runtime = _runtime(tmp_path)
    envelope = _command()
    envelope["payload"]["target_handler"] = "private_agent.invoke"
    envelope["payload"]["allowed_side_effects"] = ["private_agent_invocation"]

    result = runtime.intake_message("nexus.3_5.mq.inbox", envelope)
    ack_log = runtime.adapter.get_ack_log()
    runtime.close()

    assert result.accepted is False
    assert "PRIVATE_AGENT_INVOCATION_OUT_OF_SCOPE" in result.errors
    assert result.ack is None
    assert ack_log == []


def test_foundation_daemon_evidence_failure_blocks_intake_ack_and_durable_record(tmp_path):
    runtime = _runtime(tmp_path)
    runtime.evidence_available = False

    result = runtime.intake_message("nexus.3_5.mq.inbox", _command())
    records = runtime.state_store.list_phase5_durable_records(family="foundation_intake")
    ack_log = runtime.adapter.get_ack_log()
    runtime.close()

    assert result.accepted is False
    assert "EVIDENCE_STORE_UNAVAILABLE" in result.errors
    assert result.ack is None
    assert records == []
    assert ack_log == []


def test_foundation_daemon_invalid_subject_rejected_before_publish(tmp_path):
    runtime = _runtime(tmp_path)
    envelope = _command()

    result = runtime.validate_publish_request("nexus.3_5.mq.inbox.extra", envelope)
    runtime.close()

    assert result.allowed is False
    assert "SUBJECT_NOT_ALLOWED: nexus.3_5.mq.inbox.extra" in result.errors
    assert result.publish_attempted is False


def test_foundation_daemon_duplicate_completed_key_is_suppressed(tmp_path):
    runtime = _runtime(tmp_path)
    first = runtime.intake_message("nexus.3_5.mq.inbox", _command(message_id="msg-1"))
    second = runtime.intake_message("nexus.3_5.mq.inbox", _command(message_id="msg-2"))
    records = runtime.state_store.list_phase5_durable_records(family="foundation_intake")
    runtime.close()

    assert first.duplicate is False
    assert second.duplicate is True
    assert second.action == "duplicate_suppressed"
    assert len(records) == 1


def test_foundation_daemon_duplicate_inflight_key_is_reconciled(tmp_path):
    runtime = _runtime(tmp_path)
    runtime.state_store.create_phase5_durable_record(
        family="foundation_intake",
        status="inflight",
        payload={"message_id": "msg-original"},
        workflow_instance_id="wf-foundation-001",
        dedupe_key="idem-foundation-001",
    )

    result = runtime.intake_message("nexus.3_5.mq.inbox", _command(message_id="msg-redelivery"))
    runtime.close()

    assert result.duplicate is True
    assert result.action == "duplicate_inflight_reconciled"
    assert result.ack["ack_level"] == "consumer_intake"


def test_foundation_daemon_endpoint_timeout_retries_centrally(tmp_path):
    runtime = _runtime(tmp_path)

    result = runtime.classify_endpoint_timeout(_command(), attempt=1)
    retry_records = runtime.state_store.list_phase5_durable_records(family="foundation_retry")
    runtime.close()

    assert result.action == "retry_scheduled"
    assert result.endpoint_owned_retry is False
    assert retry_records[0].status == "scheduled"
    assert retry_records[0].payload["attempt"] == 1


def test_foundation_daemon_retry_exhaustion_records_dlq(tmp_path):
    runtime = _runtime(tmp_path)

    result = runtime.classify_endpoint_timeout(_command(), attempt=3)
    dlq_records = runtime.state_store.list_phase5_durable_records(family="foundation_dlq")
    runtime.close()

    assert result.action == "dlq_recorded"
    assert result.endpoint_owned_dlq is False
    assert dlq_records[0].status == "recorded"
    assert dlq_records[0].payload["not_business_completion"] is True


def test_foundation_daemon_replay_safe_after_restart(tmp_path):
    runtime = _runtime(tmp_path)
    runtime.intake_message("nexus.3_5.mq.inbox", _command())
    runtime.close()

    restarted = _runtime(tmp_path)
    replay = restarted.recover_after_restart()
    restarted.close()

    assert replay["replayed_records"] == 1
    assert replay["classification"] == "safe_replay_no_business_execution"
    assert replay["not_business_completion"] is True


def test_foundation_daemon_evidence_failure_blocks_publish(tmp_path):
    runtime = _runtime(tmp_path)
    runtime.evidence_available = False

    result = runtime.validate_publish_request("nexus.3_5.mq.inbox", _command())
    runtime.close()

    assert result.allowed is False
    assert "EVIDENCE_STORE_UNAVAILABLE" in result.errors
    assert result.publish_attempted is False


def test_foundation_daemon_status_requires_source_only_readiness_not_live_readiness():
    status = build_foundation_daemon_status(
        config=load_foundation_daemon_config("config/mq/foundation_daemon.example.yaml"),
        broker_ready=False,
        state_store_ready=True,
        evidence_ready=True,
    )

    assert status["route_ready_source_only"] is True
    assert status["overall_ready"] is False
    assert status["daemon_started"] is False
    assert status["not_business_completion"] is True


def test_foundation_daemon_cli_start_once_is_source_only_route_readiness():
    command = [
        sys.executable,
        "-m",
        "nexus.mq.foundation_daemon",
        "start-once",
        "--config",
        "config/mq/foundation_daemon.example.yaml",
        "--cycles",
        "1",
    ]

    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["daemon_started"] is False
    assert payload["route_ready_source_only"] is True
    assert payload["not_live_uat"] is True


def test_foundation_daemon_cli_readiness_exits_nonzero_when_overall_not_ready():
    command = [
        sys.executable,
        "-m",
        "nexus.mq.foundation_daemon",
        "readiness",
        "--config",
        "config/mq/foundation_daemon.example.yaml",
    ]

    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    payload = json.loads(completed.stdout)

    assert completed.returncode == 2
    assert payload["overall_ready"] is False
    assert payload["route_ready_source_only"] is True


def test_foundation_daemon_cli_lifecycle_surfaces_are_present_and_non_live():
    for command_name in ("run", "drain", "stop"):
        command = [
            sys.executable,
            "-m",
            "nexus.mq.foundation_daemon",
            command_name,
            "--config",
            "config/mq/foundation_daemon.example.yaml",
        ]

        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        payload = json.loads(completed.stdout)

        assert payload["command"] == command_name
        assert payload["daemon_started"] is False
        assert payload["not_live_uat"] is True
        if command_name == "run":
            assert completed.returncode == 2
            assert payload["blocked"] is True
        else:
            assert completed.returncode == 0
