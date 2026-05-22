import pytest

from nexus.mq.candidate_runtime_evidence import (
    build_candidate_runtime_evidence,
    validate_candidate_runtime_evidence,
)


def test_candidate_runtime_evidence_shape_is_non_business_and_non_secret():
    record = build_candidate_runtime_evidence(
        evidence_type="capacity_before_claim",
        status="accepted",
        refs=["evidence://capacity/jarvis"],
        details={"runtime_instance_id": "jarvis-runtime-001"},
    )

    assert record.not_business_completion is True
    assert validate_candidate_runtime_evidence(record) == []


def test_candidate_runtime_evidence_rejects_secret_values():
    with pytest.raises(ValueError) as excinfo:
        build_candidate_runtime_evidence(
            evidence_type="secret_scan",
            status="accepted",
            refs=["evidence://secret"],
            details={"raw_value": "token=abc123"},
        )

    assert "SECRET_MATERIAL_VALUE" in str(excinfo.value)
