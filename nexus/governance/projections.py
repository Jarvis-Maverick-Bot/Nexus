from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class FreshnessState(StrEnum):
    CURRENT = "current"
    REBUILDING = "rebuilding"
    FAILED = "failed"
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
    read_only: bool = True
    rebuild_reason: str = ""
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


def build_projection_snapshot(
    *,
    projection_type: str,
    workspace_id: str,
    source_checkpoint: str,
    payload: dict[str, Any],
    authority_refs: tuple[str, ...],
    generated_at: str | None = None,
) -> ProjectionSnapshot:
    return ProjectionSnapshot(
        projection_id=f"{workspace_id}:{projection_type}:{source_checkpoint}",
        projection_type=projection_type,
        workspace_id=workspace_id,
        source_checkpoint=source_checkpoint,
        freshness=FreshnessState.CURRENT,
        payload=dict(payload),
        authority_refs=tuple(authority_refs),
        read_only=True,
        generated_at=generated_at or datetime.now(UTC).isoformat(),
    )


def mark_projection_stale(snapshot: ProjectionSnapshot, *, reason: str = "source checkpoint changed") -> ProjectionSnapshot:
    return ProjectionSnapshot(
        projection_id=snapshot.projection_id,
        projection_type=snapshot.projection_type,
        workspace_id=snapshot.workspace_id,
        source_checkpoint=snapshot.source_checkpoint,
        freshness=FreshnessState.STALE,
        payload=dict(snapshot.payload),
        authority_refs=tuple(snapshot.authority_refs),
        read_only=True,
        rebuild_reason=reason,
        generated_at=snapshot.generated_at,
    )


def rebuild_projection_snapshot(
    snapshot: ProjectionSnapshot,
    *,
    latest_source_checkpoint: str,
    payload: dict[str, Any],
    generated_at: str | None = None,
) -> ProjectionSnapshot:
    return build_projection_snapshot(
        projection_type=snapshot.projection_type,
        workspace_id=snapshot.workspace_id,
        source_checkpoint=latest_source_checkpoint,
        payload=payload,
        authority_refs=tuple(snapshot.authority_refs),
        generated_at=generated_at,
    )


def failed_projection_snapshot(
    *,
    projection_type: str,
    workspace_id: str,
    source_checkpoint: str,
    authority_refs: tuple[str, ...],
    reason: str,
    generated_at: str | None = None,
) -> ProjectionSnapshot:
    return ProjectionSnapshot(
        projection_id=f"{workspace_id}:{projection_type}:{source_checkpoint}",
        projection_type=projection_type,
        workspace_id=workspace_id,
        source_checkpoint=source_checkpoint,
        freshness=FreshnessState.FAILED,
        payload={},
        authority_refs=tuple(authority_refs),
        read_only=True,
        rebuild_reason=reason,
        generated_at=generated_at or datetime.now(UTC).isoformat(),
    )
