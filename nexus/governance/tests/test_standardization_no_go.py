from __future__ import annotations

import pytest

from nexus.governance.no_go import NoGoBoundaryPolicy

from ._evidence import write_evidence


@pytest.mark.parametrize(
    ("action", "evidence_name"),
    (
        ("standardization_approval_bypass", "approval-bypass-block"),
        ("standardization_runtime_dispatch", "runtime-dispatch-block"),
        ("standardization_project_execution_packet_generation", "execution-packet-generation-block"),
        ("standardization_monitor_criteria_invention", "monitor-criteria-invention-block"),
        ("standardization_feedback_policy_bypass", "feedback-policy-bypass-block"),
    ),
)
def test_standardization_no_go_actions_are_blocked(action: str, evidence_name: str) -> None:
    result = NoGoBoundaryPolicy.default().evaluate({"action": action})

    assert result.blocked is True
    assert result.error_code is not None
    write_evidence(f"no-go/{evidence_name}.json", result.to_evidence(), slice_id="l1gov-slice-003")
