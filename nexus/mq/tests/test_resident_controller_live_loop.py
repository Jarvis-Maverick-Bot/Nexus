import json

from nexus.mq.eligibility_reservation_policy import RuntimeEligibilityDecision, RuntimeReservationLease
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


class FakeResidentLifecycleProvider:
    def assignment_decision_and_lease(
        self,
        *,
        run_id,
        agent_id,
        assignment_id,
        idempotency_key,
        target_runtime_instance_id,
        now_at,
    ):
        decision = RuntimeEligibilityDecision(
            decision_id="decision-5b-local",
            request_id=f"eligibility-{run_id}",
            dispatch_run_id=run_id,
            assignment_id=assignment_id,
            target_agent_id=agent_id,
            target_runtime_instance_id=target_runtime_instance_id,
            accepted=True,
            policy_hash="policy-hash-5b-local",
            idempotency_key=idempotency_key,
            evidence_refs=["evidence://runtime-lifecycle/decision/5b-local"],
        )
        lease = RuntimeReservationLease(
            lease_id="lease-5b-local",
            lifecycle_decision_id=decision.decision_id,
            assignment_id=assignment_id,
            dispatch_run_id=run_id,
            target_runtime_instance_id=target_runtime_instance_id,
            active=True,
            status="active",
            expires_at="2099-01-01T00:00:00+00:00",
            policy_hash=decision.policy_hash,
            idempotency_key=idempotency_key,
        )
        return decision, lease


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

    result = run_start_once(
        config=_bounded_config(tmp_path),
        broker=broker,
        lifecycle_provider=FakeResidentLifecycleProvider(),
    )

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


def test_start_once_bounded_loop_uses_configured_wbs_7_19_15_2_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_URL", "nats://192.168.31.124:7422")
    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_AUTH_REF", "local-uat-auth-ref")
    run_id = "wbs-7-19-15-2-jarvis-resident-controller-run-window-20260605T091050Z"
    config = _bounded_config(tmp_path)
    config["controller"]["run_id"] = run_id
    config["controller"]["runtime_instance_id"] = run_id
    config["controller"]["allowed_wbs_ids"] = ["7.19.15.2"]
    config["subjects"]["namespace"] = "nexus.4_19.wbs7_19_15"
    config["subjects"]["subscribe_allowlist"] = [
        "nexus.4_19.wbs7_19_15.*.registration.>",
        "nexus.4_19.wbs7_19_15.*.readiness.>",
        "nexus.4_19.wbs7_19_15.*.heartbeat.>",
        "nexus.4_19.wbs7_19_15.*.ack.>",
        "nexus.4_19.wbs7_19_15.*.progress.>",
        "nexus.4_19.wbs7_19_15.*.evidence.>",
        "nexus.4_19.wbs7_19_15.*.result_candidate.>",
        "nexus.4_19.wbs7_19_15.*.offline.>",
    ]
    config["subjects"]["publish_allowlist"] = [
        "nexus.4_19.wbs7_19_15.*.controller.init",
        "nexus.4_19.wbs7_19_15.*.assignment",
        "nexus.4_19.wbs7_19_15.*.assignment.duplicate_replay",
        "nexus.4_19.wbs7_19_15.*.drain",
    ]
    config["evidence"]["root"] = str(tmp_path / "evidence" / "RUN_ID")
    config["uat"]["assignment_id"] = "assign-wbs-7-19-15-2-001"
    config["uat"]["idempotency_key"] = "idem-wbs-7-19-15-2-001"
    broker = FakeResidentBroker(
        inbound_events=[
            {
                "subject": f"nexus.4_19.wbs7_19_15.{run_id}.jarvis.registration.ready",
                "payload": {"agent_id": "jarvis"},
            },
            {
                "subject": f"nexus.4_19.wbs7_19_15.{run_id}.jarvis.readiness.ready",
                "payload": {"agent_id": "jarvis"},
            },
            {
                "subject": f"nexus.4_19.wbs7_19_15.{run_id}.jarvis.heartbeat.tick",
                "payload": {"agent_id": "jarvis"},
            },
            {
                "subject": f"nexus.4_19.wbs7_19_15.{run_id}.jarvis.ack.assignment",
                "payload": {"assignment_id": "assign-wbs-7-19-15-2-001"},
            },
            {
                "subject": f"nexus.4_19.wbs7_19_15.{run_id}.jarvis.progress.assignment",
                "payload": {"assignment_id": "assign-wbs-7-19-15-2-001"},
            },
            {
                "subject": f"nexus.4_19.wbs7_19_15.{run_id}.jarvis.evidence.assignment",
                "payload": {"assignment_id": "assign-wbs-7-19-15-2-001"},
            },
            {
                "subject": f"nexus.4_19.wbs7_19_15.{run_id}.jarvis.result_candidate.done",
                "payload": {"assignment_id": "assign-wbs-7-19-15-2-001"},
            },
            {
                "subject": f"nexus.4_19.wbs7_19_15.{run_id}.jarvis.offline.done",
                "payload": {"agent_id": "jarvis"},
            },
        ]
    )

    result = run_start_once(
        config=config,
        broker=broker,
        lifecycle_provider=FakeResidentLifecycleProvider(),
    )

    assert result.accepted is True
    assignment_payload = next(payload for subject, payload in broker.published if subject.endswith(".assignment"))
    assert assignment_payload["wbs_id"] == "7.19.15.2"
    assert assignment_payload["no_go_scope_ref"] == "no-go://wbs-7.19.15.2"
    assert result.evidence_package.manifest_path.parent == tmp_path / "evidence" / run_id
    assignment_record = next(
        record
        for record in result.evidence_records
        if record.record_type == "bounded_assignment_published"
    )
    assert assignment_record.payload["runtime_authority_scopes"] == ["wbs://7.19.15.2"]


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

    result = run_start_once(
        config=_bounded_config(tmp_path),
        broker=broker,
        lifecycle_provider=FakeResidentLifecycleProvider(),
    )

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

    result = run_start_once(
        config=_bounded_config(tmp_path),
        broker=broker,
        lifecycle_provider=FakeResidentLifecycleProvider(),
    )

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
            lifecycle_provider=FakeResidentLifecycleProvider(),
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
