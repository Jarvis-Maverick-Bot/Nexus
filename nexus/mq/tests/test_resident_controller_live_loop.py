import json

from nexus.mq.resident_controller.cli import main
from nexus.mq.resident_controller.live_loop import run_start_once
from nexus.mq.tests.test_resident_controller_config import _config


class FakeResidentBroker:
    def __init__(self, inbound_events=None):
        self.inbound_events = list(inbound_events or [])
        self.connected_url = ""
        self.subscriptions = []
        self.published = []
        self.drained = False
        self.closed = False

    def connect(self, *, nats_url, auth_ref, connect_timeout_seconds):
        self.connected_url = nats_url

    def subscribe(self, subject, handler):
        self.subscriptions.append(subject)
        for event in self.inbound_events:
            if _subject_matches(subject, event["subject"]):
                handler(event["subject"], event["payload"])

    def publish(self, subject, payload):
        self.published.append((subject, payload))

    def drain(self):
        self.drained = True

    def close(self):
        self.closed = True


def _bounded_config(tmp_path, **overrides):
    config = _config()
    config["controller"]["launch_mode"] = "bounded_uat"
    config["controller"]["runtime_instance_id"] = "run-5b-local"
    config["controller"]["run_id"] = "run-5b-local"
    config["policy"]["require_non_loopback_for_distributed_uat"] = False
    config["subjects"]["subscribe_allowlist"] = [
        "nexus.4_19.wbs7_19_14.*.registration.>",
        "nexus.4_19.wbs7_19_14.*.readiness.>",
        "nexus.4_19.wbs7_19_14.*.heartbeat.>",
        "nexus.4_19.wbs7_19_14.*.ack.>",
        "nexus.4_19.wbs7_19_14.*.progress.>",
        "nexus.4_19.wbs7_19_14.*.evidence.>",
        "nexus.4_19.wbs7_19_14.*.result_candidate.>",
        "nexus.4_19.wbs7_19_14.*.offline.>",
    ]
    config["subjects"]["publish_allowlist"] = [
        "nexus.4_19.wbs7_19_14.*.controller.init",
        "nexus.4_19.wbs7_19_14.*.assignment",
        "nexus.4_19.wbs7_19_14.*.assignment.duplicate_replay",
        "nexus.4_19.wbs7_19_14.*.drain",
    ]
    config["evidence"]["root"] = str(tmp_path / "evidence")
    config["uat"] = {
        "max_runtime_seconds": 0,
        "assignment_enabled": True,
        "assignment_id": "assign-5b-local",
        "idempotency_key": "idem-5b-local",
    }
    config.update(overrides)
    return config


def test_start_once_bounded_loop_connects_subscribes_dispatches_and_records_candidates(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_URL", "nats://127.0.0.1:7422")
    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_AUTH_REF", "local-uat-auth-ref")
    broker = FakeResidentBroker(
        inbound_events=[
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.registration.ready",
                "payload": {"agent_id": "jarvis"},
            },
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.readiness.ready",
                "payload": {"agent_id": "jarvis"},
            },
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.heartbeat.tick",
                "payload": {"agent_id": "jarvis"},
            },
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.ack.assignment",
                "payload": {"assignment_id": "assign-5b-local"},
            },
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.progress.assignment",
                "payload": {"assignment_id": "assign-5b-local"},
            },
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.evidence.assignment",
                "payload": {"assignment_id": "assign-5b-local"},
            },
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.result_candidate.done",
                "payload": {"assignment_id": "assign-5b-local", "result": "synthetic"},
            },
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.offline.done",
                "payload": {"agent_id": "jarvis"},
            },
        ]
    )

    result = run_start_once(config=_bounded_config(tmp_path), broker=broker)

    assert result.accepted is True
    assert result.daemon_started is True
    assert result.service_state == "offline"
    assert broker.connected_url == "nats://127.0.0.1:7422"
    assert "nexus.4_19.wbs7_19_14.run-5b-local.*.heartbeat.>" in broker.subscriptions
    subjects = [subject for subject, _ in broker.published]
    assert "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.controller.init" in subjects
    assert "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.assignment" in subjects
    assert "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.drain" in subjects
    assert broker.drained is True
    assert broker.closed is True
    record_types = [record.record_type for record in result.evidence_records]
    assert "ack_candidate_observed" in record_types
    assert "result_candidate_observed" in record_types
    assert result.status_snapshot["final_acceptance"] is False
    assert result.evidence_package.review_ready is True


