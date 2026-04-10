# V1.5 Implementation Plan

**Version:** V0.3
**Date:** 2026-04-09 | Updated: 2026-04-10
**Based on:** V1.5 PRD + STEP_1..STEP_7 draft set + Direction Sync Summary
**Status:** APPROVED — updated per corrected governance model (2026-04-10)

---

## Executive Summary

**Target:** V1.5 PMO Smart Agent — governance surface + internal coordination layer over known agents, built on the frozen governed core.

**Corrected governance model (Nova-confirmed 2026-04-10):**
- Alex / Jarvis assign tasks to Maverick
- Maverick coordinates internally and returns status
- PMO Web UI presents aggregated status
- Alex / Jarvis make decisions at intake and gates
- Maverick = internal coordinator + status reporter, NOT autonomous decision-maker
- Human-governed intake/kickoff control — no automated readiness subsystem required for V1.5

**Core Principle:**
> Maverick coordinates. Platform Core governs. PMO surface displays. Humans decide at intake/gates. Each layer stays in its lane.

---

## V1.5 Build Themes

1. **True multi-project** — not a disguised single-project wrapper
2. **Internal coordination** — Maverick coordinates known agents internally, returns status; does NOT autonomously schedule
3. **Governed reference path** — BA→SA→DEV→QA pipeline is the canonical governed delivery shape
4. **Human-governed intake control** — kickoff blocked without project selection; no automated readiness engine
5. **Required reporting outputs** — Scope, SPEC, Arch, Testcase, TestReport, GuideLine
6. **Acceptance workflow expansion** — formal acceptance package using required artifact set
7. **Visible coordination status** — PMO surface shows Maverick's coordination status, not hidden backend
8. **Internal agent coordination** — Maverick handles agent coordination internally; PMO does not directly spawn
9. **Bounded advisory (Option A)** — risk signals, schedule estimates, blocker advice; non-blocking
10. **Status aggregation foundation** — clear human-readable project status view from Maverick's coordination

---

## Session Continuity Decision — Active Validation Track

Before locking the architecture, 4 directions are being validated:

| Direction | Status | Implication |
|-----------|--------|-------------|
| ACP persistent sessions via config fix | **Active** — may be recoverable via config/registration; this remains unverified | Would enable Model A if confirmed viable |
| Session leasing pattern | **Unverified** — subagents tool shows no leasing API; not ruled out until tested | Potential alternative if API supports it |
| One-shot + structured rehydration | **Verified working** | Confirmed V1.5 baseline path |
| Custom persistence layer | **Deferred** — infrastructure work, not product work | Out of scope for V1.5 |

**Current working assumption:** V1.5 proceeds with **Model B (one-shot + rehydration)** as the primary architecture. Model A remains a potential enhancement if Direction 1 (ACP config fix) proves viable without significant rework.

If Model B is the final path: continuity/memory design is **architectural, not optional**. Each spawn must receive a complete context package from Harness.

---

## Proposed Build Order

| Order | Theme | What | Dependency |
|-------|-------|------|------------|
| 1 | Multi-project model | Project object, ProjectStore, multi-project state isolation | None |
| 2 | Project/task linkage | project → task → stage relationship, task creation under project | Order 1 |
| 3 | PMO governance surface | Project management, kickoff control, status visibility, gate decisions | Order 1 |
| 4 | Required reporting surfaces | Scope, SPEC, Arch, Testcase, TestReport, GuideLine artifact tracking | Order 2 |
| 5 | Acceptance workflow | AcceptancePackage, formal acceptance flow, required artifact completeness | Order 4 |
| 6 | Maverick internal coordination | MaverickSpawner class, agent registry, coordination status return | Order 1 |
| 7 | Advisory (Option A) | Risk signals, schedule estimates, blocker advice; non-blocking | Order 6 |
| 8 | Status aggregation | PMO surface shows aggregated status from Maverick's coordination | Order 3 + 6 |

**Note on spawn path:** Agent spawn via Maverick is internal coordination. V1.5 does not require PMO → Maverick direct spawn. Telegram relay is the working path for V1.5; message middleware is V2.0.

---

## Phase 1 — Agent Spawn Path (Internal to Maverick)

**Corrected model:** Agent spawn is Maverick's internal concern. V1.5 does not make spawn a first-class PMO endpoint.

### 1.1 Spawn path status

```
runtime="subagent" + mode="run"  → WORKS ✅ (one-shot, confirmed)
runtime="subagent" + mode="session" + thread=true → BLOCKED
runtime="acp" + mode="session" + thread=true → BLOCKED
```

**V1.5 spawn:** Telegram relay (PMO → Jarvis → Maverick → Viper). This is the working path. Direct PMO → Maverick spawn is V2.0 (message middleware).

### 1.2 Agent registry definition

```python
AGENT_REGISTRY = {
    "viper_ba":  "viper-ba",
    "viper_sa":  "viper-sa",
    "viper_dev": "viper-dev",
    "viper_qa":  "viper-qa",
    "maverick":  "maverick",
}
```

### 1.3 MaverickSpawner class

