from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LocalAppViewModel:
    workspace_id: str
    read_only: bool
    workspace_picker_mode: str
    workspace_picker_creates_authority: bool
    disabled_commands: tuple[str, ...]
    freshness_chips: tuple[str, ...]
    framework: str | None = None

    def to_evidence(self) -> dict[str, Any]:
        return {
            "disabled_commands": list(self.disabled_commands),
            "framework": self.framework,
            "freshness_chips": list(self.freshness_chips),
            "read_only": self.read_only,
            "workspace_id": self.workspace_id,
            "workspace_picker_creates_authority": self.workspace_picker_creates_authority,
            "workspace_picker_mode": self.workspace_picker_mode,
        }


def build_read_only_view_model(*, workspace_id: str) -> LocalAppViewModel:
    return LocalAppViewModel(
        workspace_id=workspace_id,
        read_only=True,
        workspace_picker_mode="projection_overlay",
        workspace_picker_creates_authority=False,
        disabled_commands=("approve", "complete", "archive", "baseline", "no_go", "final_pass"),
        freshness_chips=("source", "kernel", "projection"),
        framework=None,
    )
