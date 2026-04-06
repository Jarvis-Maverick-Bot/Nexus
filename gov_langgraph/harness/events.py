"""
harness.events — Layer 3: Append-Only Event Journal

Append-only event journal for governance audit trail.
Records governance-relevant actions, changes, and conditions.

Layer 3 is NOT mutable state — events are append-only.
Layer 3 is for: audit, replay, provenance.

Governance meaning of events is owned by Platform Core Event object.
This module handles persistence only.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from gov_langgraph.platform_model import Event as PlatformEvent


# ---------------------------------------------------------------------------
# EventJournal
# ---------------------------------------------------------------------------


class EventJournal:
    """
    Append-only event journal.

    Events are written to a JSON lines (.jsonl) file, one event per line.
    Files are organized per project.

    Directory structure:
        event_dir/
            events_{project_id}.jsonl

    Layer 3 rules:
        - Append only — never modify or delete
        - One event per line — easy to stream
        - File rotation when max lines reached
    """

    def __init__(
        self,
        event_dir: Path | str,
        max_lines_per_file: int = 10000,
    ):
        self.event_dir = Path(event_dir)
        self.event_dir.mkdir(parents=True, exist_ok=True)
        self.max_lines_per_file = max_lines_per_file

    def _journal_path(self, project_id: str) -> Path:
        return self.event_dir / f"events_{project_id}.jsonl"

    # --- Append ---

    def append(self, event: PlatformEvent) -> None:
        """
        Append an event to the project's journal.

        This is append-only. Events are never modified or deleted.
        """
        path = self._journal_path(event.project_id)

        # Serialize event to dict
        data = {
            "event_id": event.event_id,
            "project_id": event.project_id,
            "task_id": event.task_id,
            "event_type": event.event_type,
            "actor": event.actor,
            "event_summary": event.event_summary,
            "related_stage": event.related_stage,
            "timestamp": event.timestamp.isoformat(),
        }

        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=2) + "\n")

    def append_raw(
        self,
        project_id: str,
        event_type: str,
        event_summary: str,
        actor: str,
        task_id: str | None = None,
        related_stage: str | None = None,
    ) -> PlatformEvent:
        """
        Create and append a raw event without a full PlatformEvent instance.

        Convenience method for direct journal writes.
        """
        event = PlatformEvent(
            project_id=project_id,
            event_type=event_type,
            event_summary=event_summary,
            actor=actor,
            task_id=task_id,
            related_stage=related_stage,
        )
        self.append(event)
        return event

    # --- Query (read-only) ---

    def get_for_project(
        self,
        project_id: str,
        limit: int | None = None,
        after: datetime | None = None,
    ) -> list[PlatformEvent]:
        """
        Load events for a project, optionally filtered and limited.

        Events are returned in reverse chronological order (newest first).
        """
        path = self._journal_path(project_id)
        if not path.exists():
            return []

        events = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    ts = datetime.fromisoformat(data["timestamp"])
                    if after and ts <= after:
                        continue
                    events.append(PlatformEvent(
                        event_id=data["event_id"],
                        project_id=data["project_id"],
                        task_id=data.get("task_id"),
                        event_type=data["event_type"],
                        actor=data["actor"],
                        event_summary=data["event_summary"],
                        related_stage=data.get("related_stage"),
                        timestamp=ts,
                    ))
                except Exception:
                    continue

        events.sort(key=lambda e: e.timestamp, reverse=True)

        if limit:
            events = events[:limit]

        return events

    def get_for_task(
        self,
        task_id: str,
        project_id: str,
        limit: int | None = None,
    ) -> list[PlatformEvent]:
        """
        Load events for a specific task within a project.
        """
        all_events = self.get_for_project(project_id)
        task_events = [e for e in all_events if e.task_id == task_id]
        if limit:
            task_events = task_events[:limit]
        return task_events

    def iter_for_project(self, project_id: str) -> Iterator[PlatformEvent]:
        """
        Iterate over all events for a project in chronological order.

        Memory-efficient: reads line by line without loading all into memory.
        """
        path = self._journal_path(project_id)
        if not path.exists():
            return

        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    yield PlatformEvent(
                        event_id=data["event_id"],
                        project_id=data["project_id"],
                        task_id=data.get("task_id"),
                        event_type=data["event_type"],
                        actor=data["actor"],
                        event_summary=data["event_summary"],
                        related_stage=data.get("related_stage"),
                        timestamp=datetime.fromisoformat(data["timestamp"]),
                    )
                except Exception:
                    continue

    # --- Stats ---

    def count_for_project(self, project_id: str) -> int:
        """Count total events for a project."""
        path = self._journal_path(project_id)
        if not path.exists():
            return 0
        with path.open(encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())

    def count_for_task(self, task_id: str, project_id: str) -> int:
        """Count total events for a specific task."""
        return len(self.get_for_task(task_id, project_id))
