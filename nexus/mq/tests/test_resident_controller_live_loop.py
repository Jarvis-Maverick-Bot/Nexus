import json
import threading
import time

from nexus.mq.eligibility_reservation_policy import RuntimeEligibilityDecision, RuntimeReservationLease
from nexus.mq.resident_controller.cli import main
from nexus.mq.resident_controller.live_loop import (
    MissingResidentLifecycleProvider,
    _post_assignment_observation_timeout_seconds,
    run_start_once,
)
from nexus.mq.tests.test_resident_controller_config import _config


class FakeResidentBroker:
    def __init__(self, inbound_events=None, *, auto_duplicate_suppression=True):
        self.inbound_events = list(inbound_events or [])
        self.auto_duplicate_suppression = auto_duplicate_suppression
        self.connected_url = ""
        self.subscriptions = []
        self.registered_handlers = []
        self.published = []
        self.actions = []
        self.drained = False
        self.closed = False

    def connect(self, *, nats_url, auth_ref, connect_timeout_seconds):
        self.actions.append(("connect", nats_url))
        self.connected_url = nats_url

    def subscribe(self, subject, handler):
        self.actions.append(("subscribe", subject))
        self.subscriptions.append(subject)
        self.registered_handlers.append((subject, handler))
        for event in self.inbound_events:
            if _subject_matches(subject, event["subject"]):
                handler(event["subject"], event["payload"])

    def publish(self, subject, payload):
        self.actions.append(("publish", subject))
        self.published.append((subject, payload))
        if self.auto_duplicate_suppression and subject.endswith(".assignment.duplicate_replay"):
            suppression_payload = {
                "assignment_id": payload.get("assignment_id", ""),
                "duplicate_replay_suppressed": True,
                "error_code": "DUPLICATE_ASSIGNMENT_SUPPRESSED",
            }
            suppression_subjects = [
                subject.rsplit(".assignment.duplicate_replay", 1)[0] + ".evidence.duplicate_replay",
                subject.rsplit(".assignment.duplicate_replay", 1)[0] + ".evidence",
            ]
            for pattern, handler in list(self.registered_handlers):
                for suppression_subject in suppression_subjects:
                    if _subject_matches(pattern, suppression_subject):
                        handler(suppression_subject, suppression_payload)

    def drain(self):
        self.drained = True

    def close(self):
        self.closed = True


class DelayedResultResidentBroker(FakeResidentBroker):
    def __init__(self, inbound_events=None, *, delayed_result_subject="", delayed_result_payload=None, delay_seconds=0.05):
        super().__init__(inbound_events)
        self.handlers = []
        self.delayed_result_subject = delayed_result_subject
        self.delayed_result_payload = dict(delayed_result_payload or {})
        self.delay_seconds = delay_seconds
        self._threads = []

    def subscribe(self, subject, handler):
        self.handlers.append((subject, handler))
        super().subscribe(subject, handler)

    def publish(self, subject, payload):
        super().publish(subject, payload)
        if subject.endswith(".assignment") and self.delayed_result_subject:
            thread = threading.Thread(target=self._deliver_result_after_delay, daemon=True)
            thread.start()
            self._threads.append(thread)

    def close(self):
        for thread in self._threads:
            thread.join(timeout=1)
        super().close()

    def _deliver_result_after_delay(self):
        time.sleep(self.delay_seconds)
        for pattern, handler in list(self.handlers):
            if _subject_matches(pattern, self.delayed_result_subject):
                handler(self.delayed_result_subject, self.delayed_result_payload)


