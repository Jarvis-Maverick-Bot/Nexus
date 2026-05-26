"""File-backed evidence writer for Candidate Adapter events."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json

from nexus.mq.agent_registry_events import secret_material_errors
from nexus.mq.candidate_adapter_event_mapper import CandidateAdapterEvent


CANDIDATE_ADAPTER_EVIDENCE_SCHEMA_VERSION = "4.19.candidate_adapter.evidence.v1"


@dataclass
class CandidateAdapterEvidenceWrite:
    accepted: bool
    evidence_ref: str = ""
    path: str = ""
    errors: list[str] | None = None
    not_business_completion: bool = True


class CandidateAdapterEvidenceWriter:
    def __init__(self, evidence_root: str | Path):
        self.evidence_root = Path(evidence_root)

    def write_event(self, event: CandidateAdapterEvent) -> CandidateAdapterEvidenceWrite:
        payload = {
            "schema_version": CANDIDATE_ADAPTER_EVIDENCE_SCHEMA_VERSION,
            "event": event.to_dict(),
            "not_business_completion": True,
        }
        errors = secret_material_errors(payload, path="candidate_adapter_evidence")
        if errors:
            return CandidateAdapterEvidenceWrite(False, errors=errors)
        encoded = json.dumps(payload, sort_keys=True, indent=2).encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()[:16]
        filename = f"{event.event_type}-{digest}.json"
        self.evidence_root.mkdir(parents=True, exist_ok=True)
        path = self.evidence_root / filename
        path.write_bytes(encoded + b"\n")
        return CandidateAdapterEvidenceWrite(
            True,
            evidence_ref=f"evidence://candidate-adapter/{filename}",
            path=str(path),
            errors=[],
        )
