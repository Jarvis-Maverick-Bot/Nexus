from __future__ import annotations

from nexus.governance.delivery_feedback import (
    validate_feedback_metric_extraction,
    validate_feedback_metric_policy_ref,
)
from nexus.governance.errors import ErrorCode

from ._evidence import write_evidence
from .fixtures.delivery_feedback import valid_extraction, valid_policy


def test_valid_feedback_metric_policy_accepts() -> None:
    result = validate_feedback_metric_policy_ref(valid_policy())

    assert result.accepted is True
    write_evidence("delivery-feedback/feedback-metric-policy-active.json", result.to_evidence(), slice_id="l1gov-slice-008")


def test_feedback_metric_policy_rejects_stale_status() -> None:
    result = validate_feedback_metric_policy_ref(valid_policy(status="stale"))

    assert result.accepted is False
    assert result.error_code == ErrorCode.DELIVERY_FEEDBACK_RECORD_INVALID
    write_evidence("delivery-feedback/feedback-metric-policy-stale-block.json", result.to_evidence(), slice_id="l1gov-slice-008")


def test_feedback_metric_policy_rejects_missing_version() -> None:
    result = validate_feedback_metric_policy_ref(valid_policy(policy_version=None))

    assert result.accepted is False
    assert "policy_version" in result.missing_fields


def test_valid_metric_extraction_accepts_policy_backed_signal() -> None:
    result = validate_feedback_metric_extraction(valid_extraction(), valid_policy())

    assert result.accepted is True
    write_evidence("delivery-feedback/feedback-metric-extraction-valid.json", result.to_evidence(), slice_id="l1gov-slice-008")


def test_metric_extraction_rejects_missing_or_stale_policy() -> None:
    result = validate_feedback_metric_extraction(valid_extraction(), valid_policy(status="superseded"))

    assert result.accepted is False
    assert result.error_code == ErrorCode.DELIVERY_FEEDBACK_RECORD_INVALID


def test_metric_extraction_rejects_low_confidence_approved_signal() -> None:
    result = validate_feedback_metric_extraction(valid_extraction(confidence=0.4, status="approved_signal"), valid_policy())

    assert result.accepted is False
    assert result.error_code == ErrorCode.DELIVERY_FEEDBACK_RECORD_INVALID
    write_evidence("delivery-feedback/feedback-metric-extraction-low-confidence-block.json", result.to_evidence(), slice_id="l1gov-slice-008")


def test_metric_extraction_rejects_direct_mutation_route() -> None:
    result = validate_feedback_metric_extraction(valid_extraction(proposed_promotion_route="update backlog now"), valid_policy())

    assert result.accepted is False
    assert result.error_code == ErrorCode.RAW_FEEDBACK_NO_AUTHORITY_MUTATION
