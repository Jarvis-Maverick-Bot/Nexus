from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class FreshnessState(StrEnum):
    FRESH = "fresh"
    STALE = "stale"


@dataclass(frozen=True)
class ProjectionSnapshot:
    projection_id: str
    projection_type: str
    workspace_id: str
    source_checkpoint: str
    freshness: FreshnessState
    payload: dict[str, Any]
    authority_refs: tuple[str, ...]
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def is_stale(self) -> bool:
        return self.freshness == FreshnessState.STALE

    @property
    def is_canonical_state(self) -> bool:
        return False

    def to_evidence(self) -> dict[str, Any]:
        return {
            "authority_refs": list(self.authority_refs),
            "freshness": self.freshness.value,
            "generated_at": self.generated_at,
            "is_canonical_state": self.is_canonical_state,
            "payload": self.payload,
            "projection_id": self.projection_id,
            "projection_type": self.projection_type,
            "source_checkpoint": self.source_checkpoint,
            "workspace_id": self.workspace_id,
        }


def build_projection(
    *,
    projection_type: str,
    workspace_id: str,
    source_checkpoint: str,
    payload: dict[str, Any],
    authority_refs: tuple[str, ...],
    generated_at: str | None = None,
) -> ProjectionSnapshot:
    projection_id = f"{workspace_id}:{projection_type}:{source_checkpoint}"
    return ProjectionSnapshot(
        projection_id=projection_id,
        projection_type=projection_type,
        workspace_id=workspace_id,
        source_checkpoint=source_checkpoint,
        freshness=FreshnessState.FRESH,
        payload=dict(payload),
        authority_refs=tuple(authority_refs),
        generated_at=generated_at or datetime.now(UTC).isoformat(),
    )
