from __future__ import annotations

from nexus.governance.errors import ErrorCode
from nexus.governance.no_go import NoGoBoundaryPolicy

from ._evidence import write_evidence


def test_blocks_runtime_live_invocation_intent() -> None:
    result = NoGoBoundaryPolicy.default().evaluate({"action": "runtime_live_invocation"})

    assert result.blocked is True
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    write_evidence("source/no-go-policy.json", result.to_evidence())


def test_blocks_deploy_config_credential_mutation_intent() -> None:
    policy = NoGoBoundaryPolicy.default()

    for action in ("deploy", "config_mutation", "credential_mutation"):
        result = policy.evaluate({"action": action})
        assert result.blocked is True
        assert result.error_code == ErrorCode.NO_GO_BOUNDARY


def test_blocks_direct_ui_approval_intent() -> None:
    result = NoGoBoundaryPolicy.default().evaluate({"action": "direct_ui_approval"})

    assert result.blocked is True
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY


def test_blocks_ack_as_acceptance_intent() -> None:
    result = NoGoBoundaryPolicy.default().evaluate({"action": "ack_as_acceptance"})

    assert result.blocked is True
    assert result.error_code == ErrorCode.ACK_NOT_ACCEPTANCE
