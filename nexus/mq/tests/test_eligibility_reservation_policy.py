import pytest

from nexus.mq.eligibility_reservation_policy import (
    RuntimeEligibilityDecision,
    RuntimeReservationLease,
    consume_reservation_lease,
    release_reservation_lease,
    validate_assignment_publish,
)


NOW = "2026-05-27T07:00:00+00:00"


def _decision(**overrides):
    data = {
        "decision_id": "decision-001",
        "request_id": "eligibility-001",
        "dispatch_run_id": "run-001",
        "assignment_id": "assignment-001",
        "target_agent_id": "jarvis",
        "target_runtime_instance_id": "jarvis-runtime-001",
        "accepted": True,
        "policy_hash": "policy-hash-001",
        "idempotency_key": "idem-001",
        "evidence_refs": ["evidence://decision/001"],
    }
    data.update(overrides)
    return RuntimeEligibilityDecision(**data)


def _lease(**overrides):
    data = {
        "lease_id": "lease-001",
        "lifecycle_decision_id": "decision-001",
        "assignment_id": "assignment-001",
        "dispatch_run_id": "run-001",
        "target_runtime_instance_id": "jarvis-runtime-001",
        "active": True,
        "status": "active",
        "expires_at": "2026-05-27T07:01:00+00:00",
        "policy_hash": "policy-hash-001",
        "idempotency_key": "idem-001",
    }
    data.update(overrides)
    return RuntimeReservationLease(**data)


def test_assignment_publish_requires_allowed_decision_and_active_lease():
    result = validate_assignment_publish(
        decision=_decision(),
        lease=_lease(),
        assignment_id="assignment-001",
        dispatch_run_id="run-001",
        runtime_instance_id="jarvis-runtime-001",
        idempotency_key="idem-001",
        now_at=NOW,
    )

    assert result.accepted is True
    assert result.errors == []


def test_assignment_publish_blocks_expired_lifecycle_decision():
    result = validate_assignment_publish(
        decision=_decision(valid_until="2026-05-27T06:59:59+00:00"),
        lease=_lease(),
        assignment_id="assignment-001",
        dispatch_run_id="run-001",
        runtime_instance_id="jarvis-runtime-001",
        idempotency_key="idem-001",
        now_at=NOW,
    )

    assert result.accepted is False
    assert "LIFECYCLE_DECISION_EXPIRED" in result.errors


def test_assignment_publish_blocks_missing_decision_or_lease():
    result = validate_assignment_publish(
        decision=None,
        lease=None,
        assignment_id="assignment-001",
        dispatch_run_id="run-001",
        runtime_instance_id="jarvis-runtime-001",
        idempotency_key="idem-001",
        now_at=NOW,
    )

    assert result.accepted is False
    assert "MISSING_LIFECYCLE_DECISION" in result.errors
    assert "MISSING_RESERVATION_LEASE" in result.errors


@pytest.mark.parametrize(
    "decision,lease,error",
    [
        (_decision(accepted=False, errors=["NO_ELIGIBLE_RUNTIME"]), _lease(), "LIFECYCLE_DECISION_NOT_ALLOWED"),
        (_decision(decision_id="decision-other"), _lease(), "LIFECYCLE_DECISION_ID_MISMATCH"),
        (_decision(), _lease(active=False, status="released"), "RESERVATION_LEASE_NOT_ACTIVE"),
        (_decision(), _lease(status="revoked", revoked=True), "RESERVATION_LEASE_REVOKED"),
        (_decision(), _lease(expires_at="2026-05-27T06:59:59+00:00"), "RESERVATION_LEASE_EXPIRED"),
        (_decision(), _lease(target_runtime_instance_id="other-runtime"), "LEASE_RUNTIME_ID_MISMATCH"),
        (_decision(), _lease(assignment_id="assignment-other"), "LEASE_ASSIGNMENT_ID_MISMATCH"),
        (_decision(), _lease(policy_hash="policy-other"), "LEASE_POLICY_HASH_MISMATCH"),
    ],
)
def test_assignment_publish_blocks_invalid_decision_or_lease(decision, lease, error):
    result = validate_assignment_publish(
        decision=decision,
        lease=lease,
        assignment_id="assignment-001",
        dispatch_run_id="run-001",
        runtime_instance_id="jarvis-runtime-001",
        idempotency_key="idem-001",
        now_at=NOW,
    )

    assert result.accepted is False
    assert error in result.errors


def test_consumed_or_released_lease_cannot_be_reused():
    consumed = consume_reservation_lease(_lease(), consumed_at=NOW)
    released = release_reservation_lease(_lease(), released_at=NOW, reason_ref="drain://run-001")

    for lease, expected in [
        (consumed, "RESERVATION_LEASE_CONSUMED"),
        (released, "RESERVATION_LEASE_RELEASED"),
    ]:
        result = validate_assignment_publish(
            decision=_decision(),
            lease=lease,
            assignment_id="assignment-001",
            dispatch_run_id="run-001",
            runtime_instance_id="jarvis-runtime-001",
            idempotency_key="idem-001",
            now_at=NOW,
        )
        assert result.accepted is False
        assert expected in result.errors
