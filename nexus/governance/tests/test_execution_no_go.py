from __future__ import annotations

import pytest

from nexus.governance.no_go import NoGoBoundaryPolicy

from ._evidence import write_evidence


@pytest.mark.parametrize(
    ("action", "evidence_name"),
    (
        ("execution_direct_419_controller_call", "direct-419-controller-block"),
        ("execution_workpacket_dispatch", "workpacket-dispatch-block"),
        ("execution_dispatch_contract_implementation", "dispatch-contract-implementation-block"),
        ("execution_runtime_live_invocation", "runtime-live-block"),
        ("execution_completion_judgement", "completion-judgement-block"),
    ),
)
def test_execution_no_go_actions_are_blocked(action: str, evidence_name: str) -> None:
    result = NoGoBoundaryPolicy.default().evaluate({"action": action})

    assert result.blocked is True
    assert result.error_code is not None
    write_evidence(f"no-go/{evidence_name}.json", result.to_evidence(), slice_id="l1gov-slice-004")
