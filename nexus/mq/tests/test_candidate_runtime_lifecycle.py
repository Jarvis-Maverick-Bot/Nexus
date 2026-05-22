from dataclasses import replace

from nexus.mq.candidate_runtime_lifecycle import evaluate_candidate_runtime_lifecycle
from nexus.mq.tests.test_candidate_runtime_identity import NOW, _identity, _profile
from nexus.mq.candidate_runtime_identity import build_candidate_registry_record


def _record(**overrides):
    record = build_candidate_registry_record(profile=_profile(), identity=_identity(), now_at=NOW)
    return replace(record, **overrides)


def test_candidate_lifecycle_ready_idle_runtime_is_eligible_for_claim():
    decision = evaluate_candidate_runtime_lifecycle(_record(), now_at="2026-05-22T00:00:30+00:00")

    assert decision.accepted is True
    assert decision.lifecycle_state == "eligible_for_claim"
    assert decision.not_business_completion is True


def test_candidate_lifecycle_startup_packet_expired_fails_closed():
    decision = evaluate_candidate_runtime_lifecycle(
        _record(startup_packet_expires_at="2026-05-21T23:59:00+00:00"),
        now_at="2026-05-22T00:00:30+00:00",
    )

    assert decision.accepted is False
    assert decision.lifecycle_state == "validating"
    assert "STARTUP_PACKET_EXPIRED" in decision.errors


def test_candidate_lifecycle_stale_or_not_accepting_blocks_claim():
    decision = evaluate_candidate_runtime_lifecycle(
        _record(presence_state="stale", accepting_new_work=False),
        now_at="2026-05-22T00:00:30+00:00",
    )

    assert decision.accepted is False
    assert decision.lifecycle_state == "stale"
    assert "PRESENCE_BLOCKS_CLAIM: stale" in decision.errors
    assert "NOT_ACCEPTING_NEW_WORK" in decision.errors