class DuplicateSuppressionResidentBroker(FakeResidentBroker):
    def __init__(
        self,
        inbound_events=None,
        *,
        suppression_subject="",
        suppression_payload=None,
        delay_seconds=0.01,
    ):
        super().__init__(inbound_events, auto_duplicate_suppression=False)
        self.handlers = []
        self.suppression_subject = suppression_subject
        self.suppression_payload = dict(suppression_payload or {})
        self.delay_seconds = delay_seconds
        self._threads = []

    def subscribe(self, subject, handler):
        self.handlers.append((subject, handler))
        super().subscribe(subject, handler)

    def publish(self, subject, payload):
        super().publish(subject, payload)
        if subject.endswith(".assignment.duplicate_replay") and self.suppression_subject:
            thread = threading.Thread(target=self._deliver_suppression_after_delay, daemon=True)
            thread.start()
            self._threads.append(thread)

    def close(self):
        for thread in self._threads:
            thread.join(timeout=1)
        super().close()

    def _deliver_suppression_after_delay(self):
        time.sleep(self.delay_seconds)
        for pattern, handler in list(self.handlers):
            if _subject_matches(pattern, self.suppression_subject):
                handler(self.suppression_subject, self.suppression_payload)


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
        "nexus.4_19.wbs7_19_15.*.jarvis.registration",
        "nexus.4_19.wbs7_19_15.*.jarvis.readiness",
        "nexus.4_19.wbs7_19_15.*.jarvis.heartbeat",
        "nexus.4_19.wbs7_19_15.*.jarvis.ack",
        "nexus.4_19.wbs7_19_15.*.jarvis.progress",
        "nexus.4_19.wbs7_19_15.*.jarvis.evidence",
        "nexus.4_19.wbs7_19_15.*.jarvis.result_candidate",
        "nexus.4_19.wbs7_19_15.*.jarvis.offline",
    ]
    config["subjects"]["publish_allowlist"] = [
        "nexus.4_19.wbs7_19_15.*.jarvis.controller.init",
        "nexus.4_19.wbs7_19_15.*.jarvis.assignment",
        "nexus.4_19.wbs7_19_15.*.jarvis.assignment.duplicate_replay",
        "nexus.4_19.wbs7_19_15.*.jarvis.drain",
    ]
    config["evidence"]["root"] = str(tmp_path / "evidence" / "RUN_ID")
    config["uat"]["assignment_id"] = "assign-wbs-7-19-15-2-001"
    config["uat"]["idempotency_key"] = "idem-wbs-7-19-15-2-001"
    config["uat"]["target_runtime_instance_id"] = "jarvis-wbs-7-19-15-2-resident-controller-rerun-20260605T091050Z"
    config["uat"]["assignment_kind"] = "synthetic_business_command_acceptance"
    broker = FakeResidentBroker(
        inbound_events=[
            {
                "subject": f"nexus.4_19.wbs7_19_15.{run_id}.jarvis.registration",
                "payload": {"agent_id": "jarvis"},
            },
            {
                "subject": f"nexus.4_19.wbs7_19_15.{run_id}.jarvis.readiness",
                "payload": {"agent_id": "jarvis"},
            },
            {
                "subject": f"nexus.4_19.wbs7_19_15.{run_id}.jarvis.heartbeat",
                "payload": {"agent_id": "jarvis"},
            },
            {
                "subject": f"nexus.4_19.wbs7_19_15.{run_id}.jarvis.ack",
                "payload": {"assignment_id": "assign-wbs-7-19-15-2-001"},
            },
            {
                "subject": f"nexus.4_19.wbs7_19_15.{run_id}.jarvis.progress",
                "payload": {"assignment_id": "assign-wbs-7-19-15-2-001"},
            },
            {
                "subject": f"nexus.4_19.wbs7_19_15.{run_id}.jarvis.evidence",
                "payload": {"assignment_id": "assign-wbs-7-19-15-2-001"},
            },
            {
                "subject": f"nexus.4_19.wbs7_19_15.{run_id}.jarvis.result_candidate",
                "payload": {"assignment_id": "assign-wbs-7-19-15-2-001"},
            },
            {
                "subject": f"nexus.4_19.wbs7_19_15.{run_id}.jarvis.offline",
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
    assert assignment_payload["assignment_kind"] == "synthetic_business_command_acceptance"
    assert assignment_payload["no_go_scope_ref"] == "no-go://wbs-7.19.15.2"
    assert result.evidence_package.manifest_path.parent == tmp_path / "evidence" / run_id
    assignment_record = next(
        record
        for record in result.evidence_records
        if record.record_type == "bounded_assignment_published"
    )
    assert assignment_record.payload["runtime_authority_scopes"] == ["wbs://7.19.15.2"]


def test_start_once_publishes_assignment_promptly_after_readiness_and_heartbeat(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_URL", "nats://127.0.0.1:7422")
    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_AUTH_REF", "local-uat-auth-ref")
    config = _bounded_config(tmp_path)
    config["uat"]["max_runtime_seconds"] = 1800
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
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.offline.done",
                "payload": {"agent_id": "jarvis"},
            },
        ]
    )

    def record_wait(seconds):
        broker.actions.append(("wait", seconds))

    monkeypatch.setattr("nexus.mq.resident_controller.live_loop._wait_for_runtime_window", record_wait)

    result = run_start_once(config=config, broker=broker)

    assert result.accepted is True
    assignment_index = broker.actions.index(("publish", "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.assignment"))
    max_runtime_wait_indexes = [
        index for index, action in enumerate(broker.actions) if action == ("wait", 1800.0)
    ]
    assert not max_runtime_wait_indexes or assignment_index < max_runtime_wait_indexes[0]


def test_start_once_default_bounded_lifecycle_provider_dispatches_valid_assignment(tmp_path, monkeypatch):
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
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.offline.done",
                "payload": {"agent_id": "jarvis"},
            },
        ]
    )

    result = run_start_once(config=_bounded_config(tmp_path), broker=broker)

    assert result.accepted is True
    assignment_payload = next(payload for subject, payload in broker.published if subject.endswith(".assignment"))
    assert assignment_payload["lifecycle_decision_id"].startswith("decision-run-5b-local-assign-5b-local-")
    assert assignment_payload["reservation_lease_id"].startswith("lease-run-5b-local-assign-5b-local-")


