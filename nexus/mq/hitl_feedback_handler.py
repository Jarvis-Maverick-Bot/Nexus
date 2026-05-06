"""
MQ HITL Feedback Handler — 3.5 Implementation
HITL Feedback validation, normalization, and resume.

Design source: GOVERNED_WORKFLOW_RUNTIME_AND_MESSAGE_QUEUE_ARCHITECTURE_V0_1.md §5.4
Baseline status: accepted-for-skeleton (3.5 V1.1, commit 3f5a5a0)

HITL flow:
1. Coordinator persists authority_wait_state before publishing Review_Task
2. Review backend sends Feedback_Message (Approve/Reject/Revise)
3. Coordinator validates Feedback_Message (actor, scope, staleness)
4. Valid feedback normalized into HITL decision record
5. Workflow resumes only after decision record exists

Design rules:
- No full PMO/Nexus review backend required for skeleton
- HITL tests use synthetic/fixture Feedback_Message to exercise validation, normalization, resume
- Revise without feedback_text is rejected
- Feedback from unauthorized actor is rejected
- Stale feedback (for non-current authority_wait) is rejected
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Any
import uuid


@dataclass
class FeedbackValidationResult:
    """Result of Feedback_Message validation."""
    valid: bool
    normalized_decision: Optional[dict] = None
    errors: list[str] = field(default_factory=list)


@dataclass
class HitlDecisionRecord:
    """Normalized HITL decision record — the only thing that authorizes workflow resume."""
    record_id: str = field(default_factory=lambda: f"hitl-dr-{uuid.uuid4().hex[:12]}")
    workflow_instance_id: str = ""
    authority_wait_id: str = ""
    reviewer_actor_id: str = ""
    reviewer_role: str = ""
    action: str = ""            # Approve | Reject | Revise
    feedback_text: Optional[str] = None
    submitted_at: str = ""
    reviewed_artifact_refs: list[str] = field(default_factory=list)
    normalized_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class AuthorityWaitState:
    """Persisted authority wait state — survives restarts."""
    wait_id: str = field(default_factory=lambda: f"auth-wait-{uuid.uuid4().hex[:12]}")
    workflow_instance_id: str = ""
    checkpoint_id: str = ""
    wait_state: str = "waiting"   # waiting | notified | responded | resolved | timed_out | escalated
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    responded_at: Optional[str] = None
    resumed_at: Optional[str] = None


class HitlFeedbackHandler:
    """
    HITL Feedback validation and normalization.

    Design rule: Feedback_Message goes through multi-step validation before
    becoming a HITL decision record. Web UI action alone is not business progress.
    """

    VALID_ACTIONS = {"Approve", "Reject", "Revise"}
    VALID_WAIT_STATES = {"waiting", "notified", "responded"}

    def __init__(self):
        self._authority_waits: dict[str, AuthorityWaitState] = {}  # wait_id → wait state
        self._decision_records: list[HitlDecisionRecord] = []
        self._feedback_log: list[FeedbackValidationResult] = []

    def create_authority_wait(
        self,
        workflow_instance_id: str,
        checkpoint_id: str,
    ) -> AuthorityWaitState:
        """Persist authority_wait_state before publishing Review_Task."""
        wait = AuthorityWaitState(
            workflow_instance_id=workflow_instance_id,
            checkpoint_id=checkpoint_id,
        )
        self._authority_waits[wait.wait_id] = wait
        return wait

    def validate_feedback(
        self,
        feedback_id: str,
        authority_wait_id: str,
        reviewer_actor_id: str,
        reviewer_role: str,
        action: str,
        feedback_text: Optional[str],
        submitted_at: str,
        reviewed_artifact_refs: list[str] = None,
        authorized_reviewers: Optional[set[str]] = None,
    ) -> FeedbackValidationResult:
        """
        Validate a Feedback_Message.

        Validation rules:
        1. action must be one of Approve/Reject/Revise
        2. Revise requires non-empty feedback_text
        3. Feedback must target a current authority_wait (not stale)
        4. Reviewer must be authorized

        Design rule: stale/ unauthorized/Revise-without-text feedback is rejected.
        """
        errors = []
        authorized_reviewers = authorized_reviewers or {"alex", "nova"}

        # Rule 1: valid action
        if action not in self.VALID_ACTIONS:
            errors.append(f"INVALID_ACTION: {action}")

        # Rule 2: Revise requires feedback_text
        if action == "Revise" and not feedback_text:
            errors.append("REVISE_WITHOUT_TEXT: Revise action requires non-empty feedback_text")

        # Rule 3: authority_wait must exist and be current (not resolved/escalated)
        if authority_wait_id not in self._authority_waits:
            errors.append(f"FEEDBACK_STALE: authority_wait {authority_wait_id} not found")
        else:
            wait = self._authority_waits[authority_wait_id]
            if wait.wait_state in ("resolved", "escalated"):
                errors.append(f"FEEDBACK_STALE: authority_wait is {wait.wait_state}")

        # Rule 4: reviewer must be authorized
        if reviewer_actor_id not in authorized_reviewers:
            errors.append(f"REVIEWER_NOT_AUTHORIZED: {reviewer_actor_id} not in authorized set")

        valid = len(errors) == 0

        result = FeedbackValidationResult(
            valid=valid,
            errors=errors,
        )
        self._feedback_log.append(result)

        if valid:
            # Normalize to HITL decision record
            decision = self._normalize_decision(
                feedback_id=feedback_id,
                authority_wait_id=authority_wait_id,
                reviewer_actor_id=reviewer_actor_id,
                reviewer_role=reviewer_role,
                action=action,
                feedback_text=feedback_text,
                submitted_at=submitted_at,
                reviewed_artifact_refs=reviewed_artifact_refs or [],
            )
            result.normalized_decision = decision.__dict__

        return result

    def _normalize_decision(
        self,
        feedback_id: str,
        authority_wait_id: str,
        reviewer_actor_id: str,
        reviewer_role: str,
        action: str,
        feedback_text: Optional[str],
        submitted_at: str,
        reviewed_artifact_refs: list[str],
    ) -> HitlDecisionRecord:
        """Normalize validated feedback into a HITL decision record."""
        # Get workflow_instance_id from authority_wait
        wait = self._authority_waits.get(authority_wait_id)
        workflow_instance_id = wait.workflow_instance_id if wait else ""

        record = HitlDecisionRecord(
            workflow_instance_id=workflow_instance_id,
            authority_wait_id=authority_wait_id,
            reviewer_actor_id=reviewer_actor_id,
            reviewer_role=reviewer_role,
            action=action,
            feedback_text=feedback_text,
            submitted_at=submitted_at,
            reviewed_artifact_refs=reviewed_artifact_refs,
        )
        self._decision_records.append(record)

        # Update authority wait state to responded
        if wait:
            wait.wait_state = "responded"
            wait.responded_at = datetime.now(timezone.utc).isoformat()

        return record

    def can_resume(self, authority_wait_id: str) -> bool:
        """Check if workflow can resume after HITL decision."""
        if authority_wait_id not in self._authority_waits:
            return False
        wait = self._authority_waits[authority_wait_id]
        return wait.wait_state == "responded"

    def get_decision_record(self, authority_wait_id: str) -> Optional[HitlDecisionRecord]:
        """Get the decision record for a given authority wait."""
        for record in self._decision_records:
            if record.authority_wait_id == authority_wait_id:
                return record
        return None

    def clear(self):
        self._authority_waits.clear()
        self._decision_records.clear()
        self._feedback_log.clear()


def test_feedback_reject_stale() -> bool:
    """
    Test: Feedback for non-current authority_wait is rejected.
    """
    handler = HitlFeedbackHandler()

    # Create a wait and mark it resolved
    wait = handler.create_authority_wait("wf-stale-test", "ckpt-001")
    wait.wait_state = "resolved"  # simulate already-resolved wait

    result = handler.validate_feedback(
        feedback_id="fb-001",
        authority_wait_id=wait.wait_id,
        reviewer_actor_id="alex",
        reviewer_role="reviewer",
        action="Approve",
        feedback_text=None,
        submitted_at=datetime.now(timezone.utc).isoformat(),
    )

    assert result.valid is False, "Stale feedback must be rejected"
    assert any("FEEDBACK_STALE" in e for e in result.errors), "Error must indicate stale feedback"

    return True


def test_feedback_reject_revise_without_text() -> bool:
    """
    Test: Feedback action=Revise with empty feedback_text is rejected.
    """
    handler = HitlFeedbackHandler()

    wait = handler.create_authority_wait("wf-revise-test", "ckpt-002")

    result = handler.validate_feedback(
        feedback_id="fb-002",
        authority_wait_id=wait.wait_id,
        reviewer_actor_id="alex",
        reviewer_role="reviewer",
        action="Revise",
        feedback_text="",  # empty — must be rejected
        submitted_at=datetime.now(timezone.utc).isoformat(),
    )

    assert result.valid is False, "Revise without feedback_text must be rejected"
    assert any("REVISE_WITHOUT_TEXT" in e for e in result.errors), "Error must indicate Revise requires text"

    return True


def test_feedback_approve_requires_actor() -> bool:
    """
    Test: Feedback from unauthorized actor is rejected.
    """
    handler = HitlFeedbackHandler()

    wait = handler.create_authority_wait("wf-actor-test", "ckpt-003")

    result = handler.validate_feedback(
        feedback_id="fb-003",
        authority_wait_id=wait.wait_id,
        reviewer_actor_id="unknown-person",  # not in authorized set
        reviewer_role="reviewer",
        action="Approve",
        feedback_text=None,
        submitted_at=datetime.now(timezone.utc).isoformat(),
    )

    assert result.valid is False, "Feedback from unauthorized actor must be rejected"
    assert any("REVIEWER_NOT_AUTHORIZED" in e for e in result.errors), "Error must indicate unauthorized actor"

    return True


def test_hitl_synthetic_feedback_resume() -> bool:
    """
    Test: Synthetic Feedback_Message (Approve/Reject/Revise) enters normalization
    → valid HITL_decision_record → resume triggered.

    Uses synthetic fixture input to exercise full Approve/Reject/Revise path
    without requiring full PMO/Nexus review backend.
    """
    handler = HitlFeedbackHandler()
    wf_id = "wf-hitl-synthetic"

    # Step 1: Create authority_wait (must persist before Review_Task publish)
    wait = handler.create_authority_wait(wf_id, "ckpt-hitl-001")
    assert wait.wait_id is not None, "Authority wait must be created"
    assert wait.wait_state == "waiting", "Wait state must start as 'waiting'"

    # Step 2: Synthetic Approve feedback
    result_approve = handler.validate_feedback(
        feedback_id="fb-synth-approve",
        authority_wait_id=wait.wait_id,
        reviewer_actor_id="alex",
        reviewer_role="reviewer",
        action="Approve",
        feedback_text=None,
        submitted_at=datetime.now(timezone.utc).isoformat(),
        reviewed_artifact_refs=["artifact/test-artifact.md"],
    )

    assert result_approve.valid is True, f"Approve feedback must be valid: {result_approve.errors}"
    assert result_approve.normalized_decision is not None, "Normalized decision must be present"
    assert result_approve.normalized_decision["action"] == "Approve", "Normalized action must be Approve"

    # Resume is now authorized
    assert handler.can_resume(wait.wait_id) is True, "Workflow must be resumable after Approve"

    # Step 3: Synthetic Revise feedback on different wait
    wait2 = handler.create_authority_wait(wf_id, "ckpt-hitl-002")
    result_revise = handler.validate_feedback(
        feedback_id="fb-synth-revise",
        authority_wait_id=wait2.wait_id,
        reviewer_actor_id="nova",
        reviewer_role="reviewer",
        action="Revise",
        feedback_text="Please refine the evidence section before proceeding.",
        submitted_at=datetime.now(timezone.utc).isoformat(),
        reviewed_artifact_refs=["artifact/test-artifact-v2.md"],
    )

    assert result_revise.valid is True, f"Revise with feedback_text must be valid: {result_revise.errors}"
    assert result_revise.normalized_decision["action"] == "Revise", "Normalized action must be Revise"
    assert result_revise.normalized_decision["feedback_text"] is not None, "Revise feedback_text must be preserved"

    # Step 4: Reject feedback
    wait3 = handler.create_authority_wait(wf_id, "ckpt-hitl-003")
    result_reject = handler.validate_feedback(
        feedback_id="fb-synth-reject",
        authority_wait_id=wait3.wait_id,
        reviewer_actor_id="alex",
        reviewer_role="reviewer",
        action="Reject",
        feedback_text=None,
        submitted_at=datetime.now(timezone.utc).isoformat(),
    )

    assert result_reject.valid is True, f"Reject feedback must be valid: {result_reject.errors}"
    assert result_reject.normalized_decision["action"] == "Reject", "Normalized action must be Reject"

    return True