def test_start_once_bounded_loop_fails_closed_without_bounded_uat_launch_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_URL", "nats://127.0.0.1:7422")
    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_AUTH_REF", "local-uat-auth-ref")
    config = _bounded_config(tmp_path)
    config["controller"]["launch_mode"] = "disabled"

    result = run_start_once(config=config, broker=FakeResidentBroker())

    assert result.accepted is False
    assert result.daemon_started is False
    assert "BOUNDED_UAT_LAUNCH_MODE_REQUIRED" in result.errors


def test_start_once_bounded_loop_rejects_default_production_port(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_URL", "nats://127.0.0.1:4222")
    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_AUTH_REF", "local-uat-auth-ref")

    result = run_start_once(config=_bounded_config(tmp_path), broker=FakeResidentBroker())

    assert result.accepted is False
    assert result.daemon_started is False
    assert "PRODUCTION_OR_DEFAULT_NATS_PORT_NOT_AUTHORIZED_FOR_5B" in result.errors


def test_start_once_bounded_loop_requires_assignment_candidate_evidence_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_URL", "nats://127.0.0.1:7422")
    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_AUTH_REF", "local-uat-auth-ref")
    broker = FakeResidentBroker(
        inbound_events=[
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.readiness.ready",
                "payload": {"agent_id": "jarvis"},
            },
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.heartbeat.tick",
                "payload": {"agent_id": "jarvis"},
            },
        ]
    )

    result = run_start_once(config=_bounded_config(tmp_path), broker=broker)

    assert result.accepted is False
    assert result.daemon_started is False
    assert "ACK_CANDIDATE_NOT_OBSERVED" in result.errors
    assert "RESULT_CANDIDATE_NOT_OBSERVED" in result.errors


def test_start_once_bounded_loop_requires_offline_observation_after_drain(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_URL", "nats://127.0.0.1:7422")
    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_AUTH_REF", "local-uat-auth-ref")
    broker = FakeResidentBroker(
        inbound_events=[
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.readiness.ready",
                "payload": {"agent_id": "jarvis"},
            },
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.heartbeat.tick",
                "payload": {"agent_id": "jarvis"},
            },
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.ack.assignment",
                "payload": {"assignment_id": "assign-5b-local"},
            },
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.progress.assignment",
                "payload": {"assignment_id": "assign-5b-local"},
            },
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.evidence.assignment",
                "payload": {"assignment_id": "assign-5b-local"},
            },
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.result_candidate.done",
                "payload": {"assignment_id": "assign-5b-local"},
            },
        ]
    )

    result = run_start_once(config=_bounded_config(tmp_path), broker=broker)

    assert result.accepted is False
    assert result.daemon_started is False
    assert "OFFLINE_NOT_OBSERVED_AFTER_DRAIN" in result.errors


def test_cli_start_once_config_only_uses_bounded_runner(tmp_path, monkeypatch):
    config = _bounded_config(tmp_path)
    config_path = tmp_path / "resident.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    output_path = tmp_path / "start_once.json"

    def fake_run_start_once(*, config):
        return run_start_once(
            config=config,
            broker=FakeResidentBroker(
                inbound_events=[
                    {
                        "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.readiness.ready",
                        "payload": {"agent_id": "jarvis"},
                    },
                    {
                        "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.heartbeat.tick",
                        "payload": {"agent_id": "jarvis"},
                    },
                    {
                        "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.ack.assignment",
                        "payload": {"assignment_id": "assign-5b-local"},
                    },
                    {
                        "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.progress.assignment",
                        "payload": {"assignment_id": "assign-5b-local"},
                    },
                    {
                        "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.evidence.assignment",
                        "payload": {"assignment_id": "assign-5b-local"},
                    },
                    {
                        "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.result_candidate.done",
                        "payload": {"assignment_id": "assign-5b-local"},
                    },
                    {
                        "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.offline.done",
                        "payload": {"agent_id": "jarvis"},
                    },
                ]
            ),
        )

    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_URL", "nats://127.0.0.1:7422")
    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_AUTH_REF", "local-uat-auth-ref")
    monkeypatch.setattr("nexus.mq.resident_controller.cli.run_start_once", fake_run_start_once)

    exit_code = main(["start-once", "--config", str(config_path), "--output", str(output_path)])

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["daemon_started"] is True
    assert payload["service_state"] == "offline"


def _subject_matches(pattern, subject):
    pattern_parts = pattern.split(".")
    subject_parts = subject.split(".")
    for index, pattern_part in enumerate(pattern_parts):
        if pattern_part == ">":
            return True
        if index >= len(subject_parts):
            return False
        if pattern_part == "*":
            continue
        if pattern_part != subject_parts[index]:
            return False
    return len(pattern_parts) == len(subject_parts)
