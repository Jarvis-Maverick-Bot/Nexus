from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .errors import ErrorCode


@dataclass(frozen=True)
class ActorRef:
    actor_id: str
    role: str


@dataclass(frozen=True)
class CommandEnvelope:
    command_type: str
    actor: ActorRef
    authority_refs: tuple[str, ...]
    expected_version: int | None
    idempotency_key: str | None
    payload: dict[str, Any] = field(default_factory=dict)
    affects_state: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass(frozen=True)
class ValidationResult:
    accepted: bool
    error_code: ErrorCode | None = None
    message: str = ""

    def to_evidence(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "error_code": self.error_code.value if self.error_code else None,
            "message": self.message,
        }


@dataclass(frozen=True)
class CommandResponse:
    accepted: bool
    error_code: ErrorCode | None = None
    aggregate_ref: str | None = None
    record_ref: str | None = None
    projection_ref: str | None = None
    retryable: bool = False
    evidence_refs: tuple[str, ...] = ()
    message: str = ""

    def to_evidence(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "aggregate_ref": self.aggregate_ref,
            "error_code": self.error_code.value if self.error_code else None,
            "evidence_refs": list(self.evidence_refs),
            "message": self.message,
            "projection_ref": self.projection_ref,
            "record_ref": self.record_ref,
            "retryable": self.retryable,
        }


def validate_command_envelope(command: CommandEnvelope) -> ValidationResult:
    if not command.command_type:
        return ValidationResult(False, ErrorCode.INVALID_TRANSITION, "command_type is required")
    if not command.authority_refs:
        return ValidationResult(False, ErrorCode.STALE_SOURCE_AUTHORITY, "authority_refs are required")
    if command.affects_state and command.expected_version is None:
        return ValidationResult(
            False,
            ErrorCode.STALE_EXPECTED_VERSION,
            "state-affecting commands require expected_version",
        )
    if command.affects_state and not command.idempotency_key:
        return ValidationResult(
            False,
            ErrorCode.MISSING_IDEMPOTENCY_KEY,
            "state-affecting commands require idempotency_key",
        )
    return ValidationResult(True)
