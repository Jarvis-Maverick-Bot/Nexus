"""
MQ Skeleton Tests — 3.5 Implementation
Run: python -m pytest nexus/mq/tests/test_mq_skeleton.py -v
Or: python nexus/mq/tests/test_mq_skeleton.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nexus.mq.envelope import MessageEnvelope, build_envelope
from nexus.mq.ack_policy import AckPolicy, WorkflowStateSeparator, test_ack_means_intake_only
from nexus.mq.idempotency_store import IdempotencyStore, test_command_idempotent_dedupe
from nexus.mq.adapter import MqAdapterStub, RetryConfig, test_dlq_on_retry_exhaustion, test_adapter_stub_publish_consume, test_adapter_stub_ack_policy
from nexus.mq.commit_boundary import CommitBoundary, CommitBoundaryWithInjectedFailure, test_commit_boundary_accepts_full, test_commit_boundary_rejects_partial, test_business_message_requires_commit_accepted
from nexus.mq.hitl_feedback_handler import HitlFeedbackHandler, test_feedback_reject_stale, test_feedback_reject_revise_without_text, test_feedback_approve_requires_actor, test_hitl_synthetic_feedback_resume
from nexus.mq.business_message import BusinessMessageEmitter
from nexus.mq.review_queue import ReviewQueueProducer, test_review_task_publish_requires_wait_state
from nexus.mq.command_handler import CommandHandler


def test_envelope_required_fields():
    """Envelope missing message_id → validation error."""
    env = MessageEnvelope(message_type="Command_Message", message_class="command")
    env.message_id = ""  # force empty
    result = env.validate()
    assert result.valid is False, "Empty message_id must fail validation"
    assert any("message_id" in e for e in result.errors), "Error must mention message_id"
    print("PASS: test_envelope_required_fields")


def test_envelope_workflow_refs():
    """Envelope missing workflow_instance_id → validation error."""
    env = MessageEnvelope(
        message_type="Command_Message",
        message_class="command",
        message_id="msg-001",
        idempotency_key="idem-001",
        producer="test",
    )
    env.workflow_instance_id = ""
    result = env.validate()
    assert result.valid is False, "Empty workflow_instance_id must fail validation"
    assert any("workflow_instance_id" in e for e in result.errors), "Error must mention workflow_instance_id"
    print("PASS: test_envelope_workflow_refs")


def test_envelope_valid_full():
    """Full valid envelope passes validation."""
    env = build_envelope(
        message_type="Command_Message",
        workflow_instance_id="wf-001",
        workflow_type="test",
        workflow_version="1.0",
        producer="test-producer",
        payload={"command": "test"},
        idempotency_key="idem-full-001",
    )
    result = env.validate()
    assert result.valid is True, f"Full envelope must pass validation: {result.errors}"
    print("PASS: test_envelope_valid_full")


def run_all_tests():
    print("=" * 60)
    print("MQ SKELETON TESTS — 3.5 Implementation")
    print("=" * 60)

    tests = [
        # Envelope
        test_envelope_required_fields,
        test_envelope_workflow_refs,
        test_envelope_valid_full,

        # ACK policy
        ("test_ack_means_intake_only", test_ack_means_intake_only),

        # Idempotency
        ("test_command_idempotent_dedupe", test_command_idempotent_dedupe),

        # Adapter/Retry/DLQ
        ("test_dlq_on_retry_exhaustion", test_dlq_on_retry_exhaustion),
        ("test_adapter_stub_publish_consume", test_adapter_stub_publish_consume),
        ("test_adapter_stub_ack_policy", test_adapter_stub_ack_policy),

        # Commit boundary
        ("test_commit_boundary_accepts_full", test_commit_boundary_accepts_full),
        ("test_commit_boundary_rejects_partial", test_commit_boundary_rejects_partial),
        ("test_business_message_requires_commit_accepted", test_business_message_requires_commit_accepted),

        # HITL feedback
        ("test_feedback_reject_stale", test_feedback_reject_stale),
        ("test_feedback_reject_revise_without_text", test_feedback_reject_revise_without_text),
        ("test_feedback_approve_requires_actor", test_feedback_approve_requires_actor),
        ("test_hitl_synthetic_feedback_resume", test_hitl_synthetic_feedback_resume),

        # Review queue
        ("test_review_task_publish_requires_wait_state", test_review_task_publish_requires_wait_state),
    ]

    passed = 0
    failed = 0

    for item in tests:
        name = item[0] if isinstance(item, tuple) else item.__name__
        fn = item[1] if isinstance(item, tuple) else item
        try:
            result = fn()
            if result is not False:
                passed += 1
                print(f"  PASS: {name}")
            else:
                failed += 1
                print(f"  FAIL: {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL: {name} — {e}")
        except Exception as e:
            failed += 1
            print(f"  ERROR: {name} — {e}")

    print()
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        print("SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED")


if __name__ == "__main__":
    run_all_tests()
