from nexus.mq.candidate_runtime_identity import build_candidate_registry_record
from nexus.mq.candidate_runtime_scheduler import build_candidate_runtime_claim
from nexus.mq.dispatch_request import DispatchRequest
from nexus.mq.tests.test_candidate_runtime_capacity import _capacity
from nexus.mq.tests.test_candidate_runtime_identity import NOW, _identity, _profile


EVAL_NOW = "2026-05-22T00:00:30+00:00"


def _record():
    return build_candidate_registry_record(profile=_profile(), identity=_identity(), now_at=NOW)


def _request(**overrides):
    data = {
        "request_id": "candidate-request-001",
        "correlation_id": "candidate-correlation-001",
        "work_ref": "work://candidate/001",
        "required_capability": "implementation",
        "required_authority_scope": "workflow.command",
        "required_privacy_scope": "project",
        "allowed_task_boundary": "implementation",
        "no_go_scope": ["no business execution"],
    }
    data.update(overrides)
    return DispatchRequest(**data)


def test_candidate_runtime_non_business_probe_claim_requires_capacity_revision():
    decision = build_candidate_runtime_claim(
        request=_request(),
        record=_record(),
        registry_revision_seen=1,
        capacity_snapshot=_capacity(),
        now_at=EVAL_NOW,
    )

    assert decision.accepted is True
    assert decision.claim is not None
    assert decision.claim.target_runtime_instance_id == "jarvis-runtime-001"
    assert decision.claim.registry_revision_seen == 1
    assert decision.claim.capacity_revision_seen == 1
    assert decision.claim.business_execution_allowed is False
    assert decision.claim.not_business_completion is True


def test_candidate_scheduler_rejects_without_capacity_before_claim():
    decision = build_candidate_runtime_claim(
        request=_request(),
        record=_record(),
        registry_revision_seen=1,
        capacity_snapshot=None,
        now_at=EVAL_NOW,
    )

    assert decision.accepted is False
    assert "CAPACITY_SNAPSHOT_MISSING" in decision.errors


def test_candidate_runtime_duplicate_claim_idempotency_suppressed():
    first = build_candidate_runtime_claim(
        request=_request(),
        record=_record(),
        registry_revision_seen=1,
        capacity_snapshot=_capacity(),
        now_at=EVAL_NOW,
    )
    replay = build_candidate_runtime_claim(
        request=_request(),
        record=_record(),
        registry_revision_seen=1,
        capacity_snapshot=_capacity(),
        now_at=EVAL_NOW,
        prior_claims={first.claim.idempotency_key: first.claim.claim_id},
    )

    assert replay.accepted is True
    assert replay.claim is None
    assert replay.duplicate_suppressed is True
    assert replay.errors == ["DUPLICATE_CLAIM_SUPPRESSED"]


def test_candidate_scheduler_blocks_business_assignment():
    decision = build_candidate_runtime_claim(
        request=_request(assignment_kind="business_task", business_dispatch_authorized=True),
        record=_record(),
        registry_revision_seen=1,
        capacity_snapshot=_capacity(),
        now_at=EVAL_NOW,
    )

    assert decision.accepted is False
    assert "BUSINESS_DISPATCH_NOT_AUTHORIZED" in decision.errors
