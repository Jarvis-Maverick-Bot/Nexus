from dataclasses import replace

from nexus.mq.private_invocation_allowlist import PrivateInvocationRequest
from nexus.mq.private_invocation_runner import PreparedDiagnosticResult, run_private_diagnostic_invocation
from nexus.mq.private_result_candidate import PrivateResultOutput
from nexus.mq.tests.test_private_agent_contract import NOW, _contract
from nexus.mq.tests.test_private_task_package import _package


def _invocation(**overrides):
    data = {
        "invocation_id": "diagnostic-echo",
        "invocation_type": "cli",
        "command_or_endpoint_ref": "cmdref://private-agent/diagnostic-echo",
        "args": {"mode": "diagnostic", "format": "json"},
        "env_refs": ["envref://private-agent/diagnostic-only"],
        "task_package_hash": _package().package_hash,
    }
    data.update(overrides)
    return PrivateInvocationRequest(**data)


def _prepared_result(**overrides):
    data = {
        "result_id": "result-private-diagnostic",
        "status_claim": "success",
        "summary": "diagnostic echo complete",
        "outputs": [PrivateResultOutput("artifact://private-agent/echo", "diagnostic_echo", "sha256:output")],
        "evidence_refs": ["evidence://private-agent/diagnostic-log"],
    }
    data.update(overrides)
    return PreparedDiagnosticResult(**data)


def test_private_contract_diagnostic_dry_run_end_to_end():
    package = _package()
    result = run_private_diagnostic_invocation(
        _contract(),
        package,
        _invocation(task_package_hash=package.package_hash),
        _prepared_result(),
        now_at=NOW,
    )

    assert result.accepted is True
    assert result.invocation_record.business_execution_allowed is False
    assert result.invocation_record.diagnostic_only is True
    assert result.result_candidate.task_package_hash == package.package_hash
    assert result.result_candidate.not_business_completion is True
    assert result.business_state_committed is False


def test_private_diagnostic_dry_run_cannot_perform_business_execution():
    package = replace(_package(), task_kind="bounded_business_candidate")
    result = run_private_diagnostic_invocation(
        _contract(max_task_package_classification="bounded_business_candidate"),
        package,
        _invocation(task_package_hash=package.package_hash),
        _prepared_result(),
        now_at=NOW,
    )

    assert result.accepted is False
    assert "PRIVATE_DIAGNOSTIC_ONLY" in result.errors
    assert result.business_state_committed is False


def test_private_diagnostic_runner_rejects_unallowlisted_invocation_before_result_candidate():
    package = _package()
    result = run_private_diagnostic_invocation(
        _contract(),
        package,
        _invocation(invocation_id="unreviewed-shell", task_package_hash=package.package_hash),
        _prepared_result(),
        now_at=NOW,
    )

    assert result.accepted is False
    assert "PRIVATE_INVOCATION_NOT_ALLOWLISTED" in result.errors
    assert result.result_candidate is None


def test_private_diagnostic_runner_does_not_treat_cli_success_as_completion():
    package = _package()
    result = run_private_diagnostic_invocation(
        _contract(),
        package,
        _invocation(task_package_hash=package.package_hash),
        _prepared_result(status_claim="success"),
        now_at=NOW,
    )

    assert result.accepted is True
    assert result.result_candidate.status_claim == "success"
    assert result.business_state_committed is False
    assert result.not_business_completion is True
