"""
MQ Review Queue Producer — 3.5 Implementation
HITL Review_Task publisher: publishes Review_Task only after authority_wait_state persisted.

Design source: GOVERNED_WORKFLOW_RUNTIME_AND_MESSAGE_QUEUE_ARCHITECTURE_V0_1.md §5.4
Baseline status: accepted-for-skeleton (3.5 V1.1, commit 3f7a5a0)

Design rule: coordinator must persist authority_wait_state BEFORE publishing Review_Task.
This ensures the wait survives restarts — HITL review wait is never lost.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid


@dataclass
class ReviewTask:
    """Represents a HITL review task published to the review queue."""
    review_task_id: str = field(default_factory=lambda: f"rtask-{uuid.uuid4().hex[:12]}")
    workflow_instance_id: str = ""
    authority_wait_id: str = ""
    queue_subject: str = "hitl.review.queue"
    checkpoint_id: str = ""
    reviewer_role: str = ""
    artifact_refs: list[str] = field(default_factory=list)
    published_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ReviewQueueProducer:
    """
    HITL Review Queue producer.

    Design rule: Review_Task may only be published after authority_wait_state
    is persisted. This is a hard ordering constraint — no exceptions.
    """

    def __init__(self):
        self._published_tasks: list[ReviewTask] = []
        self._authority_wait_registry: dict[str, dict] = {}  # wait_id → persisted wait state

    def check_wait_state_persisted(self, authority_wait_id: str) -> bool:
        """Check if authority_wait_state has been persisted before publishing."""
        return authority_wait_id in self._authority_wait_registry

    def register_authority_wait(self, wait_id: str, workflow_instance_id: str, checkpoint_id: str) -> None:
        """Register that an authority_wait_state has been persisted."""
        self._authority_wait_registry[wait_id] = {
            "wait_id": wait_id,
            "workflow_instance_id": workflow_instance_id,
            "checkpoint_id": checkpoint_id,
            "persisted_at": datetime.now(timezone.utc).isoformat(),
        }

    def publish_review_task(
        self,
        authority_wait_id: str,
        workflow_instance_id: str,
        checkpoint_id: str,
        reviewer_role: str = "reviewer",
        artifact_refs: list[str] = None,
    ) -> ReviewTask:
        """
        Publish a Review_Task to the HITL review queue.

        Design rule: authority_wait_state MUST be persisted before this is called.
        Raises RuntimeError if wait state is not registered.
        """
        if not self.check_wait_state_persisted(authority_wait_id):
            raise RuntimeError(
                f"WAIT_STATE_NOT_PERSISTED: authority_wait_id={authority_wait_id}. "
                "Review_Task must not be published before authority_wait_state is persisted."
            )

        task = ReviewTask(
            workflow_instance_id=workflow_instance_id,
            authority_wait_id=authority_wait_id,
            checkpoint_id=checkpoint_id,
            reviewer_role=reviewer_role,
            artifact_refs=artifact_refs or [],
        )
        self._published_tasks.append(task)
        return task

    def get_published_tasks(self) -> list[ReviewTask]:
        return list(self._published_tasks)

    def clear(self):
        self._published_tasks.clear()
        self._authority_wait_registry.clear()


def test_review_task_publish_requires_wait_state() -> bool:
    """
    Test: Review_Task published without persisted authority_wait_state → error.

    Acceptance criteria: publishing Review_Task before persisting wait state
    raises RuntimeError with WAIT_STATE_NOT_PERSISTED message.
    """
    producer = ReviewQueueProducer()

    # Attempt to publish WITHOUT registering authority wait state
    try:
        producer.publish_review_task(
            authority_wait_id="fake-wait-id",
            workflow_instance_id="wf-test",
            checkpoint_id="ckpt-001",
        )
        assert False, "Must raise RuntimeError when wait state is not persisted"
    except RuntimeError as e:
        assert "WAIT_STATE_NOT_PERSISTED" in str(e), f"Error must indicate wait state not persisted: {e}"

    # Now register the wait state first, then publish — should succeed
    producer.register_authority_wait(
        wait_id="real-wait-id",
        workflow_instance_id="wf-test",
        checkpoint_id="ckpt-001",
    )

    task = producer.publish_review_task(
        authority_wait_id="real-wait-id",
        workflow_instance_id="wf-test",
        checkpoint_id="ckpt-001",
        artifact_refs=["artifact/test-artifact.md"],
    )

    assert task is not None, "Review_Task must be published after wait state persisted"
    assert task.review_task_id is not None, "Review_Task must have a review_task_id"
    assert task.workflow_instance_id == "wf-test", "Review_Task must reference correct workflow"

    return True
