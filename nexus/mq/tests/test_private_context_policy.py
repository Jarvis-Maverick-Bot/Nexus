from nexus.mq.private_context_policy import (
    PrivatePackageInput,
    evaluate_private_context_policy,
    redaction_manifest_for,
)
from nexus.mq.tests.test_private_agent_contract import _contract


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


def test_context_policy_accepts_redacted_bounded_input():
    result = evaluate_private_context_policy(_contract(), [_input()])

    assert result.accepted is True
    assert result.allowed_inputs[0].ref == "excerpt://task/diagnostic"


def test_forbidden_context_blocks_private_package():
    result = evaluate_private_context_policy(
        _contract(),
        [
            _input(context_class="live_credentials"),
            _input(ref="repo://full", context_class="full_repo_checkout"),
            _input(ref="chat://raw", context_class="private_chat_history"),
        ],
    )

    assert result.accepted is False
    assert "PRIVATE_FORBIDDEN_CONTEXT_BLOCKED: live_credentials" in result.errors
    assert "PRIVATE_FORBIDDEN_CONTEXT_BLOCKED: full_repo_checkout" in result.errors
    assert "PRIVATE_FORBIDDEN_CONTEXT_BLOCKED: private_chat_history" in result.errors


def test_redaction_manifest_and_package_hash_inputs_are_required():
    result = evaluate_private_context_policy(
        _contract(),
        [_input(hash="", redaction_manifest_ref="")],
    )

    assert result.accepted is False
    assert "PRIVATE_INPUT_HASH_REQUIRED" in result.errors
    assert "PRIVATE_REDACTION_MANIFEST_REQUIRED" in result.errors


def test_private_agent_over_context_request_fails_closed():
    result = evaluate_private_context_policy(
        _contract(privacy_scope=["project"]),
        [_input(privacy_scope="full_repo")],
    )

    assert result.accepted is False
    assert "PRIVATE_INPUT_PRIVACY_SCOPE_MISMATCH" in result.errors


def test_redaction_manifest_contains_refs_and_no_raw_secret_flags():
    manifest = redaction_manifest_for([_input()])

    assert manifest["entries"][0]["ref"] == "excerpt://task/diagnostic"
    assert manifest["contains_sensitive_material"] is False
    assert manifest["contains_full_repo"] is False
    assert manifest["contains_raw_memory"] is False
    assert manifest["not_business_completion"] is True


def test_credential_like_values_cannot_appear_in_private_package_inputs():
    result = evaluate_private_context_policy(
        _contract(),
        [_input(ref="excerpt://task/token=abc")],
    )

    assert result.accepted is False
    assert any(error.startswith("SECRET_MATERIAL_VALUE") for error in result.errors)
