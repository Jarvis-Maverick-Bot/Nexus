# PMO V1 — Web UI Architecture

**Author:** Jarvis (Tech Lead)
**Date:** 2026-04-08
**Updated:** 2026-04-09
**Status:** V1 COMPLETE — frozen at v1.0.0
**Nova review:** ✅ ACCEPTED — 2026-04-08
**Nova review:** ✅ ACCEPTED — 2026-04-08

---

## Overview

PMO V1 Web UI is a **standalone web application** providing the primary human interface for the 3 PMO V1 functions.

- **Backend:** FastAPI — lightweight HTTP API exposing gov_langgraph tools as REST endpoints
- **Frontend:** Single HTML/JS page — form-based UI, no build step required
- **Target port:** 8000 (configurable via `PMO_PORT` env)

**Implementation:** Vanilla HTML/JS. FastAPI calls gov_langgraph tools directly. No gov_client.py abstraction layer in V1.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                     Browser (Web UI)                     │
│         index.html — form-based, vanilla JS             │
└─────────────────────┬───────────────────────────────────┘
                      │ HTTP JSON
                      ▼
┌─────────────────────────────────────────────────────────┐
│               FastAPI Server (port 8000)                 │
│                                                         │
│   GET  /status/{task_id}   → get_status_tool           │
│   GET  /gate/{task_id}     → get_gate_panel_tool       │
│   POST /gate/approve       → approve_gate_tool        │
│   POST /gate/reject        → reject_gate_tool          │
│   POST /kickoff             → kickoff_task_tool         │
│   GET  /tasks/{project_id} → list_tasks_tool          │
└─────────────────────┬───────────────────────────────────┘
                      │ Direct function calls
                      ▼
┌─────────────────────────────────────────────────────────┐
│              gov_langgraph tools.py                     │
│              (same tools, same logic)                   │
└─────────────────────┬───────────────────────────────────┘
                      │ Read / Write
                      ▼
┌─────────────────────────────────────────────────────────┐
│   StateStore + EventJournal + EvidenceStore (Harness)   │
└─────────────────────────────────────────────────────────┘
```

**Key principle:** PMO is a non-authoritative shell. gov_langgraph is sole source of truth. PMO holds zero independent authoritative data.

---

## API Endpoints

### `GET /status/{task_id}`
Returns full status for a single task.

**Response:**
```json
{
  "ok": true,
  "task_id": "...",
  "task_title": "...",
  "current_stage": "BA",
  "current_owner": "viper_ba",
  "task_status": "IN_PROGRESS",
  "current_blocker": null
}
```

### `GET /gate/{task_id}`
Returns the current gate decision for a task's active stage.

**Response:**
```json
{
  "ok": true,
  "task_id": "...",
  "task_title": "...",
  "current_stage": "BA",
  "current_owner": "viper_ba",
  "gate_status": "pending",
  "gate_stage": "BA",
  "gate_type": "stage_advance",
  "gate_decision": null,
  "gate_decision_by": null,
  "gate_decision_note": "",
  "gate_decided_at": null,
  "message": "..."
}
```

**`gate_status` values:** `pending` | `approved` | `rejected` | `no_gate`

### `POST /gate/approve`
Approve a governance gate. **Double-decision prevention** — returns error if gate is already decided.

**Request:**
```json
{
  "task_id": "...",
  "gate_name": "BA_GATE",
  "actor": "alex",
  "notes": "Evidence looks good"
}
```

**Response:**
```json
{
  "ok": true,
  "gate_id": "...",
  "stage": "BA",
  "task_id": "...",
  "gate_status": "approved",
  "message": "Gate approved at stage 'BA'"
}
```

### `POST /gate/reject`
Reject a governance gate. **Rejection reason is required.**

**Request:**
```json
{
  "task_id": "...",
  "gate_name": "BA_GATE",
  "actor": "alex",
  "notes": "Evidence incomplete — please revise"
}
```

**Response:**
```json
{
  "ok": true,
  "gate_id": "...",
  "stage": "BA",
  "task_id": "...",
  "gate_status": "rejected",
  "message": "Gate rejected at stage 'BA'"
}
```

### `POST /kickoff`
Announce a new project kickoff — creates a workitem at INTAKE stage.

**Product-shaped interface.** Assignee is optional (blank = unassigned). Backend sets stage to INTAKE and assigns the default project automatically.

**Request:**
```json
{
  "title": "New Feature X",
  "description": "Build a dashboard for PMO to view project status",
  "priority": 1,
  "assignee": "viper_ba",
  "actor": "alex"
}
```

**Response:**
```json
{
  "ok": true,
  "task_id": "...",
  "task_title": "New Feature X",
  "current_stage": "INTAKE",
  "assignee": "viper_ba",
  "message": "Kickoff announced: 'New Feature X' entered pipeline at INTAKE, assigned to viper_ba."
}
```

**Priority values:** 0=P0, 1=P1, 2=P2, 3=P3

### `GET /tasks/{project_id}`
List all workitems for a project.

**Response:**
```json
{
  "ok": true,
  "project_id": "...",
  "tasks": [...],
  "count": 1
}
```

---

## Frontend Structure

```
pmo_web_ui/
├── main.py              # FastAPI server (port 8000)
└── static/
    └── index.html       # Standalone frontend — vanilla HTML/JS/CSS
