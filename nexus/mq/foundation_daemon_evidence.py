"""File-backed source evidence helpers for the MQ foundation daemon."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json


class FoundationEvidenceRecorder:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.available = True

    def write_record(self, family: str, name: str, payload: dict[str, Any]) -> str:
        if not self.available:
            raise RuntimeError("EVIDENCE_STORE_UNAVAILABLE")
        directory = self.root / family
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{name}.json"
        data = dict(payload)
        data["not_business_completion"] = True
        path.write_text(json.dumps(data, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8")
        return path.as_posix()

    def build_manifest(self) -> dict[str, Any]:
        files = sorted(path for path in self.root.rglob("*") if path.is_file())
        entries = []
        for path in files:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            entries.append({"path": path.as_posix(), "sha256": digest})
        return {"entries": entries, "not_business_completion": True}
