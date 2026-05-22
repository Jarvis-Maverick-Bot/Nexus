from nexus.mq.candidate_runtime_capacity import CandidateRuntimeCapacitySnapshot, evaluate_capacity_before_claim


NOW = "2026-05-22T00:00:30+00:00"


def _capacity(**overrides):
    data = {
        "runtime_instance_id": "jarvis-runtime-001",
        "capacity_revision": 1,
        "observed_at": "2026-05-22T00:00:00+00:00",
        "accepting_new_work": True,
        "active_assignment_count": 0,
        "max_concurrent_assignments": 1,
        "load_state": "idle",
        "supported_claim_classes": ["non_business_probe"],
        "evidence_ref": "evidence://capacity/jarvis",
    }
    data.update(overrides)
    return CandidateRuntimeCapacitySnapshot(**data)


def test_candidate_scheduler_requires_capacity_before_claim():
    decision = evaluate_capacity_before_claim(
        _capacity(),
        runtime_instance_id="jarvis-runtime-001",
        required_claim_class="non_business_probe",
        now_at=NOW,
    )

    assert decision.accepted is True
    assert decision.capacity_revision == 1
    assert decision.not_business_completion is True


def test_missing_capacity_fails_closed():
    decision = evaluate_capacity_before_claim(
        None,
        runtime_instance_id="jarvis-runtime-001",
        required_claim_class="non_business_probe",
        now_at=NOW,
    )

    assert decision.accepted is False
    assert decision.errors == ["CAPACITY_SNAPSHOT_MISSING"]


def test_capacity_blocks_stale_full_or_not_accepting_runtime():
    decision = evaluate_capacity_before_claim(
        _capacity(
            observed_at="2026-05-21T23:58:00+00:00",
            accepting_new_work=False,
            active_assignment_count=1,
            load_state="draining",
        ),
        runtime_instance_id="jarvis-runtime-001",
        required_claim_class="non_business_probe",
        now_at=NOW,
    )

    assert decision.accepted is False
    assert "CAPACITY_SNAPSHOT_STALE" in decision.errors
    assert "CAPACITY_NOT_ACCEPTING_NEW_WORK" in decision.errors
    assert "CAPACITY_LIMIT_EXCEEDED" in decision.errors
    assert "CAPACITY_LOAD_STATE_BLOCKED: draining" in decision.errors