```python
class MaverickSpawner:
    """Internal coordinator — routes work to known agents based on context."""

    def coordinate(self, project_id: str, task_id: str, role: str) -> CoordinationResult:
        """Coordinate a known agent for a task."""
        ...

    def get_status(self, project_id: str, task_id: str) -> CoordinationStatus:
        """Return current coordination status."""
        ...
```

Key design rule: Maverick **coordinates** known agents internally. It does not autonomously decide — it executes assigned coordination and reports status.

---

## Phase 2 — Multi-Project Model

### 2.1 Project object

```python
class Project:
    project_id: str
    name: str
    description: str
    owner: str
    status: ProjectStatus  # ACTIVE | SUSPENDED | COMPLETE | SHUTDOWN
    created_at: datetime
    updated_at: datetime

class ProjectStatus(str, Enum):
    ACTIVE    = "active"
    SUSPENDED  = "suspended"
    COMPLETE  = "complete"
    SHUTDOWN  = "shutdown"
```

### 2.2 ProjectStore

JSON file-based persistence parallel to StateStore.

### 2.3 Go Kickoff vs Shutdown behavior

| Alex action | System response |
|-------------|-----------------|
| Shutdown | Project status → SHUTDOWN. No project/task created. Audit log entry. |
| Go Kickoff | Readiness checked first. If all checks pass → project + task created and activated. If any check fails → nothing created, blocked reasons returned. |

---

## Phase 3 — Human-Governed Intake Control

**Corrected model (Nova 2026-04-10):** No automated readiness-check subsystem is required for V1.5. Human-governed intake/kickoff control exists at the PMO surface.

### 3.1 PMO intake control (human-facing)

| Control point | Behavior |
|--------------|----------|
| Project creation | Requires: project_name, project_owner, project_goal (goal optional) |
| Kickoff | Blocked without project selection — human must actively choose which project to kick off |
| Gate decisions | Human reviews and approves/rejects at each stage gate |
| Intake decision | Alex / Jarvis assigns to Maverick — this is the human decision point, not an automated trigger |

### 3.2 Readiness framing

PMO surface shows clear readiness / status framing to humans:
- Project must be in ACTIVE status before tasks can be created under it
- Kickoff form requires project selection (enforced at form level)
- No automated ReadinessCheck engine — humans make go/no-go decisions at intake

### 3.3 Future (V2.0)

Automated readiness-check subsystem (ReadinessCheck objects, /check-readiness endpoints) is deferred to V2.0 when message middleware enables proper command channel.

---

## Phase 4 — Required Reporting Outputs

These 6 artifacts are mandatory for every V1.5 project:

| Artifact | Generated by | When |
|----------|-------------|------|
| Scope | Alex defines | On project creation |
| SPEC (7-step) | BA agent | After BA stage |
| Arch | SA agent | After SA stage |
| Testcase | QA prep | Before QA stage |
| TestReport | Alex UAT | After QA |
| GuideLine | Maverick drafts; Alex reviews and approves | On project completion |

**Governance rule:** No project reaches DONE without all 6 artifacts present and linked in Harness.

---

## Phase 5 — Acceptance Workflow

### 5.1 AcceptancePackage

```python
class AcceptancePackage:
    task_id: str
    deliverables: list[Deliverable]
    verification_notes: str
    test_results_ref: str
    approval_signatures: dict[str, str]
    artifact_completeness: dict[str, bool]
```

### 5.2 Acceptance flow

```
TASK_READY_FOR_ACCEPTANCE
    → PMO notifies Alex
    → Alex reviews AcceptancePackage + artifact completeness
    → Alex approves or rejects with reason
    → If approved: TASK_DONE
    → If rejected: TASK_REVISION_REQUESTED
```

---

## Phase 6 — Maverick Advisory (Option A)

### 6.1 Advisory signals

| Signal | Trigger | Output |
|--------|---------|--------|
| Risk signal | Task blocked > N hours | "Task X blocked by [reason]. Consider escalating." |
| Schedule signal | Task duration > estimate | "Task X is N hours over estimate." |
| Stage signal | Stage transition | "Task X completed BA. SA is next." |
| Summary signal | On demand | Full project status from Maverick |

### 6.2 Advisory boundary

Maverick advisory is **informational only, non-blocking, non-authoritative**.

---

## Watchpoints

- Multi-project must not be a thin wrapper faking multiple projects over shared state
- Maverick must not become an autonomous decision-maker — it coordinates and reports, humans decide
- PMO surface must not blur the line between status display and governance authority
- Spawn path: Telegram relay is V1.5's working path; message middleware is V2.0 — do not conflate them
- Advisory (Option A) adds ambition and schedule risk; treat carefully
- Human-governed intake control must remain human — do not automate the go/no-go decision

---

## One-line Definition

**V1.5 is the PMO governance surface + internal coordination layer: Alex/Jarvis assign to Maverick, Maverick coordinates known agents internally and returns status, PMO Web UI aggregates and displays status, humans decide at intake/gates, and Platform Core remains the sole authoritative source of truth — no automated readiness subsystem required for V1.5, message middleware deferred to V2.0.****