```

**index.html sections:**
- **Gate Confirmation:** Load gate by task ID → product-shaped gate panel (stage, status badge, evidence, approve/reject buttons)
- **View Status:** task_id input → JSON response
- **Announce Kickoff:** title + description + priority selector (P0–P3) + assignee (optional) + actor → JSON response
- **List Tasks:** project_id → task list
- Color-coded output: green = ok, red = error, amber = warning

**Design principles:**
- Gate panel shows only decision-relevant fields (no raw backend state)
- Kickoff form uses product model — no `project_id`, `current_stage`, or `current_owner` fields exposed
- Double-decision prevention: already-approved/rejected gates show status badge, not action buttons

---

## File Inventory

| File | Location | Purpose |
|------|----------|---------|
| main.py | `pmo_web_ui/main.py` | FastAPI server, 6 endpoints, harness init |
| index.html | `pmo_web_ui/static/index.html` | Vanilla HTML/JS/CSS frontend |

---

## E2E Verification

| # | Action | Result |
|---|--------|--------|
| 1 | GET /status/{task_id} | ✅ 200 — correct stage/owner/status |
| 2 | GET /gate/{task_id} | ✅ 200 — gate panel loads correctly |
| 3 | POST /gate/approve | ✅ 200 — gate saved, event written |
| 4 | POST /gate/reject | ✅ 200 — gate saved, rejection logged |
| 5 | POST /kickoff (with assignee) | ✅ 200 — workitem created at INTAKE |
| 6 | POST /kickoff (without assignee) | ✅ 200 — assignee = unassigned |
| 7 | POST /kickoff (missing fields) | ✅ 422 — validation error |
| 8 | GET /tasks/{project_id} | ✅ 200 — task list returned |
| 9 | Static HTML served | ✅ 200 — all sections present |

**Committed:** `c026c49` — feat(Sprint3): product-shaped kickoff — no backend fields in UI

---

## Scope Boundary

**In scope for PMO V1 Web UI:**
- ✅ View Status
- ✅ Confirm Gate (approve/reject with double-decision prevention)
- ✅ Announce Kickoff (product-shaped, no backend fields)
- ✅ Error handling (platform unreachable, double confirm, reject without reason)

**NOT in scope (future phases):**
- ❌ gov_client.py abstraction layer
- ❌ Next.js frontend
- ❌ Kickoff readiness checks
- ❌ Expanded reporting
- ❌ Multi-user support
- ❌ Artifact upload/management

---

## Sprint Status

| Sprint | Target | Status | Commit |
|--------|--------|--------|--------|
| M1 | Scaffold + Status View | ✅ COMPLETE | `eadc080` |
| M2 | Gate Confirmation | ✅ ACCEPTED | `6bcec5d` + `2b8458a` |
| M3 | Kickoff Announcement | ✅ ACCEPTED | `c026c49` |
| M4 | Edge Cases + Integration | ✅ ACCEPTED | `530b72f` |
| M5 | V1 Complete | ✅ COMPLETE | `efbcac9` |

---

## Sign-offs

| Role | Name | Decision | Date |
|------|------|---------|------|
| Nova (CAO) | Nova | ✅ APPROVED — architecture direction | 2026-04-08 |

## Open Items

| Item | Owner | Status |
|------|-------|--------|
| M2 Sprint 2 close | Alex + Nova | ✅ ACCEPTED — 2026-04-09 |
| M3 Sprint 3 close | Alex + Nova | ✅ ACCEPTED — 2026-04-09 |
| M4 Edge Cases + Integration | Alex + Nova | ✅ ACCEPTED — 2026-04-09 (`530b72f`) |
| DEFAULT_PROJECT_ID hardcoded | Jarvis | ⚠️ NOTE — V1 shortcut, not doctrine (Nova 2026-04-09) |
| Evidence pending = gate_decision_note emptiness | Jarvis | ⚠️ NOTE — V1 simplification, not long-term evidence model (Nova 2026-04-09) |
