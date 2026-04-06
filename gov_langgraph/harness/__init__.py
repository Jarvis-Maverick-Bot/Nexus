"""
harness — Layer 2: State Persistence

Checkpoint, JSON state store, config, evidence references.

Layer 2: Workflow checkpoint/state = resumability + operational runtime state
Layer 3: Event journal = append-only trace (events.py)

Harness responsibility:
    - State persistence and retrieval
    - Evidence reference storage
    - Checkpoint lifecycle management

Harness does NOT own:
    - Governance meaning
    - Decision authority
    - Verification judgment
"""

from .config import HarnessConfig, get_default_config
from .state_store import StateStore
from .checkpointer import Checkpointer, CheckpointRecord, CheckpointError, CheckpointNotFoundError
from .evidence import EvidenceStore, EvidenceRecord, EvidenceType
from .events import EventJournal

__all__ = [
    # Config
    "HarnessConfig",
    "get_default_config",
    # State Store
    "StateStore",
    # Checkpointer
    "Checkpointer",
    "CheckpointRecord",
    "CheckpointError",
    "CheckpointNotFoundError",
    # Evidence
    "EvidenceStore",
    "EvidenceRecord",
    "EvidenceType",
    # Event Journal
    "EventJournal",
]
