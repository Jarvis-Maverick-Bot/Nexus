from __future__ import annotations

from nexus.governance.delivery_feedback import (
    validate_feedback_triage_decision,
    validate_feedback_triage_decision_request,
)
from nexus.governance.errors import ErrorCode

from ._evidence import write_evidence
from .fixtures.delivery_feedback import valid_triage_decision, valid_triage_request


def test_triage_request_accepts_material_feedback_with_impact_preflight() -> None:
    result = validate_feedback_triage_decision_request(valid_triage_request())

    assert result.accepted is True
    write_evidence("delivery-feedback/triage-request-monitor-required.json", result.to_evidence(), slice_id="l1gov-slice-008")


def test_triage_request_rejects_scope_effect_without_impact_assessment() -> None:
    result = validate_feedback_triage_decision_request(valid_triage_request(impact_assessment_ref=""))

    assert result.accepted is False
    assert result.error_code == ErrorCode.IMPACT_CONTROL_RECORD_INVALID
    write_evidence("delivery-feedback/impact-preflight-required-before-next-cycle.json", result.to_evidence(), slice_id="l1gov-slice-008")


def test_triage_request_rejects_direct_deploy_or_dispatch_option() -> None:
    result = validate_feedback_triage_decision_request(valid_triage_request(options=("deploy_to_production", "actual_dispatch")))

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY


def test_triage_decision_accepts_human_decision_backed_candidate_route() -> None:
    result = validate_feedback_triage_decision(valid_triage_decision())

    assert result.accepted is True
    write_evidence("delivery-feedback/triage-decision-with-human-decision.json", result.to_evidence(), slice_id="l1gov-slice-008")


def test_triage_decision_rejects_without_human_decision() -> None:
    result = validate_feedback_triage_decision(valid_triage_decision(human_decision_ref=""))

    assert result.accepted is False
    assert result.error_code == ErrorCode.MISSING_HUMAN_DECISION
    write_evidence("delivery-feedback/triage-decision-without-human-decision-block.json", result.to_evidence(), slice_id="l1gov-slice-008")


def test_triage_decision_rejects_direct_backlog_mutation_route() -> None:
    result = validate_feedback_triage_decision(valid_triage_decision(approved_route="update backlog now"))

    assert result.accepted is False
    assert result.error_code == ErrorCode.RAW_FEEDBACK_NO_AUTHORITY_MUTATION
