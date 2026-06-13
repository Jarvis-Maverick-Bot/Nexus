from __future__ import annotations

from dataclasses import replace

from nexus.governance.errors import ErrorCode
from nexus.governance.service_facade import CommandDraft, validate_command_draft, validate_service_command_envelope

from ._evidence import write_evidence
from .fixtures.service_facade import SERVICE_SOURCE_REFS, service_command


def valid_draft(**overrides: object) -> CommandDraft:
    values = {
        "draft_id": "draft-001",
        "command_type": "SubmitCommandDraft",
        "target_ref": "layer1-governance",
        "payload": {"requested_action": "prepare_baseline_entry"},
        "read_only_blocked": False,
        "source_refs": SERVICE_SOURCE_REFS,
        "draft_status": "draft",
        "created_by": "agent:thunder",
    }
    values.update(overrides)
    return CommandDraft(**values)


def test_valid_command_draft_accepts() -> None:
    result = validate_command_draft(valid_draft())

    assert result.accepted is True
    write_evidence("service-facade/command-draft-valid.json", result.to_evidence(), slice_id="l1gov-slice-009")


def test_read_only_command_draft_blocks_state_mutation() -> None:
    result = validate_command_draft(valid_draft(read_only_blocked=True))

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    write_evidence("service-facade/read-only-mutation-block.json", result.to_evidence(), slice_id="l1gov-slice-009")


def test_command_draft_rejects_final_or_production_status() -> None:
    for status in ("approved", "accepted", "complete", "final_pass", "production_ready", "deployed", "active", "closed"):
        result = validate_command_draft(valid_draft(draft_status=status))

        assert result.accepted is False
        assert result.error_code == ErrorCode.NO_GO_BOUNDARY


def test_command_draft_rejects_sentence_shaped_runtime_or_dispatch_intent() -> None:
    for text in (
        "please dispatch now",
        "please activate route now",
        "please execute workpacket now",
        "mark production readiness",
        "complete project",
        "mutate config now",
    ):
        result = validate_command_draft(valid_draft(payload={"operator_note": text}))

        assert result.accepted is False
        assert result.error_code == ErrorCode.NO_GO_BOUNDARY


def test_service_command_envelope_rejects_boolean_expected_version() -> None:
    command = service_command(expected_version=True)

    result = validate_service_command_envelope(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.STALE_EXPECTED_VERSION
    write_evidence("service-facade/boolean-version-reject.json", result.to_evidence(), slice_id="l1gov-slice-009")


def test_service_command_envelope_rejects_payload_version_mismatch() -> None:
    command = service_command(expected_version=2, payload={"expected_version": 1})

    result = validate_service_command_envelope(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.STALE_EXPECTED_VERSION


def test_service_command_envelope_rejects_idempotency_mismatch() -> None:
    command = service_command(payload={"idempotency_key": "different-key"})

    result = validate_service_command_envelope(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.IDEMPOTENCY_KEY_REUSE
    write_evidence("service-facade/idempotency-mismatch-reject.json", result.to_evidence(), slice_id="l1gov-slice-009")


def test_service_command_envelope_requires_nova_authorization_source_for_state_change() -> None:
    command = replace(service_command(), authorization_source=None)
    command.payload["authorization_source"] = ""

    result = validate_service_command_envelope(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.STALE_SOURCE_AUTHORITY
