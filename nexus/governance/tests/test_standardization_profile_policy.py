from __future__ import annotations

from nexus.governance.errors import ErrorCode
from nexus.governance.standardization import (
    validate_deliverable_evaluation_profile,
    validate_feedback_metric_policy,
    validate_standardization_bundle,
)

from ._evidence import write_evidence
from .fixtures.standardization import valid_execution_plan, valid_feedback_policy, valid_profile


def test_deliverable_evaluation_profile_accepts_complete_review_policy() -> None:
    result = validate_deliverable_evaluation_profile(valid_profile())

    assert result.accepted is True
    write_evidence(
        "standardization/evaluation-profile-policy.json",
        result.to_evidence(),
        slice_id="l1gov-slice-003",
    )


def test_deliverable_evaluation_profile_requires_llm_constraints_and_thresholds() -> None:
    result = validate_deliverable_evaluation_profile(valid_profile(llm_review_constraints=(), pass_threshold=True))

    assert result.accepted is False
    assert result.error_code == ErrorCode.MISSING_EVALUATION_PROFILE
    assert result.missing_fields == ("llm_review_constraints", "pass_threshold")
    write_evidence(
        "standardization/evaluation-profile-field-block.json",
        result.to_evidence(),
        slice_id="l1gov-slice-003",
    )


def test_material_deliverable_without_profile_is_rejected() -> None:
    result = validate_standardization_bundle(
        plan=valid_execution_plan(profile_refs=()),
        profiles=(),
        feedback_policy=valid_feedback_policy(),
    )

    assert result.accepted is False
    assert result.error_code == ErrorCode.MISSING_EVALUATION_PROFILE
    assert "material deliverable lacks evaluation profile: implementation-design-package" in result.blocked_reasons
    write_evidence("standardization/missing-profile.json", result.to_evidence(), slice_id="l1gov-slice-003")


def test_feedback_driven_plan_requires_metric_policy() -> None:
    result = validate_standardization_bundle(
        plan=valid_execution_plan(feedback_metric_policy_ref=""),
        profiles=(valid_profile(),),
        feedback_policy=None,
        feedback_driven_change=True,
    )

    assert result.accepted is False
    assert result.error_code == ErrorCode.RAW_FEEDBACK_NO_AUTHORITY_MUTATION
    assert "feedback-driven planning change requires FeedbackMetricPolicy" in result.blocked_reasons
    write_evidence("standardization/feedback-policy.json", result.to_evidence(), slice_id="l1gov-slice-003")


def test_feedback_metric_policy_requires_measurement_fields() -> None:
    result = validate_feedback_metric_policy(valid_feedback_policy(severity_scale=(), promotion_thresholds={}))

    assert result.accepted is False
    assert result.error_code == ErrorCode.STANDARDIZATION_RECORD_INVALID
    assert result.missing_fields == ("severity_scale", "promotion_thresholds")
