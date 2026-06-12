from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .errors import ErrorCode
from .kernel import GovernanceKernel
from .no_go import NoGoBoundaryPolicy
from .schemas import CommandEnvelope, CommandResponse, validate_command_envelope
from .source_authority import SourceAuthorityManifest, verify_source_authority
from .workspace_init import WORKSPACE_INIT_COMMAND_TYPES, validate_workspace_init_command


@dataclass
class GovernanceServiceContract:
    source_manifest: SourceAuthorityManifest
    no_go_policy: NoGoBoundaryPolicy
    kernel: GovernanceKernel

    def handle(self, command: CommandEnvelope, intent: dict[str, Any] | None = None) -> CommandResponse:
        source_result = verify_source_authority(self.source_manifest)
        if not source_result.accepted:
            return CommandResponse(
                False,
                error_code=ErrorCode.STALE_SOURCE_AUTHORITY
                if source_result.error_code == ErrorCode.STALE_SOURCE_AUTHORITY.value
                else ErrorCode.NO_GO_BOUNDARY,
                message=source_result.message,
            )

        no_go = self.no_go_policy.evaluate(intent)
        if no_go.blocked:
            return CommandResponse(False, error_code=no_go.error_code, message=no_go.message)

        validation = (
            validate_workspace_init_command(command)
            if command.command_type in WORKSPACE_INIT_COMMAND_TYPES
            else validate_command_envelope(command)
        )
        if not validation.accepted:
            return CommandResponse(False, error_code=validation.error_code, message=validation.message)

        if not command.affects_state:
            return CommandResponse(True, projection_ref=f"projection:{command.payload.get('projection_type', 'unknown')}")

        transition = self.kernel.apply(_kernel_command(command))
        return CommandResponse(
            transition.accepted,
            error_code=transition.error_code,
            aggregate_ref=transition.new_state.aggregate_id,
            record_ref=transition.record.record_id if transition.record else None,
            message=transition.message,
        )


def _kernel_command(command: CommandEnvelope) -> CommandEnvelope:
    if command.command_type == "SubmitWorkspaceInitRecord":
        return replace(command, expected_version=command.payload["expected_kernel_version"])
    return command
