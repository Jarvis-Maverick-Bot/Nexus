from __future__ import annotations

from nexus.governance.schemas import ActorRef, CommandEnvelope


SERVICE_SOURCE_REFS = (
    "WBS V0.6",
    "L1.11.9",
    "a8aae37032502800778f02c7defc0dce5d1231fd",
)


def service_actor() -> ActorRef:
    return ActorRef(actor_id="agent:thunder", role="implementation")


def service_command(
    command_type: str = "SubmitCommandDraft",
    *,
    expected_version: int | bool | None = 0,
    idempotency_key: str | None = "svc-cmd-001",
    payload: dict[str, object] | None = None,
    affects_state: bool = True,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type=command_type,
        actor=service_actor(),
        authority_refs=SERVICE_SOURCE_REFS,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        payload={
            "source_refs": SERVICE_SOURCE_REFS,
            "target_ref": "layer1-governance",
            "expected_state": "completion_continuity_review_requested",
            "expected_version": expected_version,
            "idempotency_key": idempotency_key,
            "authorization_source": "Nova-approved-baseline",
            **(payload or {}),
        },
        affects_state=affects_state,
        command_id="svc-cmd-001",
        target_ref="layer1-governance",
        expected_state="completion_continuity_review_requested",
        source_refs=SERVICE_SOURCE_REFS,
        authorization_source="Nova-approved-baseline",
    )