def test_start_once_missing_lifecycle_provider_fails_closed_without_assignment(tmp_path, monkeypatch):
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
        lifecycle_provider=MissingResidentLifecycleProvider(),
    )

    assert result.accepted is False
    assert "MISSING_LIFECYCLE_DECISION_ID" in result.errors
    assert "MISSING_RESERVATION_LEASE_ID" in result.errors
    assert all(not subject.endswith(".assignment") for subject, _ in broker.published)


def test_start_once_records_observed_event_timestamps(tmp_path, monkeypatch):
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
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.offline.done",
                "payload": {"agent_id": "jarvis"},
            },
        ]
    )

    result = run_start_once(config=_bounded_config(tmp_path), broker=broker)

    timestamps = result.status_snapshot["event_timestamps"]
    assert timestamps["readiness_at"]
    assert timestamps["heartbeat_at"]
    assert timestamps["assignment_published_at"]
    assert timestamps["ack_at"]
    assert timestamps["result_candidate_at"]
    assert timestamps["drain_at"]
    assert result.status_snapshot["last_heartbeat_at"] == timestamps["heartbeat_at"]


def test_start_once_waits_beyond_short_post_assignment_window_for_result_candidate(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_URL", "nats://127.0.0.1:7422")
    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_AUTH_REF", "local-uat-auth-ref")
    config = _bounded_config(tmp_path)
    config["uat"]["post_assignment_seconds"] = 0.01
    result_subject = "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.result_candidate.done"
    broker = DelayedResultResidentBroker(
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
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.offline.done",
                "payload": {"agent_id": "jarvis"},
            },
        ],
        delayed_result_subject=result_subject,
        delayed_result_payload={"assignment_id": "assign-5b-local", "result": "synthetic"},
        delay_seconds=0.05,
    )

    result = run_start_once(config=config, broker=broker)

    assert result.accepted is True
    assert "RESULT_CANDIDATE_NOT_OBSERVED" not in result.errors
    assert result.status_snapshot["event_timestamps"]["result_candidate_at"]


def test_post_assignment_observation_window_uses_recovery_timeout_minimum_for_7_19_15_2():
    timeout = _post_assignment_observation_timeout_seconds(
        {"post_assignment_seconds": 1},
        {"result_candidate_timeout_seconds": 120},
    )

    assert timeout >= 120


def test_start_once_publishes_duplicate_replay_after_result_candidate_before_drain(tmp_path, monkeypatch):
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
    subjects = [subject for subject, _ in broker.published]
    assignment_index = subjects.index("nexus.4_19.wbs7_19_14.run-5b-local.jarvis.assignment")
    duplicate_index = subjects.index("nexus.4_19.wbs7_19_14.run-5b-local.jarvis.assignment.duplicate_replay")
    drain_index = subjects.index("nexus.4_19.wbs7_19_14.run-5b-local.jarvis.drain")
    assert assignment_index < duplicate_index < drain_index
    duplicate_payload = broker.published[duplicate_index][1]
    assert duplicate_payload["assignment_id"] == "assign-5b-local"
    assert duplicate_payload["idempotency_key"] == "idem-5b-local"
    assert duplicate_payload["duplicate_replay"] is True
    assert result.status_snapshot["event_timestamps"]["duplicate_replay_at"]


