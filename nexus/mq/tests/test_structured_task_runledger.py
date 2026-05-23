from nexus.mq.structured_task_models import RunLedger
from nexus.mq.structured_task_runledger import transition_runledger


def _ledger(state="created"):
    return RunLedger(
        run_id="run-001",
        task_id="task-001",
        envelope_version="v1",
        packet_id="packet-001",
        selected_role="implementer",
        selected_runtime_id="runtime-001",
        current_state=state,
        state_history=[state],
        checkpoint_refs=[],
        interruption_reason=None,
        timeout_at=None,
        started_at=None,
        completed_at=None,
        last_event_at="2026-05-23T00:00:00+00:00",
    )


def test_runledger_allows_normalized_to_validated_only_after_validation():
    result = transition_runledger(
        _ledger("normalized"),
        "validated",
        evidence_ref="evidence://validation",
    )

    assert result.ok is True
    assert result.ledger.current_state == "validated"


def test_runledger_rejects_invalid_state_skip():
    result = transition_runledger(
        _ledger("normalized"),
        "routed",
        evidence_ref="evidence://route",
    )

    assert result.ok is False
    assert "INVALID_RUNLEDGER_TRANSITION: normalized -> routed" in result.errors


def test_dispatch_ack_running_separation():
    skip = transition_runledger(
        _ledger("routed"),
        "acked",
        evidence_ref="evidence://ack",
    )
    dispatched = transition_runledger(
        _ledger("routed"),
        "dispatched",
        evidence_ref="evidence://dispatch",
    )

    assert skip.ok is False
    assert dispatched.ok is True
    assert dispatched.ledger.current_state == "dispatched"


def test_completed_is_not_acceptance():
    result = transition_runledger(
        _ledger("checkpointed"),
        "completed",
        evidence_ref="evidence://result-candidate",
    )

    assert result.ok is True
    assert result.ledger.current_state == "completed"
    assert result.ledger.not_business_completion is True
    assert "completed" in result.ledger.state_history


def test_missing_evidence_blocks_transition():
    result = transition_runledger(_ledger("created"), "normalized", evidence_ref="")

    assert result.ok is False
    assert "MISSING_TRANSITION_EVIDENCE" in result.errors
