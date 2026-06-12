from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_ROOT = REPO_ROOT / "verification" / "4.21" / "l1gov-slice-001"


def write_evidence(relative_path: str, payload: dict[str, Any]) -> Path:
    target = EVIDENCE_ROOT / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target
