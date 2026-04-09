# Harness Integration Plan — V1

**Author:** Jarvis
**Date:** 2026-04-09
**Status:** V1 ARCHIVE — part of v1.0.0 freeze set

---

## Purpose

This document describes how the Harness layer is integrated into the PMO Smart Agent V1: what responsibilities it owns, what state/events/checkpoints it manages, and what is intentionally out of scope.

---

## Harness in the Layer Model

```
Layer 1: PMO Shell         — External interface (HTTP API)
Layer 2: Harness            — State + events + checkpoints ← THIS
Layer 3: Platform Model     — Governance rules and objects
Layer 4: LangGraph Engine   — Pipeline execution
```

Harness is the **state and trace substrate**. It does not make governance decisions, but it records and enforces the state those decisions operate on.

---

## Harness Subsystems

Harness consists of 5 subsystems in `gov_langgraph/harness/`:

### 1. StateStore (`state_store.py`)
JSON file-based persistence for workitems and task states.

**What it stores:**
- `workitems/{task_id}.json` — task metadata, current stage, owner, gate status
- `taskstates/{task_id}.json` — operational runtime state (current stage, status, timestamps)

**API:**
```
StateStore.save_workitem(workitem) → writes JSON
StateStore.load_workitem(task_id) → reads JSON
StateStore.save_taskstate(state)  → writes JSON
StateStore.load_taskstate(task_id) → reads JSON
```

**In V1:** All state is file-based. No database. `StateStore` is the authoritative source of truth for workitem state within gov_langgraph.

**Not owned by StateStore:** Governance meaning of state fields. That is Platform Model's responsibility.

### 2. Checkpointer (`checkpointer.py`)
Named checkpoint snapshots for resumability.

**What it stores:**
- `checkpoints/{task_id}/{checkpoint_name}.json` — point-in-time snapshot

**API:**
```
Checkpointer.save(task_id, checkpoint_name) → snapshot of current state
Checkpointer.load(task_id, checkpoint_name) → restore from snapshot
```

**In V1:** Used to snapshot state before stage transitions. Enables resume if a pipeline run is interrupted.

**Not owned by Checkpointer:** Whether to checkpoint, what name to use, when to resume. Those are LangGraph Engine decisions.

### 3. EventJournal (`events.py`)
Append-only event log for audit trail.

**What it stores:**
- `event_journal.jsonl` — one JSON line per event, never modified or deleted

**Event schema:**
```python
{
    "event_id": str,        # UUID
    "timestamp": str,       # ISO 8601
    "task_id": str,
    "actor": str,           # who triggered
    "event_type": str,      # e.g., "stage_advance", "gate_approved"
    "payload": dict         # event-specific data
}
```

**In V1:** Used by `AgentExecutor` to log stage transitions, gate decisions, and authority checks. Provides the governance trace that Alex can audit.

**Not owned by EventJournal:** What events to log, what payload to include. Those are enforced by AgentExecutor.

### 4. EvidenceStore (`evidence.py`)
Evidence reference storage per workitem.

**What it stores:**
- `evidence/{task_id}/{stage}/{evidence_type}.json` — evidence records

**Evidence types (V1):**
- `HANDOFF` — BA→SA, SA→DEV, DEV→QA handoff documents
- `APPROVAL` — gate approval records
- `REJECTION` — gate rejection records with reason

**API:**
```
EvidenceStore.put(task_id, stage, evidence_type, record)
EvidenceStore.get(task_id, stage, evidence_type)
EvidenceStore.list(task_id)
```

**In V1 simplification:** Evidence presence is inferred from `gate_decision_note` non-emptiness. A proper evidence model with content-addressable storage is deferred beyond V1.

### 5. Invariants (`invariants.py`)
Runtime consistency validation.

**What it validates:**
- Workitem/taskstate consistency (stage must match, owner must be set)
- Terminal state correctness (DONE/REJECTED cannot advance)
- Gate decision consistency (already-decided gates cannot be re-decided)

**API:**
```
validate_task_consistency(workitem, taskstate) → raises InvariantError if violated
```

**In V1:** All 9 E2E tests validate invariant enforcement. 0 invariant violations in cold-start E2E.

---

## Harness → Platform Model Boundary

Harness and Platform Model are adjacent layers:

| | Harness | Platform Model |
|--|---------|----------------|
| **Owns** | State storage, event log, checkpoints | Governance rules, authority matrix, stage transitions |
| **Does NOT own** | Meaning of state | State persistence |
| **Calls** | Platform Model for validation | Does not call Harness |

Harness `validate_task_consistency()` calls Platform Model enums (Tier, Action, Stage). But Platform Model does not depend on Harness.

**Clean separation:** This means Harness could be swapped for a database-backed implementation without changing Platform Model.

---

## Harness → LangGraph Boundary

LangGraph is the primary **consumer** of Harness:

```
LangGraph Engine:
  → calls StateStore.load_workitem()    before stage node runs
  → calls StateStore.save_workitem()   after stage node completes
  → calls Checkpointer.save()          before stage advance
  → calls Checkpointer.load()          on resume
  → calls EventJournal.append()        after each stage transition
  → calls EvidenceStore.put()          on handoff document creation
  → calls validate_task_consistency()  at start and end of each run
```

LangGraph is the **only** layer that writes to Harness in the normal pipeline path. PMO shell reads state via Harness to answer API requests.

---

## V1 Harness Scope Summary

| Subsystem | V1 Responsibility | Status |
|-----------|-------------------|--------|
| StateStore | JSON file persistence for workitems/taskstates | ✅ Complete |
| Checkpointer | Named snapshots before stage transitions | ✅ Complete |
| EventJournal | Append-only event log (JSONL) | ✅ Complete |
| EvidenceStore | Reference storage per workitem/stage | ✅ V1 simplification |
| Invariants | Runtime consistency validation | ✅ Complete |

---

## V1 Harness Exclusions (Deferred Beyond V1)

These are intentional V1 exclusions, not accidental gaps:

1. **No database backing** — StateStore is JSON files only. DB integration deferred.
2. **No content-addressable evidence** — EvidenceStore stores references, not evidence content. Proper evidence model deferred.
3. **No cross-process transactions** — StateStore operations are not atomic across multiple files. Transactional state updates deferred.
4. **No evidence content validation** — EvidenceStore accepts any dict; content schema validation deferred.
5. **No automated evidence completeness check** — "Evidence pending" = `gate_decision_note` emptiness. Sophisticated evidence chain deferred.

---

## Architecture Decisions (Harness)

| Decision | Rationale |
|----------|-----------|
| JSON file-based (not DB) | V1 simplification; file system = sufficient for single-project PMO |
| EventJournal = append-only JSONL | Simple, durable, no write conflicts; easy to replay |
| Checkpoints named by stage | Enables per-stage resume; no ambiguity on which checkpoint to load |
| EvidenceStore per-workitem directory | Logical isolation; easy to list all evidence for a task |
| Invariants checked at harness level | Catches state corruption early; before Platform Model enforcement |

---

## Archive Reference

Source in repo: `D:\Projects\gov_langgraph\gov_langgraph\harness\`

Key files:
- `state_store.py` — StateStore class
- `checkpointer.py` — Checkpointer + CheckpointRecord
- `events.py` — EventJournal
- `evidence.py` — EvidenceStore + EvidenceType
- `invariants.py` — validate_task_consistency()
- `config.py` — HarnessConfig

For engineering lessons learned from the original harness design: see `HARNESS_ENGINEERING_INTEGRATION_REVIEW_V0_1.md` (separate document in archive).
