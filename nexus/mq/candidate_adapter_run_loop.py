"""Deterministic Candidate Adapter run-loop helper for tests and review."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nexus.mq.candidate_adapter_api import CandidateAdapterApi


@dataclass
class CandidateAdapterLoopResult:
    accepted: bool
    trace: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    not_business_completion: bool = True


def run_candidate_adapter_loop(
    api: CandidateAdapterApi,
    *,
    profile_path: str | Path,
    session_path: str | Path,
    startup_packet_ref: str,
    self_check_evidence_ref: str,
    heartbeat_sequence: int,
    now_at: str,
    max_assignments: int = 1,
    progress_ref: str = "progress://candidate-adapter/source-only",
    evidence_ref: str = "evidence://candidate-adapter/source-only",
    result_ref: str = "result://candidate-adapter/source-only",
    final_evidence_ref: str = "evidence://candidate-adapter/offline",
    offline_after_idle: bool = False,
) -> CandidateAdapterLoopResult:
    trace: list[str] = []
    payload: dict[str, Any] = {}

    for step_name, result in (
        ("connect", api.connect(profile_path, session_path=session_path)),
        ("register", api.register(session_path)),
        (
            "ready",
            api.submit_readiness(
                session_path,
                startup_packet_ref=startup_packet_ref,
                self_check_evidence_ref=self_check_evidence_ref,
            ),
        ),
        ("heartbeat", api.heartbeat(session_path, sequence=heartbeat_sequence)),
    ):
        if not result.accepted:
            return CandidateAdapterLoopResult(False, trace=trace, errors=result.errors, payload=payload)
        trace.append(step_name)

    for _ in range(max_assignments):
        awaited = api.await_assignment(session_path)
        if not awaited.accepted:
            return CandidateAdapterLoopResult(False, trace=trace, errors=awaited.errors, payload=payload)
        trace.append("await_assignment")
        assignment = awaited.payload.get("assignment")
        if assignment is None:
            break
        ack = api.ack_assignment(session_path, assignment, now_at=now_at)
        if not ack.accepted:
            return CandidateAdapterLoopResult(False, trace=trace, errors=ack.errors, payload=payload)
        trace.append("ack")
        if ack.payload.get("duplicate_suppressed"):
            trace.append("duplicate_replay_suppressed")
            continue
        assignment_id = assignment["assignment_id"]

        progress = api.report_progress(session_path, assignment_id=assignment_id, progress_ref=progress_ref)
        if not progress.accepted:
            return CandidateAdapterLoopResult(False, trace=trace, errors=progress.errors, payload=payload)
        trace.append("progress")

        evidence = api.report_evidence(session_path, assignment_id=assignment_id, evidence_ref=evidence_ref)
        if not evidence.accepted:
            return CandidateAdapterLoopResult(False, trace=trace, errors=evidence.errors, payload=payload)
        trace.append("evidence")

        result = api.report_result_candidate(
            session_path,
            assignment_id=assignment_id,
            result_ref=result_ref,
            evidence_ref=evidence_ref,
        )
        if not result.accepted:
            return CandidateAdapterLoopResult(False, trace=trace, errors=result.errors, payload=payload)
        trace.append("result_candidate")

    if max_assignments > 0:
        drained = api.drain(session_path, reason_ref="source-only-loop-complete", evidence_ref=evidence_ref)
        if not drained.accepted:
            return CandidateAdapterLoopResult(False, trace=trace, errors=drained.errors, payload=payload)
        trace.append("drain")

        offline = api.offline(session_path, final_evidence_ref=final_evidence_ref)
        if not offline.accepted:
            return CandidateAdapterLoopResult(False, trace=trace, errors=offline.errors, payload=payload)
        trace.append("offline")
        payload["offline_event"] = offline.payload["event"]
    elif offline_after_idle:
        offline = api.offline(session_path, final_evidence_ref=final_evidence_ref)
        if not offline.accepted:
            return CandidateAdapterLoopResult(False, trace=trace, errors=offline.errors, payload=payload)
        trace.append("offline")
        payload["offline_event"] = offline.payload["event"]

    return CandidateAdapterLoopResult(True, trace=trace, payload=payload)
