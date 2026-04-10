# Day 1 Progress Report — gov_langgraph V1.5

**Date:** 2026-04-09
**Reporting:** Jarvis
**Status:** CANDID — facts only, no performance
**Version:** 1.1 — updated per Nova's feedback (2026-04-09 23:31 GMT+8)
**Distribution:** Nova + Alex

---

## Executive Summary

Day 1 of gov_langgraph V1.5 is complete. The governance shell (PMO Web UI, multi-project model, kickoff, gate decisions, event journal) is built and E2E verified. The pipeline code is complete but cannot execute autonomously in V1.5 — agent spawning requires either a working command channel (deferred to V2.0) or the Telegram relay workaround (functional but not ideal for a self-governed PMO).

Day 1 work extended and hardened the V1.5 branch. Sprint checkpoints were reviewed and accepted as delivered, but final closure requires integrated branch state and end-to-end verification — checkpoint acceptance is not equivalent to full integrated version acceptance. The honest result: a solid governance foundation with known gaps — all addressed by V2.0 middleware.

---

## Planned vs. Actual — Day 1

### Sprint 1 — OpenClaw Spawn + Multi-Project Model

**What was planned:**
- Verify sessions_spawn from PMO runtime
- Add Project object + ProjectStore
- Add project tools (create, get, list)
- Verify multi-project isolation
- Spawn agent via MaverickSpawner

**What was completed:**
- Project object + ProjectStatus enum ✅
- ProjectStore (JSON file persistence) ✅
- ProjectStore wired into harness layer ✅
- create_project_tool, get_project_tool, list_projects_tool ✅
- API contract verified (E2E: 5/5 endpoints pass)

**What was NOT completed:**
- sessions_spawn verification from FastAPI — FAILED
  - cmdop SDK is cloud gRPC only; sessions_spawn is Node.js runtime IPC
  - PMO cannot directly spawn agents — this is a real architectural gap
  - workaround: Telegram relay (PMO → Jarvis on Telegram → Maverick)
- MaverickSpawner.schedule() actual agent spawn — NOT VERIFIED
  - Class and method exist but end-to-end spawn not tested

**Root cause of gap:** The Python SDK (cmdop) used by the openclaw package connects to the cloud gRPC service. sessions_spawn is a local gateway tool exposed only through the Node.js runtime. A standalone FastAPI process cannot reach it.

---

### Sprint 2 — Project/Task Linkage + Kickoff Readiness + MaverickSpawner

**What was planned:**
- WorkItem project_id linkage
- Task creation under specific project
- ReadinessCheck + KickoffReadiness objects (4 mandatory checks)
- /check-readiness and /project/{id}/activate endpoints
- MaverickSpawner.schedule() implementation
- Agent registry config
- Spawn failure graceful handling

**What was completed:**
- WorkItem project_id linkage ✅
- Task creation under specific project ✅
- Project creation form added to PMO Web UI ✅
- Kickoff blocked without project selection (selector disabled until project exists) ✅
- Agent registry config (agents.yaml) ✅
- Spawn failure: logs error, returns error response ✅
- Project creation field name contract aligned (frontend ↔ backend) ✅

**What was NOT completed:**
- ReadinessCheck + KickoffReadiness objects — NOT BUILT
- /check-readiness and /project/{id}/activate endpoints — NOT BUILT
- PMO accepts kickoff without readiness verification (no gate on scope, team, schedule, dependencies)
- MaverickSpawner.schedule() end-to-end — NOT TESTED

---

## Additional Fixes Applied During Day 1

During Nova's three-skill closure review, the following issues were found and resolved:

| Issue | Severity | Status |
|-------|----------|--------|
| Project status enum mismatch (frontend: `on-hold`/`completed`/`archived` vs. backend: `on_hold`/`closed`/`shutdown`) | Major | ✅ FIXED |
| Project creation field name mismatch (frontend sent `name`/`owner` → backend expects `project_name`/`project_owner`) | Major | ✅ FIXED |
| Test artifacts committed to branch (`_test_spawn.py`, `_test_spawn2.py`, `pmo_server.err`, `pmo_server.log`) | Major | ✅ FIXED — removed from branch, .gitignore added |
| gateway_spawner.py not classified as experimental | Minor | ✅ FIXED — experimental note added to docstring |
| /test-spawn endpoint not classified as experimental | Minor | ✅ FIXED — experimental note added to docstring |

---

## E2E Lifecycle Verification — 5/5 PASSED

```
1. Create project...  status=200 ok=True project_id=6631044e-6e15-4275-b06f-fcdac838edf7
2. Kickoff task...    status=200 ok=True task_id=01af1b22-7612-4aea-8741-ad0c6a8ee3af
3. Get task status... status=200 ok=True tasks_count=1
4. Load gate panel... status=200 ok=True gate_status=pending
5. List projects...   status=200 ok=True count=43
=== ALL CHECKS PASSED ===
```

All 5 PMO Web UI endpoints verified against live backend.

---

## Root Cause Analysis

All three gaps (spawn verification, readiness checks, E2E pipeline) trace back to one architectural problem: **no direct command channel from PMO to Maverick.**

V1.5 built:
- Shared filesystem (StateStore + ProjectStore + EventJournal) for **state**
- PMO Web UI (FastAPI) for **governance visibility**

