"""Candidate Adapter API facade with deterministic provider injection."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nexus.mq.candidate_adapter_assignment_validator import (
    CandidateAssignmentEvent,
    CandidateReservationLease,
    assignment_intake_prerequisite_errors,
    validate_candidate_assignment,
)
from nexus.mq.candidate_adapter_event_mapper import (
    build_candidate_action_event,
    candidate_safe_assignment_view,
    map_assignment_to_candidate_event,
)
from nexus.mq.candidate_adapter_profile_loader import load_candidate_adapter_profile
from nexus.mq.candidate_adapter_session_store import (
    CandidateAdapterSession,
    CandidateAdapterSessionStore,
    build_session_from_profile,
)
from nexus.mq.candidate_adapter_subject_broker_policy import validate_assignment_subject


@dataclass
class CandidateAdapterOperationResult:
    accepted: bool
    operation: str
    errors: list[str] = field(default_factory=list)
    session: CandidateAdapterSession | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        data = {
            "accepted": self.accepted,
            "operation": self.operation,
            "errors": list(self.errors),
            "payload": self.payload,
            "not_business_completion": self.not_business_completion,
        }
        if self.session is not None:
            data["session"] = {
                "session_id": self.session.session_id,
                "agent_id": self.session.agent_id,
                "runtime_instance_id": self.session.runtime_instance_id,
                "lifecycle_state": self.session.lifecycle_state,
                "broker_profile_ref": self.session.broker_profile_ref,
            }
        return data


@dataclass
class CandidateAdapterProviders:
    broker: "InMemoryAssignmentBroker"
    lifecycle: "InMemoryLifecycleProvider"


class InMemoryAssignmentBroker:
    def __init__(self, assignments: list[CandidateAssignmentEvent] | None = None):
        self.assignments = list(assignments or [])
        self.await_calls = 0
        self.published_events: list[dict[str, Any]] = []

    def await_assignment(self, session: CandidateAdapterSession, *, timeout_s: float | None = None) -> CandidateAssignmentEvent | None:
        self.await_calls += 1
        if not self.assignments:
            return None
        return self.assignments.pop(0)

    def publish_event(self, event: dict[str, Any]) -> None:
        self.published_events.append(dict(event))


class InMemoryLifecycleProvider:
    def __init__(self, leases: dict[str, CandidateReservationLease] | None = None):
        self.leases = dict(leases or {})
        self.lookups: list[str] = []

    def get_lease(self, lease_id: str) -> CandidateReservationLease | None:
        self.lookups.append(lease_id)
        if not lease_id:
            return None
        return self.leases.get(lease_id)


class CandidateAdapterApi:
    def __init__(self, *, session_store: CandidateAdapterSessionStore, providers: CandidateAdapterProviders):
        self.session_store = session_store
        self.providers = providers

    def connect(
        self,
        profile_path: str | Path,
        *,
        session_path: str | Path,
        local_only_authorization: bool = False,
    ) -> CandidateAdapterOperationResult:
        self.session_store.bind(session_path)
        loaded = load_candidate_adapter_profile(profile_path, local_only_authorization=local_only_authorization)
        if not loaded.accepted or loaded.profile is None:
            return CandidateAdapterOperationResult(False, "connect", errors=loaded.errors)
        session = build_session_from_profile(loaded.profile)
        self.session_store.save(session)
        event = build_candidate_action_event("connect", session=session, evidence_refs=[loaded.profile.evidence_output_ref])
        return CandidateAdapterOperationResult(
            True,
            "connect",
            session=session,
            payload={"profile_digest": loaded.profile_digest, "event": event.to_dict()},
        )

    def register(self, session_path: str | Path) -> CandidateAdapterOperationResult:
        session = self._load(session_path)
        if session.lifecycle_state not in {"connected", "registered", "ready", "idle"}:
            return CandidateAdapterOperationResult(False, "register", errors=[f"SESSION_STATE_BLOCKS_REGISTER: {session.lifecycle_state}"])
        session.lifecycle_state = "registered"
        session.registration_ref = f"registry://candidate/{session.agent_id}/{session.runtime_instance_id}"
        self.session_store.save(session)
        event = build_candidate_action_event("register", session=session, evidence_refs=[session.registration_ref])
        return CandidateAdapterOperationResult(True, "register", session=session, payload={"event": event.to_dict()})

    def submit_readiness(
        self,
        session_path: str | Path,
        *,
        startup_packet_ref: str,
        self_check_evidence_ref: str,
    ) -> CandidateAdapterOperationResult:
        session = self._load(session_path)
        errors: list[str] = []
        if not startup_packet_ref:
            errors.append("MISSING_STARTUP_PACKET_REF")
        if not self_check_evidence_ref:
            errors.append("MISSING_SELF_CHECK_EVIDENCE_REF")
        if errors:
            return CandidateAdapterOperationResult(False, "ready", errors=errors, session=session)
        session.startup_packet_ref = startup_packet_ref
        session.readiness_evidence_ref = self_check_evidence_ref
        session.lifecycle_state = "ready"
        self.session_store.save(session)
        event = build_candidate_action_event("readiness", session=session, evidence_refs=[startup_packet_ref, self_check_evidence_ref])
        return CandidateAdapterOperationResult(True, "ready", session=session, payload={"event": event.to_dict()})

    def heartbeat(
        self,
        session_path: str | Path,
        *,
        sequence: int,
        observed_state: dict[str, Any] | None = None,
    ) -> CandidateAdapterOperationResult:
        session = self._load(session_path)
        errors: list[str] = []
        observed_runtime_id = (observed_state or {}).get("runtime_instance_id")
        if observed_runtime_id and observed_runtime_id != session.runtime_instance_id:
            errors.append("HEARTBEAT_RUNTIME_IDENTITY_MISMATCH")
        if sequence <= session.last_heartbeat_sequence:
            errors.append("HEARTBEAT_SEQUENCE_REGRESSION")
        if errors:
            return CandidateAdapterOperationResult(False, "heartbeat", errors=errors, session=session)
        session.last_heartbeat_sequence = sequence
        if session.lifecycle_state == "ready":
            session.lifecycle_state = "idle"
        self.session_store.save(session)
        event = build_candidate_action_event("heartbeat", session=session, payload={"sequence": sequence})
        return CandidateAdapterOperationResult(True, "heartbeat", session=session, payload={"event": event.to_dict()})

    def await_assignment(self, session_path: str | Path, *, timeout_s: float | None = None) -> CandidateAdapterOperationResult:
        session = self._load(session_path)
        prerequisite_errors = assignment_intake_prerequisite_errors(session, operation="INTAKE")
        if prerequisite_errors:
            return CandidateAdapterOperationResult(
                False,
                "await_assignment",
                errors=prerequisite_errors,
                session=session,
            )
        assignment = self.providers.broker.await_assignment(session, timeout_s=timeout_s)
        if assignment is None:
            return CandidateAdapterOperationResult(True, "await_assignment", session=session, payload={"assignment": None})
        subject_decision = validate_assignment_subject(assignment.assignment_subject, session.allowed_subject_patterns)
        if not subject_decision.accepted:
            return CandidateAdapterOperationResult(False, "await_assignment", errors=subject_decision.errors, session=session)
        event = map_assignment_to_candidate_event(assignment, session=session)
        return CandidateAdapterOperationResult(
            True,
            "await_assignment",
            session=session,
            payload={"assignment": candidate_safe_assignment_view(assignment), "event": event.to_dict()},
        )

    def ack_assignment(
        self,
        session_path: str | Path,
        assignment_ref: CandidateAssignmentEvent | dict[str, Any],
        *,
        now_at: str | None = None,
    ) -> CandidateAdapterOperationResult:
        session = self._load(session_path)
        assignment = _assignment_from_ref(assignment_ref)
        lease = self.providers.lifecycle.get_lease(assignment.reservation_lease_id)
        validation = validate_candidate_assignment(assignment, session=session, lease=lease, now_at=now_at)
        if not validation.accepted:
            return CandidateAdapterOperationResult(False, "ack", errors=validation.errors, session=session)
        if _has_matching_active_assignment(session, assignment):
            return CandidateAdapterOperationResult(
                True,
                "ack",
                errors=["DUPLICATE_ASSIGNMENT_SUPPRESSED"],
                session=session,
                payload={"assignment_id": assignment.assignment_id, "duplicate_suppressed": True},
            )
        _append_unique(session.active_assignment_refs, assignment.assignment_id)
        _append_unique(session.active_decision_ids, assignment.lifecycle_decision_id)
        _append_unique(session.active_reservation_lease_ids, assignment.reservation_lease_id)
        _append_unique(session.active_idempotency_keys, assignment.idempotency_key)
        session.lifecycle_state = "assigned"
        self.session_store.save(session)
        event = build_candidate_action_event(
            "assignment_ack",
            session=session,
            assignment_id=assignment.assignment_id,
            evidence_refs=[f"evidence://candidate-adapter/ack/{assignment.assignment_id}"],
        )
        self.providers.broker.publish_event(event.to_dict())
        return CandidateAdapterOperationResult(True, "ack", session=session, payload={"event": event.to_dict()})

    def report_progress(self, session_path: str | Path, *, assignment_id: str, progress_ref: str) -> CandidateAdapterOperationResult:
        session = self._load(session_path)
        errors = _active_assignment_errors(session, assignment_id)
        if not progress_ref:
            errors.append("MISSING_PROGRESS_REF")
        if errors:
            return CandidateAdapterOperationResult(False, "progress", errors=errors, session=session)
        event = build_candidate_action_event(
            "progress",
            session=session,
            assignment_id=assignment_id,
            payload={"progress_ref": progress_ref},
            evidence_refs=[progress_ref],
        )
        return CandidateAdapterOperationResult(True, "progress", session=session, payload={"event": event.to_dict()})

    def report_evidence(self, session_path: str | Path, *, assignment_id: str, evidence_ref: str) -> CandidateAdapterOperationResult:
        session = self._load(session_path)
        errors = _active_assignment_errors(session, assignment_id)
        if not evidence_ref:
            errors.append("MISSING_EVIDENCE_REF")
        if errors:
            return CandidateAdapterOperationResult(False, "evidence", errors=errors, session=session)
        event = build_candidate_action_event("evidence", session=session, assignment_id=assignment_id, evidence_refs=[evidence_ref])
        return CandidateAdapterOperationResult(True, "evidence", session=session, payload={"event": event.to_dict()})

    def report_result_candidate(
        self,
        session_path: str | Path,
        *,
        assignment_id: str,
        result_ref: str,
        evidence_ref: str,
    ) -> CandidateAdapterOperationResult:
        session = self._load(session_path)
        errors = _active_assignment_errors(session, assignment_id)
        if not result_ref:
            errors.append("MISSING_RESULT_REF")
        if not evidence_ref:
            errors.append("MISSING_RESULT_EVIDENCE_REF")
        if errors:
            return CandidateAdapterOperationResult(False, "result", errors=errors, session=session)
        event = build_candidate_action_event(
            "result_candidate",
            session=session,
            assignment_id=assignment_id,
            payload={"result_ref": result_ref},
            evidence_refs=[evidence_ref],
        )
        return CandidateAdapterOperationResult(True, "result", session=session, payload={"event": event.to_dict()})

    def drain(self, session_path: str | Path, *, reason_ref: str, evidence_ref: str) -> CandidateAdapterOperationResult:
        session = self._load(session_path)
        if not evidence_ref:
            return CandidateAdapterOperationResult(False, "drain", errors=["MISSING_DRAIN_EVIDENCE_REF"], session=session)
        session.lifecycle_state = "draining"
        self.session_store.save(session)
        event = build_candidate_action_event(
            "draining",
            session=session,
            payload={"reason_ref": reason_ref},
            evidence_refs=[evidence_ref],
        )
        return CandidateAdapterOperationResult(True, "drain", session=session, payload={"event": event.to_dict()})

    def offline(self, session_path: str | Path, *, final_evidence_ref: str, reason_ref: str = "source-only-shutdown") -> CandidateAdapterOperationResult:
        session = self._load(session_path)
        if not final_evidence_ref:
            return CandidateAdapterOperationResult(False, "offline", errors=["OFFLINE_REQUIRES_FINAL_EVIDENCE_REF"], session=session)
        session.lifecycle_state = "offline"
        self.session_store.save(session)
        event = build_candidate_action_event(
            "offline",
            session=session,
            payload={"reason_ref": reason_ref},
            evidence_refs=[final_evidence_ref],
        )
        return CandidateAdapterOperationResult(True, "offline", session=session, payload={"event": event.to_dict()})

    def _load(self, session_path: str | Path) -> CandidateAdapterSession:
        self.session_store.bind(session_path)
        return self.session_store.load()


def _assignment_from_ref(assignment_ref: CandidateAssignmentEvent | dict[str, Any]) -> CandidateAssignmentEvent:
    if isinstance(assignment_ref, CandidateAssignmentEvent):
        return assignment_ref
    return CandidateAssignmentEvent.from_dict(assignment_ref)


def _active_assignment_errors(session: CandidateAdapterSession, assignment_id: str) -> list[str]:
    if assignment_id not in session.active_assignment_refs:
        return [f"ASSIGNMENT_NOT_ACTIVE: {assignment_id}"]
    return []


def _has_matching_active_assignment(session: CandidateAdapterSession, assignment: CandidateAssignmentEvent) -> bool:
    try:
        index = session.active_assignment_refs.index(assignment.assignment_id)
    except ValueError:
        return False
    expected = {
        "idempotency_key": session.active_idempotency_keys,
        "lifecycle_decision_id": session.active_decision_ids,
        "reservation_lease_id": session.active_reservation_lease_ids,
    }
    observed = {
        "idempotency_key": assignment.idempotency_key,
        "lifecycle_decision_id": assignment.lifecycle_decision_id,
        "reservation_lease_id": assignment.reservation_lease_id,
    }
    for field_name, values in expected.items():
        if index >= len(values) or values[index] != observed[field_name]:
            return False
    return True


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)
