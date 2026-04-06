"""
harness.evidence — Evidence Reference Persistence

Stores evidence artifact references (file paths, test results, review outputs).
This is Harness responsibility: persistence and retrieval of evidence.

Governance meaning of evidence is owned by Gate/Event — not here.

Evidence types supported:
- test_result: path to test output file
- review_artifact: path to review document
- execution_log: command output or execution trace
- deliverable: path to a deliverable file
- checkpoint_ref: reference to a previous checkpoint
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Evidence Type
# ---------------------------------------------------------------------------


class EvidenceType(str, Enum):
    """Categories of evidence artifacts."""
    TEST_RESULT = "test_result"
    REVIEW_ARTIFACT = "review_artifact"
    EXECUTION_LOG = "execution_log"
    DELIVERABLE = "deliverable"
    CHECKPOINT_REF = "checkpoint_ref"
    COMMAND_OUTPUT = "command_output"
    SCREENSHOT = "screenshot"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Evidence Record
# ---------------------------------------------------------------------------


@dataclass
class EvidenceRecord:
    """
    Reference to an evidence artifact.

    Note: This stores a REFERENCE to evidence, not the evidence itself.
    The actual artifact lives at the path or URL specified.

    Harness responsibility: persist, retrieve, link
    Governance meaning: owned by Gate/Event
    """

    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    evidence_type: EvidenceType = EvidenceType.OTHER
    task_id: str = ""
    project_id: str = ""

    # Reference
    path: str = ""  # file path or URL
    description: str = ""

    # Metadata
    actor_role: str = ""  # who generated this evidence
    recorded_at: datetime = field(default_factory=datetime.utcnow)
    tags: list[str] = field(default_factory=list)

    # Governance linkage
    linked_gate_id: Optional[str] = None
    linked_event_id: Optional[str] = None
    linked_checkpoint_id: Optional[str] = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["evidence_type"] = self.evidence_type.value
        data["recorded_at"] = self.recorded_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> EvidenceRecord:
        data = dict(data)
        data["evidence_type"] = EvidenceType(data.get("evidence_type", "other"))
        if isinstance(data.get("recorded_at"), str):
            data["recorded_at"] = datetime.fromisoformat(data["recorded_at"])
        return cls(**data)


# ---------------------------------------------------------------------------
# Evidence Store
# ---------------------------------------------------------------------------


class EvidenceStore:
    """
    Persists and retrieves EvidenceRecord objects.

    Files are stored as JSON lines (.jsonl) per project, or per task.
    This allows append-only writes without rewriting large files.

    Directory structure:
        evidence_dir/
            evidence_{project_id}.jsonl
            evidence_{task_id}.jsonl
    """

    def __init__(self, evidence_dir: Path | str):
        self.evidence_dir = Path(evidence_dir)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    def _file_path(self, key: str, by: str = "project") -> Path:
        return self.evidence_dir / f"evidence_{by}_{key}.jsonl"

    # --- Append (append-only) ---

    def append(self, record: EvidenceRecord) -> None:
        """
        Append an evidence record to the appropriate .jsonl file.
        """
        if record.task_id:
            path = self._file_path(record.task_id, by="task")
            path.open("a", encoding="utf-8").write(
                json.dumps(record.to_dict(), indent=2) + "\n"
            )
        elif record.project_id:
            path = self._file_path(record.project_id, by="project")
            path.open("a", encoding="utf-8").write(
                json.dumps(record.to_dict(), indent=2) + "\n"
            )
        else:
            raise ValueError("EvidenceRecord must have either task_id or project_id")

    def append_test_result(
        self,
        task_id: str,
        project_id: str,
        path: str,
        description: str = "",
        actor_role: str = "",
        tags: list[str] | None = None,
    ) -> EvidenceRecord:
        """Convenience: append a test result evidence record."""
        record = EvidenceRecord(
            evidence_type=EvidenceType.TEST_RESULT,
            task_id=task_id,
            project_id=project_id,
            path=path,
            description=description,
            actor_role=actor_role,
            tags=tags or [],
        )
        self.append(record)
        return record

    def append_review_artifact(
        self,
        task_id: str,
        project_id: str,
        path: str,
        description: str = "",
        actor_role: str = "",
        tags: list[str] | None = None,
    ) -> EvidenceRecord:
        """Convenience: append a review artifact evidence record."""
        record = EvidenceRecord(
            evidence_type=EvidenceType.REVIEW_ARTIFACT,
            task_id=task_id,
            project_id=project_id,
            path=path,
            description=description,
            actor_role=actor_role,
            tags=tags or [],
        )
        self.append(record)
        return record

    def append_deliverable(
        self,
        task_id: str,
        project_id: str,
        path: str,
        description: str = "",
        actor_role: str = "",
        tags: list[str] | None = None,
    ) -> EvidenceRecord:
        """Convenience: append a deliverable evidence record."""
        record = EvidenceRecord(
            evidence_type=EvidenceType.DELIVERABLE,
            task_id=task_id,
            project_id=project_id,
            path=path,
            description=description,
            actor_role=actor_role,
            tags=tags or [],
        )
        self.append(record)
        return record

    # --- Query ---

    def get_for_task(self, task_id: str) -> list[EvidenceRecord]:
        """Load all evidence records for a task_id."""
        path = self._file_path(task_id, by="task")
        return self._load(path)

    def get_for_project(self, project_id: str) -> list[EvidenceRecord]:
        """Load all evidence records for a project_id."""
        path = self._file_path(project_id, by="project")
        return self._load(path)

    def get_by_type(
        self,
        project_id: str,
        evidence_type: EvidenceType,
    ) -> list[EvidenceRecord]:
        """Get all evidence of a specific type for a project."""
        records = self.get_for_project(project_id)
        return [r for r in records if r.evidence_type == evidence_type]

    def _load(self, path: Path) -> list[EvidenceRecord]:
        if not path.exists():
            return []
        records = []
        for line in path.open(encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    records.append(EvidenceRecord.from_dict(json.loads(line)))
                except Exception:
                    pass
        return records

    # --- Linkage ---

    def link_to_gate(self, evidence_id: str, gate_id: str) -> None:
        """Link an evidence record to a gate decision."""
        # Load all records, update, rewrite
        # This is a full rewrite because .jsonl doesn't support in-place update
        # For high-volume use, consider a database instead
        # For V1 this is acceptable
        pass  # Implement if needed

    def get_linked_to_gate(self, gate_id: str) -> list[EvidenceRecord]:
        """Get all evidence linked to a specific gate."""
        # Would need full scan — implement if needed for V1
        return []