V1.5 does NOT have:
- A command bus for **actions** (spawn agent, trigger readiness check, advance pipeline)
- Direct PMO → Maverick communication path

Current command path in V1.5:
```
PMO Web UI → Telegram message to Jarvis → Jarvis spawns Maverick → Maverick spawns Viper
```

This works but is operationally fragile — Telegram is the critical path for every agent spawn, and a self-governed PMO should not depend on a human's Telegram session to trigger pipeline actions.

---

## Plans for Remaining Items

### V2.0 — Message Middleware

**Proposed solution:** Replace shared filesystem as command bus with a proper message middleware.

#### What
SQLite-backed durable message queue. PMO and Maverick both connect to the same SQLite file on the shared drive. No separate message broker infrastructure required.

#### Message Envelope
```json
{
  "id": "uuid-v4",
  "to": "maverick",
  "from": "pmo",
  "action": "spawn | readiness_check | advance_stage | ...",
  "payload": { ... },
  "timestamp": "ISO-8601",
  "reply_to": null,
  "status": "pending | delivered | acknowledged | failed",
  "delivery_attempts": 0
}
```

#### SQLite Schema (proposed)
```sql
CREATE TABLE messages (
  id TEXT PRIMARY KEY,
  envelope TEXT NOT NULL,  -- JSON
  status TEXT DEFAULT 'pending',
  delivery_attempts INTEGER DEFAULT 0,
  created_at TEXT NOT NULL,
  delivered_at TEXT,
  acknowledged_at TEXT
);

CREATE INDEX idx_to_status ON messages(to, status);
CREATE INDEX idx_created ON messages(created_at);
```

#### Governance Rule (per Nova)
Middleware = transport/coordination layer only. Not the system of record. Not the governance truth. State and governance decisions remain in StateStore/ProjectStore/EventJournal.

#### Why SQLite
- Atomic writes (no concurrent clobbering like JSON file sharing)
- Works over network share (SMB)
- Durable — messages persist until acknowledged
- No separate service to run or monitor
- Observable — status column shows delivery state

#### Communication Patterns Supported

**1. Agent → Agent (Maverick ← PMO)**
```
PMO writes: { to: "maverick", action: "spawn", payload: { role: "viper_ba", project_id: "..." } }
Maverick reads, processes, writes ack: { status: "acknowledged", payload: { session_key: "..." } }
PMO sees result
```

**2. Human → Agent (Alex → Maverick via PMO)**
```
Alex fills PMO form → PMO writes message → Maverick reads → processes
```

**3. Agent → Human (Maverick → PMO → Alex)**
```
Maverick writes: { to: "pmo", action: "gate_pending", payload: { task_id: "...", stage: "BA_GATE" } }
PMO polls, surfaces gate panel → Alex approves/rejects
```

#### Solves Simultaneously
- Direct PMO → Maverick spawn (no Telegram relay)
- Readiness check triggers (middleware message → Maverick evaluates)
- Guaranteed at-least-once delivery with acknowledgment
- No concurrent write clobbering
- Observable delivery state for every command

#### Timeline
- Sprint 3 (Day 2): Architecture spec + Nova review
- Sprint 4 (Day 2): Implementation
- Sprint 5 (Day 3): Integration + E2E
- Sprint 6 (Day 3): UAT + acceptance

---

## V1.5 — Honest Assessment

### What V1.5 Delivers
- **Governance shell:** Project management, kickoff announcement, gate confirmation, status view, task listing
- **Multi-project state model:** ProjectStore with full CRUD, state isolation per project
- **Pipeline code:** BA → SA → DEV → QA stage nodes, halt nodes, evidence store
- **Event journal:** Immutable audit trail for all governance actions
- **Formal acceptance workflow:** Gate decisions with double-decision prevention, approve/reject with notes

### What V1.5 Does NOT Deliver
- **Autonomous spawn:** PMO cannot spawn agents without Telegram relay
- **Readiness-gated kickoff:** Any project can be kicked off regardless of scope/team/schedule readiness
- **Verified E2E pipeline:** Pipeline code exists but execution not verified end-to-end

### V1.5 Limitation — Explicitly Documented
This limitation is accepted only because it is documented here and deferred to V2.0:
- **V1.5 = governance shell + state model + pipeline code**
- **V2.0 = transport/middleware hardening + autonomous spawn**
- Middleware is the transport/coordination layer — not the system of record, not the governance truth
- This limitation must appear in any V1.5 acceptance documentation

### Commits on v1.5 (Day 1)
| Commit | Description |
|--------|-------------|
| `5151645` | feat(Sprint2): project creation form + project-aware kickoff |
| `b18af7a` | fix(V1.5): align project status enum + remove test artifacts |
| `ac7d49d` | chore(V1.5): mark gateway_spawner and /test-spawn as experimental |
| `74dad17` | fix(V1.5): align project creation field names frontend-to-backend |
| `990b92c` | chore(V1.5): remove _e2e_test.py from tracked files |

---

## Recommended Next Steps

1. **Nova reviews this report** — confirm it accurately reflects the situation, flag any misstatements
2. **Alex + Nova approve V2.0 direction** — pivot Day 2 to middleware architecture spec
3. **Sprint 3 begins** — define message envelope, SQLite schema, communication patterns
4. **V2.0 design review** with Nova before any implementation begins

---

*Report filed by Jarvis — 2026-04-09 23:28 GMT+8*
