from __future__ import annotations

import pytest

from nexus.governance.no_go import NoGoBoundaryPolicy

from ._evidence import write_evidence


@pytest.mark.parametrize(
    ("action", "evidence_name"),
    (
        ("workspace_init_planning_content", "planning-content-out-of-scope"),
        ("workspace_init_approval_bypass", "approval-bypass-block"),
        ("workspace_init_runtime_dispatch", "runtime-dispatch-block"),
        ("shared_docs_mutation", "shared-docs-mutation-block"),
    ),
)
def test_workspace_init_no_go_actions_are_blocked(action: str, evidence_name: str) -> None:
    result = NoGoBoundaryPolicy.default().evaluate({"action": action})

    assert result.blocked is True
    assert result.error_code is not None
    payload = result.to_evidence()
    payload["planning_terms_preserved"] = [
        "scope_baseline",
        "wbs_backlog",
        "risk_register",
        "dependency_map",
        "execution_plan_candidate",
    ]
    write_evidence(f"no-go/{evidence_name}.json", payload, slice_id="l1gov-slice-002")
