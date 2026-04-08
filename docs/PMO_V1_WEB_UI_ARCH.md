# PMO V1 — Web UI Architecture

**Author:** Jarvis (Tech Lead)
**Date:** 2026-04-08
**Status:** ACTIVE — Reflects built implementation (2026-04-08)
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
│   POST /gate/approve       → approve_gate_tool         │
│   POST /gate/reject        → reject_gate_tool          │
│   POST /kickoff             → create_task_tool          │
│   GET  /tasks/{project_id} → list_tasks_tool           │
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

### `POST /gate/approve`
Approve a governance gate.

**Request:**
```json
{
  "task_id": "...",
  "gate_name": "DEFAULT",
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
  "message": "Gate approved at stage 'BA'"
}
```

### `POST /gate/reject`
Reject a governance gate.

**Request:**
```json
{
  "task_id": "...",
  "gate_name": "DEFAULT",
  "actor": "alex",
  "notes": "Evidence incomplete"
}
```

**Response:**
```json
{
  "ok": true,
  "gate_id": "...",
  "stage": "BA",
  "task_id": "...",
  "message": "Gate rejected at stage 'BA'"
}
```

### `POST /kickoff`
Announce a new project kickoff — creates a new workitem at INTAKE stage.

**Request:**
```json
{
  "task_title": "New Feature X",
  "project_id": "...",
  "current_owner": "BA",
  "current_stage": "BA",
  "priority": 3,
  "actor": "alex"
}
```

**Response:**
```json
{
  "ok": true,
  "task_id": "...",
  "task_title": "...",
  "current_stage": "BA",
  "message": "Task '...' created"
}
```

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

**index.html features:**
- View Status: task_id input → JSON response
- Approve Gate: task_id + gate_name + actor + notes → JSON response
- Reject Gate: same fields → JSON response
- Kickoff: title + project_id + owner + stage + priority + actor → JSON response
- List Tasks: project_id → task list
- Color-coded output: green = ok, red = error
- No external dependencies

---

## File Inventory

| File | Location | Purpose |
|------|----------|---------|
| main.py | `pmo_web_ui/main.py` | FastAPI server, 5 endpoints, harness init |
| index.html | `pmo_web_ui/static/index.html` | Vanilla HTML/JS/CSS frontend |

---

## E2E Verification (7/7 ✅)

| # | Action | Result |
|---|--------|--------|
| 1 | GET /status/{task_id} | 200 — correct stage/owner/status |
| 2 | POST /gate/approve | 200 — gate saved, event written |
| 3 | POST /gate/reject | 200 — gate saved, rejection logged |
| 4 | POST /kickoff | 200 — workitem created |
| 5 | GET /tasks/{project_id} | 200 — task list returned |
| 6 | Static HTML served | 200 — all sections present |
| 7 | GET / → index.html | 200 — frontend loads |

**Committed:** `eadc080` — feat(pmo_web_ui): add PMO Web UI — FastAPI + vanilla HTML/JS dashboard

---

## Scope Boundary

**In scope for PMO V1 Web UI:**
- ✅ View Status
- ✅ Confirm Gate (approve/reject)
- ✅ Announce Kickoff
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

| Sprint | Target | Status |
|--------|--------|--------|
| M1 | Scaffold + Status View | ✅ COMPLETE |
| M2 | Gate Confirmation | 🔲 |
| M3 | Kickoff Announcement | 🔲 |
| M4 | Edge Cases + Integration | 🔲 |
| M5 | V1 Complete | 🔲 |

---

## Sign-offs

| Role | Name | Decision | Date |
|------|------|---------|------|
| Nova (CAO) | Nova | ✅ APPROVED — architecture direction | 2026-04-08 |

---

## Open Items

| Item | Owner | Status |
|------|-------|--------|
| Sprint 1 close | Alex + Nova | 🔲 PENDING |
| Sprint 2 start | Jarvis | 🔲 PENDING |
