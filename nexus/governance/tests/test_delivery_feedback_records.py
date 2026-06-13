from __future__ import annotations

import pytest

from nexus.governance.delivery_feedback import (
    validate_accepted_increment_ref,
    validate_delivery_record,
    validate_feedback_record,
)
from nexus.governance.errors import ErrorCode

from ._evidence import write_evidence
from .fixtures.delivery_feedback import (
    valid_accepted_increment,
    valid_delivery_record,
    valid_feedback_record,
)


def test_valid_accepted_increment_ref_accepts() -> None:
    result = validate_accepted_increment_ref(valid_accepted_increment())

    assert result.accepted is True
    write_evidence("delivery-feedback/accepted-increment-valid.json", result.to_evidence(), slice_id="l1gov-slice-008")


@pytest.mark.parametrize(
    "field_name",
    ("accepted_decision_ref", "evidence_refs", "deliverable_evaluation_result_refs"),
)
def test_accepted_increment_ref_rejects_missing_authority_fields(field_name: str) -> None:
    result = validate_accepted_increment_ref(
        valid_accepted_increment(**{field_name: () if field_name.endswith("refs") else ""})
    )

    assert result.accepted is False
    assert result.error_code == ErrorCode.DELIVERY_FEEDBACK_RECORD_INVALID
    assert field_name in result.missing_fields


@pytest.mark.parametrize("status", ("submitted", "active", "complete", "final_pass", "production_ready"))
def test_accepted_increment_ref_rejects_non_increment_status(status: str) -> None:
    result = validate_accepted_increment_ref(valid_accepted_increment(status=status))

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY


def test_valid_delivery_record_accepts() -> None:
    result = validate_delivery_record(valid_delivery_record(), valid_accepted_increment())

    assert result.accepted is True
    write_evidence("delivery-feedback/delivery-record-valid.json", result.to_evidence(), slice_id="l1gov-slice-008")


def test_delivery_record_rejects_production_deploy_implication() -> None:
    result = validate_delivery_record(
        valid_delivery_record(preview_or_release_scope="deploy to production", status="production_ready"),
        valid_accepted_increment(),
    )

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    write_evidence("delivery-feedback/delivery-record-production-deploy-no-go.json", result.to_evidence(), slice_id="l1gov-slice-008")


def test_delivery_record_rejects_without_accepted_increment() -> None:
    result = validate_delivery_record(valid_delivery_record(), valid_accepted_increment(status="submitted"))

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY


def test_valid_feedback_record_accepts() -> None:
    result = validate_feedback_record(valid_feedback_record())

    assert result.accepted is True
    write_evidence("delivery-feedback/feedback-record-valid.json", result.to_evidence(), slice_id="l1gov-slice-008")


@pytest.mark.parametrize(
    "raw_summary",
    (
        "mutate backlog from this raw feedback",
        "update scope directly",
        "update success criteria now",
        "update no-go now",
        "update priority now",
        "mutate packet now",
        "create requirement from one comment",
        "approve completion",
        "mark production_ready",
    ),
)
def test_feedback_record_rejects_raw_feedback_direct_mutation(raw_summary: str) -> None:
    result = validate_feedback_record(valid_feedback_record(raw_summary=raw_summary))

    assert result.accepted is False
    assert result.error_code == ErrorCode.RAW_FEEDBACK_NO_AUTHORITY_MUTATION
    write_evidence(
        f"delivery-feedback/raw-feedback-direct-{raw_summary.split()[0].replace('_', '-')}-mutation-no-go.json",
        result.to_evidence(),
        slice_id="l1gov-slice-008",
    )


def test_feedback_record_rejects_without_delivery_or_project_ref() -> None:
    result = validate_feedback_record(valid_feedback_record(delivery_ref="", project_id=""))

    assert result.accepted is False
    assert result.error_code == ErrorCode.DELIVERY_FEEDBACK_RECORD_INVALID
