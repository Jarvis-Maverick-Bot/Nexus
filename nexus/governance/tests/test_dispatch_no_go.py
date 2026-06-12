from __future__ import annotations

import pytest

from nexus.governance.no_go import NoGoBoundaryPolicy

from ._evidence import write_evidence


@pytest.mark.parametrize(
    ("action", "evidence_name"),
    (
        ("dispatch_runtime_live_invocation", "runtime-live-block"),
        ("dispatch_actual_execution", "actual-dispatch-block"),
        ("dispatch_direct_419_controller_call", "direct-419-controller-block"),
        ("dispatch_workpacket_execution", "workpacket-execution-block"),
        ("dispatch_completion_judgement", "completion-judgement-block"),
    ),
)
def test_dispatch_no_go_actions_are_blocked(action: str, evidence_name: str) -> None:
    result = NoGoBoundaryPolicy.default().evaluate({"action": action})

    assert result.blocked is True
    assert result.error_code is not None
    write_evidence(f"no-go/{evidence_name}.json", result.to_evidence(), slice_id="l1gov-slice-005")
