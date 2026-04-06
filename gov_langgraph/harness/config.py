"""
harness.config — V1 Harness Configuration

Minimal settings for V1 checkpoint and state persistence.
Paths, thresholds, and operational parameters.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Default Paths
# ---------------------------------------------------------------------------

DEFAULT_STATE_DIR = Path("~/.gov_langgraph/state").expanduser()
DEFAULT_EVENT_DIR = Path("~/.gov_langgraph/events").expanduser()
DEFAULT_CHECKPOINT_DIR = Path("~/.gov_langgraph/checkpoints").expanduser()


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class HarnessConfig:
    """
    V1 Harness configuration.

    All paths are configurable so the harness can run in different
    environments without code changes.
    """

    # Directory for WorkItem / TaskState snapshot files
    state_dir: Path = DEFAULT_STATE_DIR

    # Directory for append-only event journal files
    event_dir: Path = DEFAULT_EVENT_DIR

    # Directory for checkpoint files (atomic state saves)
    checkpoint_dir: Path = DEFAULT_CHECKPOINT_DIR

    # File naming convention
    project_file_pattern: str = "project_{project_id}.json"
    workitem_file_pattern: str = "workitem_{task_id}.json"
    taskstate_file_pattern: str = "taskstate_{task_id}.json"
    event_file_pattern: str = "events_{project_id}.jsonl"

    # Checkpoint settings
    checkpoint_before_transition: bool = True  # Save before advancing stage
    checkpoint_after_transition: bool = True   # Save after advancing stage

    # Event journal settings
    event_flush_interval: int = 10  # Flush to disk every N events
    event_file_max_lines: int = 10000  # Rotate event file after this many lines

    # Paths to create on init
    _auto_init_dirs: list[str] = field(
        default_factory=lambda: ["state_dir", "event_dir", "checkpoint_dir"]
    )

    def ensure_dirs(self) -> None:
        """Create all configured directories if they don't exist."""
        for attr in self._auto_init_dirs:
            path = getattr(self, attr, None)
            if path is not None:
                path.mkdir(parents=True, exist_ok=True)

    def resolve_path(self, file_pattern: str, **kwargs: str) -> Path:
        """
        Resolve a file pattern to an actual path.

        Example:
            config.resolve_path(config.project_file_pattern, project_id="abc")
        """
        filename = file_pattern.format(**kwargs)
        # Determine which dir this belongs to
        if "project" in file_pattern:
            base = self.state_dir
        elif "taskstate" in file_pattern:
            base = self.state_dir
        elif "workitem" in file_pattern:
            base = self.state_dir
        elif "event" in file_pattern:
            base = self.event_dir
        else:
            base = self.state_dir
        return base / filename


# ---------------------------------------------------------------------------
# Global Default Config
# ---------------------------------------------------------------------------

_default_config: HarnessConfig | None = None


def get_default_config() -> HarnessConfig:
    """Get or create the global default config."""
    global _default_config
    if _default_config is None:
        _default_config = HarnessConfig()
        _default_config.ensure_dirs()
    return _default_config
