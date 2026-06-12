from __future__ import annotations

from nexus.governance.errors import ErrorCode, REQUIRED_ERROR_CODES
from nexus.governance.schemas import ActorRef, CommandEnvelope, validate_command_envelope

from ._evidence import write_evidence


def actor() -> ActorRef:
    return ActorRef(actor_id="alex", role="decision_authority")


def test_state_command_requires_expected_version() -> None:
    command = CommandEnvelope(
        command_type="InitializeAuthority",
        actor=actor(),
        authority_refs=("WBS V0.6",),
        expected_version=None,
        idempotency_key="cmd-001",
        payload={"target_state": "authority_initialized"},
        affects_state=True,
    )

    result = validate_command_envelope(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.STALE_EXPECTED_VERSION
    write_evidence("schema/common-schema.json", {"state_command_requires_expected_version": True})


def test_state_command_requires_idempotency_key() -> None:
    command = CommandEnvelope(
        command_type="InitializeAuthority",
        actor=actor(),
        authority_refs=("WBS V0.6",),
        expected_version=0,
        idempotency_key=None,
        payload={"target_state": "authority_initialized"},
        affects_state=True,
    )

    result = validate_command_envelope(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.MISSING_IDEMPOTENCY_KEY


def test_read_command_allows_missing_expected_version() -> None:
    command = CommandEnvelope(
        command_type="RefreshProjection",
        actor=actor(),
        authority_refs=("WBS V0.6",),
        expected_version=None,
        idempotency_key=None,
        payload={"projection_type": "mission_control"},
        affects_state=False,
    )

    result = validate_command_envelope(command)

    assert result.accepted is True
    assert result.error_code is None


def test_error_catalog_contains_required_no_go_errors() -> None:
    required = {code.value for code in REQUIRED_ERROR_CODES}

    assert "ERR_STALE_SOURCE_AUTHORITY" in required
    assert "ERR_STALE_EXPECTED_VERSION" in required
    assert "ERR_MISSING_HUMAN_DECISION" in required
    assert "ERR_MISSING_EVALUATION_PROFILE" in required
    assert "ERR_NO_GO_BOUNDARY" in required
    assert "ERR_ACK_NOT_ACCEPTANCE" in required
    assert "ERR_RAW_FEEDBACK_NO_AUTHORITY_MUTATION" in required
