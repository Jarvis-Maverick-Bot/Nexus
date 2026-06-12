from __future__ import annotations

from nexus.governance.errors import ErrorCode
from nexus.governance.kernel import GovernanceKernel
from nexus.governance.schemas import ActorRef, CommandEnvelope

from ._evidence import write_evidence


def command(
    command_type: str,
    *,
    expected_version: int = 0,
    key: str = "cmd-001",
    payload: dict[str, object] | None = None,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type=command_type,
        actor=ActorRef(actor_id="alex", role="decision_authority"),
        authority_refs=("WBS V0.6", "f9eaa5b"),
        expected_version=expected_version,
        idempotency_key=key,
        payload=payload or {},
        affects_state=True,
    )


def test_valid_transition_appends_record_and_increments_version() -> None:
    kernel = GovernanceKernel()

    result = kernel.apply(command("InitializeAuthority"))

    assert result.accepted is True
    assert result.new_state.state == "authority_initialized"
    assert result.new_state.version == 1
    assert len(kernel.records) == 1
    write_evidence("kernel/replay-authority.json", result.to_evidence())


def test_illegal_transition_rejects_without_append() -> None:
    kernel = GovernanceKernel()

    result = kernel.apply(command("AcceptIncrement"))

    assert result.accepted is False
    assert result.error_code == ErrorCode.INVALID_TRANSITION
    assert len(kernel.records) == 0


def test_replay_rebuilds_aggregate_state_from_records() -> None:
    kernel = GovernanceKernel()
    kernel.apply(command("InitializeAuthority"))
    kernel.apply(command("MarkKernelReady", expected_version=1, key="cmd-002"))

    rebuilt = GovernanceKernel.replay(kernel.records)

    assert rebuilt.state.state == "kernel_ready"
    assert rebuilt.state.version == 2


def test_stale_expected_version_rejected_without_append() -> None:
    kernel = GovernanceKernel()
    kernel.apply(command("InitializeAuthority"))

    result = kernel.apply(command("MarkKernelReady", expected_version=0, key="cmd-002"))

    assert result.accepted is False
    assert result.error_code == ErrorCode.STALE_EXPECTED_VERSION
    assert len(kernel.records) == 1
    write_evidence("kernel/version-idempotency.json", result.to_evidence())


def test_duplicate_idempotency_key_returns_prior_result_without_duplicate_append() -> None:
    kernel = GovernanceKernel()
    first = kernel.apply(command("InitializeAuthority", key="same-key"))
    second = kernel.apply(command("InitializeAuthority", key="same-key"))

    assert first.accepted is True
    assert second.accepted is True
    assert second.record.record_id == first.record.record_id
    assert len(kernel.records) == 1


def test_idempotency_key_reuse_with_different_body_rejected() -> None:
    kernel = GovernanceKernel()
    kernel.apply(command("InitializeAuthority", key="same-key"))
    result = kernel.apply(command("MarkKernelReady", expected_version=1, key="same-key"))

    assert result.accepted is False
    assert result.error_code == ErrorCode.IDEMPOTENCY_KEY_REUSE
