from __future__ import annotations

from nexus.governance.delivery_feedback import validate_feedback_metric_trend
from nexus.governance.errors import ErrorCode

from ._evidence import write_evidence
from .fixtures.delivery_feedback import valid_policy, valid_trend


def test_valid_feedback_metric_trend_accepts_review_required_threshold() -> None:
    result = validate_feedback_metric_trend(valid_trend(), valid_policy())

    assert result.accepted is True
    write_evidence(
        "delivery-feedback/feedback-metric-trend-threshold-met-review-required.json",
        result.to_evidence(),
        slice_id="l1gov-slice-008",
    )


def test_feedback_metric_trend_rejects_empty_signal_refs() -> None:
    result = validate_feedback_metric_trend(valid_trend(metric_signal_refs=()), valid_policy())

    assert result.accepted is False
    assert "metric_signal_refs" in result.missing_fields


def test_feedback_metric_trend_rejects_stale_policy_version() -> None:
    result = validate_feedback_metric_trend(valid_trend(policy_version=2), valid_policy(policy_version=3))

    assert result.accepted is False
    assert result.error_code == ErrorCode.DELIVERY_FEEDBACK_RECORD_INVALID


def test_feedback_metric_trend_rejects_unknown_threshold_status() -> None:
    result = validate_feedback_metric_trend(valid_trend(threshold_status="ship_it"), valid_policy())

    assert result.accepted is False
    assert result.error_code == ErrorCode.DELIVERY_FEEDBACK_RECORD_INVALID


def test_feedback_metric_trend_rejects_threshold_met_without_review_route() -> None:
    result = validate_feedback_metric_trend(valid_trend(threshold_status="threshold_met", status="threshold_met"), valid_policy())

    assert result.accepted is False
    assert result.error_code == ErrorCode.MISSING_HUMAN_DECISION


def test_feedback_metric_trend_rejects_direct_mutation_recommended_action() -> None:
    result = validate_feedback_metric_trend(valid_trend(recommended_next_action="update success criteria directly"), valid_policy())

    assert result.accepted is False
    assert result.error_code == ErrorCode.RAW_FEEDBACK_NO_AUTHORITY_MUTATION