def test_start_once_blocks_drain_when_duplicate_suppression_evidence_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_URL", "nats://127.0.0.1:7422")
    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_AUTH_REF", "local-uat-auth-ref")
    config = _bounded_config(tmp_path)
    config["uat"]["duplicate_replay_suppression_timeout_seconds"] = 0.01
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
                "payload": {"assignment_id": "assign-5b-local", "result": "synthetic"},
            },
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.offline.done",
                "payload": {"agent_id": "jarvis"},
            },
        ],
        auto_duplicate_suppression=False,
    )

    result = run_start_once(config=config, broker=broker)

    assert result.accepted is False
    assert "DUPLICATE_REPLAY_SUPPRESSION_NOT_OBSERVED: jarvis" in result.errors
    subjects = [subject for subject, _ in broker.published]
    assert "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.assignment.duplicate_replay" in subjects
    assert "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.drain" not in subjects


def test_start_once_waits_for_duplicate_suppression_evidence_before_drain(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_URL", "nats://127.0.0.1:7422")
    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_AUTH_REF", "local-uat-auth-ref")
    broker = DuplicateSuppressionResidentBroker(
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
                "payload": {"assignment_id": "assign-5b-local", "result": "synthetic"},
            },
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.offline.done",
                "payload": {"agent_id": "jarvis"},
            },
        ],
        suppression_subject="nexus.4_19.wbs7_19_14.run-5b-local.jarvis.evidence.duplicate_replay",
        suppression_payload={
            "assignment_id": "assign-5b-local",
            "duplicate_replay_suppressed": True,
            "error_code": "DUPLICATE_ASSIGNMENT_SUPPRESSED",
        },
    )

    result = run_start_once(config=_bounded_config(tmp_path), broker=broker)

    assert result.accepted is True
    subjects = [subject for subject, _ in broker.published]
    duplicate_index = subjects.index("nexus.4_19.wbs7_19_14.run-5b-local.jarvis.assignment.duplicate_replay")
    drain_index = subjects.index("nexus.4_19.wbs7_19_14.run-5b-local.jarvis.drain")
    assert duplicate_index < drain_index
    assert result.status_snapshot["event_timestamps"]["duplicate_suppression_at"]


def test_start_once_publishes_assignment_once_after_duplicate_readiness_and_heartbeat(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_URL", "nats://127.0.0.1:7422")
    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_AUTH_REF", "local-uat-auth-ref")
    monkeypatch.setattr("nexus.mq.resident_controller.live_loop._wait_for_candidate_observations", lambda **kwargs: None)
    broker = FakeResidentBroker(
        inbound_events=[
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.readiness.ready",
                "payload": {"agent_id": "jarvis"},
            },
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.readiness.again",
                "payload": {"agent_id": "jarvis"},
            },
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.heartbeat.tick",
                "payload": {"agent_id": "jarvis"},
            },
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.heartbeat.again",
                "payload": {"agent_id": "jarvis"},
            },
        ]
    )

    result = run_start_once(config=_bounded_config(tmp_path), broker=broker)

    assignment_subjects = [subject for subject, _ in broker.published if subject.endswith(".assignment")]
    assert assignment_subjects == ["nexus.4_19.wbs7_19_14.run-5b-local.jarvis.assignment"]
    assert "ACK_CANDIDATE_NOT_OBSERVED" in result.errors


def test_start_once_does_not_publish_assignment_before_readiness_and_heartbeat(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_URL", "nats://127.0.0.1:7422")
    monkeypatch.setenv("NEXUS_RESIDENT_CONTROLLER_NATS_AUTH_REF", "local-uat-auth-ref")
    broker = FakeResidentBroker(
        inbound_events=[
            {
                "subject": "nexus.4_19.wbs7_19_14.run-5b-local.jarvis.readiness.ready",
                "payload": {"agent_id": "jarvis"},
            },
        ]
    )

    result = run_start_once(config=_bounded_config(tmp_path), broker=broker)

    assert all(not subject.endswith(".assignment") for subject, _ in broker.published)
    assert "ASSIGNMENT_READINESS_HEARTBEAT_NOT_OBSERVED: jarvis" in result.errors


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
    monkeypatch.setattr("nexus.mq.resident_controller.live_loop._wait_for_candidate_observations", lambda **kwargs: None)
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
