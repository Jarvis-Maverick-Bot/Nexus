from nexus.mq.private_invocation_allowlist import (
    PrivateInvocationRequest,
    validate_private_invocation_allowlist,
)
from nexus.mq.tests.test_private_agent_contract import _contract


def _request(**overrides):
    data = {
        "invocation_id": "diagnostic-echo",
        "invocation_type": "cli",
        "command_or_endpoint_ref": "cmdref://private-agent/diagnostic-echo",
        "args": {"mode": "diagnostic", "format": "json"},
        "env_refs": ["envref://private-agent/diagnostic-only"],
        "task_package_hash": "sha256:abc",
    }
    data.update(overrides)
    return PrivateInvocationRequest(**data)


def test_private_invocation_accepts_declared_diagnostic_command_only():
    result = validate_private_invocation_allowlist(_contract(), _request())

    assert result.accepted is True
    assert result.invocation.invocation_id == "diagnostic-echo"
    assert result.not_business_completion is True


def test_private_invocation_rejects_unallowlisted_command():
    result = validate_private_invocation_allowlist(
        _contract(),
        _request(invocation_id="shell", command_or_endpoint_ref="cmdref://private-agent/shell"),
    )

    assert result.accepted is False
    assert "PRIVATE_INVOCATION_NOT_ALLOWLISTED" in result.errors


def test_private_invocation_rejects_unallowlisted_endpoint():
    result = validate_private_invocation_allowlist(
        _contract(),
        _request(command_or_endpoint_ref="https://example.invalid/unreviewed"),
    )

    assert result.accepted is False
    assert "PRIVATE_INVOCATION_TARGET_NOT_ALLOWLISTED" in result.errors


def test_private_invocation_rejects_unallowlisted_args_and_env():
    result = validate_private_invocation_allowlist(
        _contract(),
        _request(args={"mode": "diagnostic", "format": "xml", "extra": "true"}, env_refs=["envref://token/live"]),
    )

    assert result.accepted is False
    assert "PRIVATE_INVOCATION_ARG_VALUE_NOT_ALLOWLISTED: format" in result.errors
    assert "PRIVATE_INVOCATION_ARG_NOT_ALLOWLISTED: extra" in result.errors
    assert "PRIVATE_INVOCATION_ENV_REF_NOT_ALLOWLISTED: envref://token/live" in result.errors
    assert "PRIVATE_INVOCATION_ENV_REF_FORBIDDEN: envref://token/live" in result.errors


def test_private_invocation_requires_package_hash_before_invocation():
    result = validate_private_invocation_allowlist(_contract(), _request(task_package_hash=""))

    assert result.accepted is False
    assert "PRIVATE_INVOCATION_REQUIRES_TASK_PACKAGE_HASH" in result.errors
