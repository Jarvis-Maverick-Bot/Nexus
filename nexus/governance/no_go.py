from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ErrorCode


@dataclass(frozen=True)
class NoGoResult:
    blocked: bool
    error_code: ErrorCode | None = None
    category: str | None = None
    message: str = ""

    def to_evidence(self) -> dict[str, Any]:
        return {
            "blocked": self.blocked,
            "category": self.category,
            "error_code": self.error_code.value if self.error_code else None,
            "message": self.message,
        }


@dataclass(frozen=True)
class NoGoBoundaryPolicy:
    blocked_actions: dict[str, ErrorCode]

    @classmethod
    def default(cls) -> "NoGoBoundaryPolicy":
        return cls(
            blocked_actions={
                "coding_without_authorization": ErrorCode.NO_GO_BOUNDARY,
                "runtime_live_invocation": ErrorCode.NO_GO_BOUNDARY,
                "implementation_dispatch": ErrorCode.NO_GO_BOUNDARY,
                "deploy": ErrorCode.NO_GO_BOUNDARY,
                "config_mutation": ErrorCode.NO_GO_BOUNDARY,
                "credential_mutation": ErrorCode.NO_GO_BOUNDARY,
                "lower_layer_runtime_control": ErrorCode.NO_GO_BOUNDARY,
                "direct_ui_approval": ErrorCode.NO_GO_BOUNDARY,
                "canonical_promotion": ErrorCode.NO_GO_BOUNDARY,
                "production_readiness": ErrorCode.NO_GO_BOUNDARY,
                "final_pass": ErrorCode.NO_GO_BOUNDARY,
                "ack_as_acceptance": ErrorCode.ACK_NOT_ACCEPTANCE,
                "raw_feedback_authority_mutation": ErrorCode.RAW_FEEDBACK_NO_AUTHORITY_MUTATION,
                "accept_without_evaluation_profile": ErrorCode.MISSING_EVALUATION_PROFILE,
            }
        )

    def evaluate(self, intent: dict[str, Any] | None) -> NoGoResult:
        action = str((intent or {}).get("action", "")).strip()
        if not action:
            return NoGoResult(False)
        error_code = self.blocked_actions.get(action)
        if error_code is None:
            return NoGoResult(False)
        return NoGoResult(
            True,
            error_code=error_code,
            category=action,
            message=f"blocked by Slice 001 no-go boundary: {action}",
        )
