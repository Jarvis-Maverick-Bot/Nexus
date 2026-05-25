"""Resident controller evidence package builder."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import hashlib
import json

from nexus.mq.agent_registry_events import secret_material_errors


@dataclass
class ResidentEvidenceRecord:
    sequence: int
    record_type: str
    event_time: str
    payload: dict[str, Any]
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvidencePackageResult:
    review_ready: bool
    manifest_path: Path
    checksum_path: Path
    secret_scan_path: Path
    errors: list[str] = field(default_factory=list)
    checksums: dict[str, str] = field(default_factory=dict)
    not_business_completion: bool = True


def build_evidence_package(
    *,
    run_id: str,
    evidence_root: Path,
    records: list[ResidentEvidenceRecord],
    status_summary: dict[str, Any],
) -> EvidencePackageResult:
    evidence_root.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    if not records:
        errors.append("MISSING_RAW_EVIDENCE_RECORDS")
    secret_errors: list[str] = []
    for record in records:
        secret_errors.extend(secret_material_errors(record.to_dict(), path=f"records[{record.sequence}]"))
    secret_errors.extend(secret_material_errors(status_summary, path="status_summary"))
    errors.extend(secret_errors)

    events_path = evidence_root / "events.jsonl"
    status_path = evidence_root / "status_after.json"
    manifest_path = evidence_root / "manifest.json"
    checksum_path = evidence_root / "SHA256SUMS"
    secret_scan_path = evidence_root / "secret_scan.txt"
    verdict_path = evidence_root / "verdict_report.md"

    _write_jsonl(events_path, [record.to_dict() for record in records])
    _write_json(status_path, status_summary)
    secret_scan_path.write_text("\n".join(secret_errors) if secret_errors else "NO_HIGH_CONFIDENCE_SECRET_FINDINGS\n", encoding="utf-8")
    verdict_path.write_text(
        "# Resident Controller Evidence Package\n\n"
        f"Run: {run_id}\n\n"
        f"Review ready: {not errors}\n\n"
        "not_business_completion: true\n",
        encoding="utf-8",
    )
    checksums = {
        "events.jsonl": _sha256_ref(events_path),
        "status_after.json": _sha256_ref(status_path),
        "secret_scan.txt": _sha256_ref(secret_scan_path),
        "verdict_report.md": _sha256_ref(verdict_path),
    }
    manifest = {
        "schema_version": "4.19.resident_controller.evidence_manifest.v1",
        "run_id": run_id,
        "record_count": len(records),
        "review_ready": not errors,
        "errors": _dedupe(errors),
        "checksums": checksums,
        "not_business_completion": True,
    }
    _write_json(manifest_path, manifest)
    checksums["manifest.json"] = _sha256_ref(manifest_path)
    checksum_path.write_text(
        "".join(f"{digest}  {filename}\n" for filename, digest in sorted(checksums.items())),
        encoding="utf-8",
    )
    return EvidencePackageResult(
        review_ready=not errors,
        manifest_path=manifest_path,
        checksum_path=checksum_path,
        secret_scan_path=secret_scan_path,
        errors=_dedupe(errors),
        checksums=checksums,
    )


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _sha256_ref(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error and error not in deduped:
            deduped.append(error)
    return deduped
