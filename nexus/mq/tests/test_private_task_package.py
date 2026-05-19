from dataclasses import replace

from nexus.mq.private_context_policy import PrivatePackageInput
from nexus.mq.private_task_package import (
    PrivateTaskPackageRequest,
    build_private_task_package,
    validate_private_task_package,
)
from nexus.mq.tests.test_private_agent_contract import NOW, _contract


def _input(**overrides):
    data = {
        "ref": "excerpt://task/diagnostic",
        "classification": "redacted",
        "hash": "sha256:input",
        "context_class": "diagnostic_metadata",
        "redaction_manifest_ref": "redaction://task/diagnostic",
        "privacy_scope": "project",
    }
    data.update(overrides)
    return PrivatePackageInput(**data)


def _request(**overrides):
    data = {
        "task_package_id": "pkg-private-diagnostic",
        "assignment_id": "assign-private-diagnostic",
        "contract_id": "contract-private-diagnostic",
        "contract_revision": 1,
        "task_kind": "diagnostic",
        "objective": "Return a deterministic diagnostic echo.",
        "allowed_inputs": [_input()],
        "forbidden_actions": ["no repo writes", "no credential access", "no business execution"],
        "allowed_outputs": ["diagnostic_echo", "command_log"],
        "evidence_required": ["evidence://private-agent/diagnostic-log"],
        "timeout_policy_ref": "timeout://private-agent/diagnostic",
        "no_go_conditions": ["no private-agent business completion", "no broad context"],
    }
    data.update(overrides)
    return PrivateTaskPackageRequest(**data)


def _package():
    result = build_private_task_package(_contract(), _request(), now_at=NOW)
    assert result.accepted is True
    return result.package


def test_private_task_package_records_redaction_manifest_and_hash():
    package = _package()

    assert package.package_hash.startswith("sha256:")
    assert package.redaction_manifest_ref == "redaction-manifest://pkg-private-diagnostic"
    assert package.redaction_manifest["entries"][0]["hash"] == "sha256:input"
    assert package.not_business_completion is True
    assert package.task_kind == "diagnostic"


def test_private_task_package_rejects_forbidden_context_before_invocation():
    result = build_private_task_package(
        _contract(),
        _request(allowed_inputs=[_input(context_class="live_credentials")]),
        now_at=NOW,
    )

    assert result.accepted is False
    assert "PRIVATE_FORBIDDEN_CONTEXT_BLOCKED: live_credentials" in result.errors


def test_private_task_package_rejects_missing_redaction_manifest_and_hash():
    result = build_private_task_package(
        _contract(),
        _request(allowed_inputs=[_input(hash="", redaction_manifest_ref="")]),
        now_at=NOW,
    )

    assert result.accepted is False
    assert "PRIVATE_INPUT_HASH_REQUIRED" in result.errors
    assert "PRIVATE_REDACTION_MANIFEST_REQUIRED" in result.errors


def test_private_task_package_rejects_non_diagnostic_task_kind():
    result = build_private_task_package(
        _contract(max_task_package_classification="non_business_probe"),
        _request(task_kind="non_business_probe"),
        now_at=NOW,
    )

    assert result.accepted is False
    assert "PRIVATE_DIAGNOSTIC_ONLY" in result.errors


def test_private_task_package_hash_is_verified():
    package = replace(_package(), package_hash="sha256:tampered")

    errors = validate_private_task_package(package, contract=_contract(), now_at=NOW)

    assert "PRIVATE_TASK_PACKAGE_HASH_MISMATCH" in errors


def test_private_task_package_expired_fails_closed():
    package = _package()

    errors = validate_private_task_package(package, contract=_contract(), now_at="2026-05-19T00:06:00+00:00")

    assert "PRIVATE_TASK_PACKAGE_EXPIRED" in errors
