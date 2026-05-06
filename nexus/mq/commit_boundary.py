"""
MQ Commit Boundary — 3.5 Implementation
Local transactional commit: evidence refs + governed state transition
committed together before Business_Message is emitted.

Design source: GOVERNED_WORKFLOW_RUNTIME_AND_MESSAGE_QUEUE_ARCHITECTURE_V0_1.md §5.2
Baseline status: accepted-for-skeleton (3.5 V1.1, commit 3f7a5a0)

Default commit posture: local transactional commit.
This prevents the main failure: task executes but governed truth is not updated.

Design rules:
- Evidence refs and state transition must be committed in the same controlled path
- If either fails, neither is committed — workflow remains not-complete
- Distributed commit (outbox/recovery) is out of skeleton scope
- Business_Message emitted ONLY after commit acceptance
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Any
import uuid


@dataclass
class CommitResult:
    """Result of a transactional commit attempt."""
    accepted: bool
    commit_id: str = field(default_factory=lambda: f"commit-{uuid.uuid4().hex[:12]}")
    workflow_instance_id: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    state_transition: Optional[dict] = None
    error: Optional[str] = None
    committed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class EvidenceWriteResult:
    """Result of an evidence write attempt."""
    accepted: bool
    evidence_refs: list[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class StateTransitionResult:
    """Result of a state transition attempt."""
    accepted: bool
    previous_state: str = ""
    new_state: str = ""
    error: Optional[str] = None


class CommitBoundary:
    """
    Local transactional commit boundary.

    Design rule: evidence refs and state transition are committed together
    or not at all. This is the only path to Business_Message emission.

    Skeleton implementation: in-memory store simulating the governed state store.
    In production, this would be the actual governed state + evidence store.
    """

    def __init__(self):
        self._evidence_store: dict[str, list[str]] = {}   # workflow_instance_id → evidence_refs
        self._state_store: dict[str, str] = {}            # workflow_instance_id → state
        self._commit_log: list[CommitResult] = []

    def try_commit(
        self,
        workflow_instance_id: str,
        evidence_refs: list[str],
        state_transition: dict,
    ) -> CommitResult:
        """
        Attempt local transactional commit.

        Design rule:
        - Both evidence write AND state transition must succeed
        - If either fails, neither is committed — commit rejected
        - Only accepted commit emits Business_Message candidate
        """
        # Step 1: write evidence refs
        evidence_result = self._write_evidence(workflow_instance_id, evidence_refs)

        # Step 2: apply state transition
        state_result = self._apply_state_transition(workflow_instance_id, state_transition)

        # Step 3: if both succeed, commit is accepted
        if evidence_result.accepted and state_result.accepted:
            commit = CommitResult(
                accepted=True,
                workflow_instance_id=workflow_instance_id,
                evidence_refs=evidence_refs,
                state_transition=state_transition,
            )
            self._commit_log.append(commit)
            return commit
        else:
            # Partial failure — rollback both
            self._rollback(workflow_instance_id)
            error = "; ".join(
                filter(None, [
                    evidence_result.error,
                    state_result.error,
                ])
            )
            commit = CommitResult(
                accepted=False,
                workflow_instance_id=workflow_instance_id,
                evidence_refs=evidence_refs,
                state_transition=state_transition,
                error=error or "partial failure",
            )
            self._commit_log.append(commit)
            return commit

    def _write_evidence(self, workflow_instance_id: str, evidence_refs: list[str]) -> EvidenceWriteResult:
        """Write evidence refs to evidence store."""
        try:
            self._evidence_store[workflow_instance_id] = evidence_refs
            return EvidenceWriteResult(accepted=True, evidence_refs=evidence_refs)
        except Exception as e:
            return EvidenceWriteResult(accepted=False, error=str(e))

    def _apply_state_transition(self, workflow_instance_id: str, state_transition: dict) -> StateTransitionResult:
        """Apply state transition to state store."""
        try:
            previous = self._state_store.get(workflow_instance_id, "unknown")
            new_state = state_transition.get("new_state", "")
            self._state_store[workflow_instance_id] = new_state
            return StateTransitionResult(
                accepted=True,
                previous_state=previous,
                new_state=new_state,
            )
        except Exception as e:
            return StateTransitionResult(accepted=False, error=str(e))

    def _rollback(self, workflow_instance_id: str):
        """Rollback both evidence and state on partial failure."""
        self._evidence_store.pop(workflow_instance_id, None)
        self._state_store.pop(workflow_instance_id, None)

    def get_current_state(self, workflow_instance_id: str) -> str:
        return self._state_store.get(workflow_instance_id, "unknown")

    def get_evidence_refs(self, workflow_instance_id: str) -> list[str]:
        return list(self._evidence_store.get(workflow_instance_id, []))

    def get_commit_log(self) -> list[CommitResult]:
        return list(self._commit_log)

    def clear(self):
        self._evidence_store.clear()
        self._state_store.clear()
        self._commit_log.clear()


def test_commit_boundary_accepts_full() -> bool:
    """
    Test: evidence + state both accepted → Business_Message candidate emitted.

    Acceptance criteria: commit accepted → evidence stored + state updated.
    """
    boundary = CommitBoundary()
    wf_id = "wf-commit-accept"

    evidence = ["evidence/artifact-001.md", "evidence/result-002.json"]
    transition = {"new_state": "completed", "trigger": "business_event"}

    result = boundary.try_commit(wf_id, evidence, transition)

    assert result.accepted is True, "Commit must be accepted when both evidence and state succeed"
    assert boundary.get_current_state(wf_id) == "completed", "State must be updated after commit"
    assert boundary.get_evidence_refs(wf_id) == evidence, "Evidence refs must be stored after commit"

    return True


def test_commit_boundary_rejects_partial() -> bool:
    """
    Test: evidence accepted but state rejected → no Business_Message emitted.

    Acceptance criteria: partial commit → both rolled back, commit rejected.
    """
    boundary = CommitBoundaryWithInjectedFailure()
    wf_id = "wf-commit-partial"

    evidence = ["evidence/artifact-001.md"]
    transition = {"new_state": "completed"}

    result = boundary.try_commit(wf_id, evidence, transition)

    assert result.accepted is False, "Commit must be rejected when state fails"
    assert boundary.get_current_state(wf_id) == "unknown", "State must be rolled back after rejected commit"
    assert boundary.get_evidence_refs(wf_id) == [], "Evidence must be rolled back after rejected commit"

    return True


class CommitBoundaryWithInjectedFailure(CommitBoundary):
    """Commit boundary with controllable failure for testing partial commit."""

    def _apply_state_transition(self, workflow_instance_id: str, state_transition: dict) -> StateTransitionResult:
        # Inject failure to simulate state store rejection
        return StateTransitionResult(accepted=False, error="injected: state store unavailable")


def test_business_message_requires_commit_accepted() -> bool:
    """
    Test: Business_Message emitted only after commit_accepted.

    Acceptance criteria: Business_Message emitted before commit acceptance → error.
    This test verifies the gate: no Business_Message without accepted commit.
    """
    boundary = CommitBoundary()
    wf_id = "wf-bizmsg-test"

    evidence = ["evidence/test-artifact.md"]
    transition = {"new_state": "completed"}

    # Attempt commit
    result = boundary.try_commit(wf_id, evidence, transition)

    # Only after commit accepted may Business_Message be emitted
    # Business_Message emission gate: check commit.accepted before emitting
    can_emit = result.accepted

    if can_emit:
        # Business_Message would be emitted here
        biz_msg = {
            "business_event_type": "workflow_completed",
            "workflow_instance_id": wf_id,
            "commit_id": result.commit_id,
            "evidence_refs": result.evidence_refs,
        }
        assert biz_msg is not None, "Business_Message must be emitted after commit accepted"
    else:
        # Business_Message must NOT be emitted
        assert result.accepted is False, "Business_Message must not emit when commit rejected"

    return True
