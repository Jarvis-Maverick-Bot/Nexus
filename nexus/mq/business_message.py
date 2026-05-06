"""
MQ Business Message — 3.5 Implementation
Business_Message emitter: emitted ONLY after evidence/state commit accepted.

Design source: GOVERNED_WORKFLOW_RUNTIME_AND_MESSAGE_QUEUE_ARCHITECTURE_V0_1.md §7.4
Baseline status: accepted-for-skeleton (3.5 V1.1, commit 3f7a5a0)

Business_Message semantics:
- Emitted only after commit boundary accepts required evidence refs and state transition
- The first message that represents accepted governed business progress
- Handler success alone does NOT emit Business_Message
- Business progress is emitted as a durable event for downstream consumption
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid


@dataclass
class BusinessMessage:
    """
    Represents accepted governed business progress.

    Design rule: this is emitted ONLY after accepted evidence/state commit.
    It is NOT emitted on handler success — handler success is a candidate.
    """
    business_event_id: str = field(default_factory=lambda: f"biz-{uuid.uuid4().hex[:12]}")
    business_event_type: str = ""
    workflow_instance_id: str = ""
    transition_id: str = ""
    commit_id: str = ""
    previous_state: str = ""
    new_state: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    validation_result: str = "accepted"
    emitted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "business_event_id": self.business_event_id,
            "business_event_type": self.business_event_type,
            "workflow_instance_id": self.workflow_instance_id,
            "transition_id": self.transition_id,
            "commit_id": self.commit_id,
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "evidence_refs": self.evidence_refs,
            "validation_result": self.validation_result,
            "emitted_at": self.emitted_at,
        }


class BusinessMessageEmitter:
    """
    Business_Message emitter.

    Design rule: emit() may only be called after commit_accepted.
    Calling emit() without accepted commit is a design rule violation.
    """

    def __init__(self):
        self._emitted: list[BusinessMessage] = []

    def emit(
        self,
        commit_result: "CommitResult",  # from commit_boundary
        business_event_type: str,
        previous_state: str,
    ) -> BusinessMessage:
        """
        Emit Business_Message after commit acceptance.

        Args:
            commit_result: result from CommitBoundary.try_commit()
            business_event_type: type of business event
            previous_state: state before transition

        Design rule: only emit after commit accepted.
        """
        if not commit_result.accepted:
            raise ValueError(
                f"Business_Message.emit() called with rejected commit: {commit_result.error}. "
                "Business_Message may only be emitted after accepted evidence/state commit."
            )

        biz_msg = BusinessMessage(
            business_event_type=business_event_type,
            workflow_instance_id=commit_result.workflow_instance_id,
            transition_id=commit_result.state_transition.get("new_state", "") if commit_result.state_transition else "",
            commit_id=commit_result.commit_id,
            previous_state=previous_state,
            new_state=commit_result.state_transition.get("new_state", "") if commit_result.state_transition else "",
            evidence_refs=commit_result.evidence_refs,
        )
        self._emitted.append(biz_msg)
        return biz_msg

    def get_emitted(self) -> list[BusinessMessage]:
        return list(self._emitted)

    def clear(self):
        self._emitted.clear()
