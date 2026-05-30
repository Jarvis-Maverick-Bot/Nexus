from nexus.mq.codex_runtime_adapter import build_codex_registry_record
from nexus.mq.codex_worker import (
    CodexWorkerDaemon,
    CodexWorkerPolicy,
    build_codex_execution_event,
    build_codex_result_candidate,
)
from nexus.mq.tests.test_codex_runtime_adapter import NOW, _registration


def _worker():
    record = build_codex_registry_record(registration=_registration(), now_at=NOW)
    return CodexWorkerDaemon(
        adapter_id="codex-adapter-001",
        record=record,
        policy=CodexWorkerPolicy(),
    )


def test_codex_worker_default_policy_refuses_start_and_live_nats():
    decision = _worker().evaluate_start()

    assert decision.accepted is False
    assert decision.errors == ["CODEX_WORKER_DISABLED"]
    assert decision.live_worker_started is False
    assert decision.nats_listener_started is False


def test_codex_worker_heartbeat_drain_and_offline_are_non_business_events():
    worker = _worker()
    heartbeat = worker.build_heartbeat_event(now_at=NOW)
    drain = worker.build_drain_event(now_at=NOW, reason_ref="drain://manual")
    offline = worker.build_offline_event(now_at=NOW, reason_ref="offline://manual")

    assert heartbeat.event_type == "heartbeat"
    assert heartbeat.payload["runtime_provider"] == "codex"
    assert drain.payload["accepting_new_work"] is False
    assert offline.payload["presence_state"] == "offline"
    assert heartbeat.not_business_completion is True
    assert drain.not_business_completion is True
    assert offline.not_business_completion is True


def test_codex_execution_event_requires_evidence_and_is_not_acceptance():
    event = build_codex_execution_event(
        event_id="event-codex-001",
        run_id="run-codex-001",
        assignment_id="assign-codex-001",
        task_id="task-codex-001",
        runtime_instance_id="codex-runtime-001",
        event_type="completed_execution",
        event_time=NOW,
        evidence_ref="evidence://codex/run/001",
    )

    assert event.event_type == "completed_execution"
    assert event.not_business_completion is True


def test_codex_result_candidate_requires_evidence_and_never_business_completion():
    candidate = build_codex_result_candidate(
        result_id="result-codex-001",
        run_id="run-codex-001",
        assignment_id="assign-codex-001",
        task_id="task-codex-001",
        runtime_instance_id="codex-runtime-001",
        status="blocked",
        changed_file_refs=[],
        evidence_refs=["evidence://codex/blocked/001"],
        emitted_at=NOW,
    )

    assert candidate.status == "blocked"
    assert candidate.not_business_completion is True
    assert candidate.no_go_violation_detected is False
