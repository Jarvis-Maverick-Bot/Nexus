"""
Doctrine Bridge — Runtime Contract Loader
========================================

Purpose: Turn doctrine files (Markdown, SKOS) into runtime contracts.

The gap: system has doctrine files but they don't drive runtime decisions.
This bridge fills that gap by:

1. Loading doctrine files from the SKOS/shared drive structure
2. Parsing them into structured doctrine snapshots
3. Mapping doctrine metadata to StepContract fields (doctrine_loading_set)
4. Making the snapshot available to executors at runtime

How it works:
- At handler initialization, doctrine_loader loads all files in doctrine_loading_set
- Snapshot is passed to executor as context
- Executor judges draft against snapshot (not hardcoded rules)
- Handler uses contract map to determine mandatory output

Files read from:
  \\\\192.168.31.124\\Nova-Jarvis-Shared\\working\\01-projects\\Nexus\\V2.0\\

The V2_0_FOUNDATION.md, V2_0_SCOPE.md, V2_0_PRD.md serve as doctrine source.
"""

import re
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


# ── Shared drive paths ─────────────────────────────────────────────────────────

_SHARED_ROOT = Path(r"\\192.168.31.124\Nova-Jarvis-Shared\working\01-projects\Nexus\V2.0")
_RELEASE_DEFINITION = _SHARED_ROOT / "01-release-definition"


# ── Doctrine name → file path mapping ────────────────────────────────────────

DOCTRINE_PATHS: Dict[str, Path] = {
    "v2_0_foundation_baseline": _RELEASE_DEFINITION / "V2_0_FOUNDATION_V0_2.md",
    "v2_0_scope":               _RELEASE_DEFINITION / "V2_0_SCOPE_V0_2.md",
    "v2_0_prd":                 _RELEASE_DEFINITION / "V2_0_PRD_V0_2.md",
}


# ── Doctrine snapshot ─────────────────────────────────────────────────────────

@dataclass
class DoctrineSnapshot:
    """Structured doctrine context for runtime use."""
    name: str
    content: str
    path: Path
    loaded: bool
    errors: List[str] = field(default_factory=list)


@dataclass
class LoadedDoctrine:
    """Union of all doctrine snapshots for a given loading set."""
    doctrine_snapshot: Dict[str, DoctrineSnapshot]
    doctrine_loaded: bool
    errors: List[str]


def load_doctrine_snapshot(doctrine_loading_set: List[str]) -> LoadedDoctrine:
    """
    Load all doctrine files named in doctrine_loading_set.
    Returns a LoadedDoctrine with all snapshots + success/failure per file.

    Usage:
        result = load_doctrine_snapshot(["v2_0_foundation_baseline", "v2_0_scope", "v2_0_prd"])
        if result.doctrine_loaded:
            snapshot = result.doctrine_snapshot
            # pass snapshot to executor
    """
    errors = []
    doctrine_snapshot = {}

    for name in doctrine_loading_set:
        path = DOCTRINE_PATHS.get(name)
        if not path:
            errors.append(f"no path mapping for doctrine: {name}")
            doctrine_snapshot[name] = DoctrineSnapshot(
                name=name, content="", path=path or Path(), loaded=False, errors=[f"no path mapping"]
            )
            continue

        if not path.exists():
            # Try workspace-relative path as fallback
            workspace_path = Path(__file__).parent.parent.parent / "governance" / "docs" / path.name
            if workspace_path.exists():
                path = workspace_path

        try:
            content = path.read_text(encoding='utf-8')
            doctrine_snapshot[name] = DoctrineSnapshot(
                name=name,
                content=content,
                path=path,
                loaded=True,
                errors=[]
            )
        except FileNotFoundError:
            doctrine_snapshot[name] = DoctrineSnapshot(
                name=name, content="", path=path, loaded=False, errors=[f"file not found: {path}"]
            )
            errors.append(f"file not found: {path}")
        except Exception as e:
            doctrine_snapshot[name] = DoctrineSnapshot(
                name=name, content="", path=path, loaded=False, errors=[str(e)]
            )
            errors.append(f"error loading {name}: {e}")

    doctrine_loaded = all(s.loaded for s in doctrine_snapshot.values())

    return LoadedDoctrine(
        doctrine_snapshot=doctrine_snapshot,
        doctrine_loaded=doctrine_loaded,
        errors=errors
    )


# ── Contract-driven executor helper ────────────────────────────────────────────
# When a handler needs to check "what is the mandatory output for X",
# it calls get_step_contract(message_type) → StepContract.
# The mandatory_output field tells the handler what to produce.

from .runtime_contract_map import get_contract, StepContract, NotifyPolicy


def get_mandatory_output(message_type: str) -> Optional[str]:
    """Return the mandatory_output for a message type, or None if terminal."""
    contract = get_contract(message_type)
    return contract.mandatory_output if contract else None


def get_allowed_results(message_type: str) -> List[str]:
    """Return allowed_results for a message type."""
    contract = get_contract(message_type)
    return contract.allowed_results if contract else []


def get_executor(message_type: str) -> Optional[str]:
    """Return which agent should handle this message type."""
    contract = get_contract(message_type)
    return contract.executor if contract else None


def get_notify_policy(message_type: str) -> List[NotifyPolicy]:
    """Return notify policy for a message type."""
    contract = get_contract(message_type)
    return contract.notify_policy if contract else []


# ── Re-exports ─────────────────────────────────────────────────────────────────
# For convenience, executors import from here, not from runtime_contract_map directly.

__all__ = [
    "load_doctrine_snapshot",
    "get_contract",
    "get_mandatory_output",
    "get_allowed_results",
    "get_executor",
    "get_notify_policy",
    "LoadedDoctrine",
    "DoctrineSnapshot",
    "DOCTRINE_PATHS",
]
