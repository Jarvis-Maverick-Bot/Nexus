from __future__ import annotations

import pytest

from nexus.governance.delivery_feedback import validate_completion_continuity_packet
from nexus.governance.errors import ErrorCode

from ._evidence import write_evidence
from .fixtures.delivery_feedback import valid_completion_packet


@pytest.mark.parametrize("status", ("complete", "continuity_active", "production_ready", "deployed", "final_pass"))
def test_completion_packet_rejects_completion_or_production_status(status: str) -> None:
    result = validate_completion_continuity_packet(valid_completion_packet(status=status))

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    write_evidence(
        f"delivery-feedback/completion-{status.replace('_', '-')}-block.json",
        result.to_evidence(),
        slice_id="l1gov-slice-008",
    )


def test_completion_packet_rejects_requested_completion_without_human_decision() -> None:
    result = validate_completion_continuity_packet(valid_completion_packet(requested_decision="approve completion"))

    assert result.accepted is False
    assert result.error_code == ErrorCode.MISSING_HUMAN_DECISION
    write_evidence("delivery-feedback/completion-without-human-decision-block.json", result.to_evidence(), slice_id="l1gov-slice-008")


@pytest.mark.parametrize(
    "field_name",
    ("open_risks", "remaining_scope", "continuity_rule_candidate", "owner_ref", "cadence", "review_criteria", "stop_conditions"),
)
def test_completion_packet_rejects_incomplete_continuity_rules(field_name: str) -> None:
    result = validate_completion_continuity_packet(
        valid_completion_packet(
            **{
                field_name: ()
                if field_name in ("open_risks", "review_criteria", "stop_conditions")
                else ""
            }
        )
    )

    assert result.accepted is False
    assert result.error_code == ErrorCode.DELIVERY_FEEDBACK_RECORD_INVALID
    assert field_name in result.missing_fields
