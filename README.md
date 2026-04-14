# gov_langgraph — V1.7 Build Candidate

**Version:** V1.7 (`origin/v1.7`, tag `v1.7.0`)
**Status:** ✅ Sprint 6R CLOSED — Nova ACCEPT WITH NOTES (2026-04-12 23:39 GMT+8)
**Pending:** Alex second-round UAT

---

## What is this?

`gov_langgraph` is the THE ONE enterprise governance engine. It provides:

- **Platform Core** — objects, authority rules, state machine for BA→SA→DEV→QA pipeline
- **Harness Layer** — persistence, checkpointing, event journaling, evidence storage
- **PMO Web UI** — FastAPI dashboard at `http://localhost:8000/`
- **Game Production Surface** — Grid Chase tracked through all 6 stages
- **OpenClaw Integration** — tool functions for Telegram-based operation

---

## V1.7 Build Summary

**Grid Chase** (game_id: `633e3ac6-1511-4605-9cb6-ddf7eb00b924`) completed all 6 governance stages:

| Stage | Status | Artifact |
|-------|--------|----------|
| CONCEPT | ✅ Complete | GC-BRIEF-001 |
| GAME_SPEC | ✅ Complete | GC-SPEC-001 |
| PRODUCTION_PREP | ✅ Complete | GC-HANDOVER-001 |
| PRODUCTION_BUILD | ✅ Complete | GC-BUILD-001 |
| QA_PLAYTEST | ✅ Complete | — |
| ACCEPTANCE_DELIVERY | ✅ Complete | GC-DELIVERY-001 |

**Git tag:** `v1.7.0` applied and pushed to `origin/v1.7`

---

## Quick Start

```bash
cd D:\Projects\gov_langgraph

# Install dependencies
pip install -r requirements.txt

# Boot PMO Web UI
python -m uvicorn pmo_web_ui.main:app --port 8000

# Open in browser
# http://localhost:8000/
```

---

## Running Tests

```bash
# Smoke tests (Sprint 2R — 7 workflow tests)
python run_s2_tests.py

# Smoke tests (Sprint 4R — 9 PMO game surface tests)
python run_s4_tests.py

# E2E integration test (full 6-stage progression)
python E2E_TEST.py

# Full LangGraph pipeline test
python LANGGRAPH_E2E_TEST.py
```

---

## Project Structure

```
gov_langgraph/
├── platform_model/              # Platform Core
│   ├── objects.py              # Project, WorkItem, TaskState, Workflow, Handoff, Gate, Event
│   ├── authority.py            # Role-based authority (Tier 1/2/3)
│   ├── state_machine.py         # Stage transition validation
│   ├── exceptions.py           # Exception hierarchy
│   └── workflows.py            # V1 Pipeline definition
│
├── langgraph_engine/            # LangGraph StateGraph
│   ├── state.py                # GovernanceState dataclass
│   ├── graph.py                # build_graph() — START→maverick→stage nodes→END
│   ├── pipeline.py             # compile() + run_workitem()
│   ├── runtime.py              # RuntimeContext singleton
│   ├── edges.py               # Edge routing rules
│   └── nodes/                 # Stage nodes + maverick
│
├── harness/                     # Persistence
│   ├── config.py               # HarnessConfig
│   ├── state_store.py         # JSON file I/O
│   ├── checkpointer.py        # Before/after checkpointing
│   ├── events.py             # Append-only event journal
│   └── evidence.py           # Evidence storage
│
├── pmo_smart_agent/            # PMO CLI
│   ├── cli.py                # 6 commands: status, list, pipeline, events, checkpoint, evidence
│   └── dashboard.py          # get_pipeline_view() + render_pipeline_text()
│
├── pmo_web_ui/                 # PMO Web UI (FastAPI)
│   └── main.py               # Server on port 8000
│       └── static/           # Frontend assets
│           ├── index.html   # Main dashboard
│           ├── main-app.js  # Extracted inline script (V1.7 fix)
│           ├── utils.js     # Pure JS helpers
│           ├── gate-surface.js  # Gate interaction
│           └── i18n-runtime.js  # EN/ZH translations
│
├── openclaw_integration/       # OpenClaw tool layer
│   └── tools.py              # 20 tool functions for Telegram operation
│
└── artifacts/                 # Grid Chase production artifacts
    └── GC-BUILD-001/         # Build Candidate (game engine + REST API + web dashboard)
        ├── game_engine.py    # Flask game API server
        └── requirements.txt  # Runtime dependencies
```

---

## V1.7 Sprint Log

| Sprint | Focus | Status | Key Commits |
|--------|-------|--------|-------------|
| 1R | THE ONE Definition | ✅ Closed | — |
| 2R | Workflow + Stage Definitions | ✅ Closed | Smoke tests 7/7 pass |
| 3R | Game Brief + Game Spec | ✅ Closed | GC-BRIEF-001, GC-SPEC-001 |
| 4R | PMO Game Production Surface | ✅ Closed | Backend 7f7becf, Frontend b722693 |
| 5R | Production Handoff + Validation | ✅ Closed | GC-HANDOVER-001, GC-VALIDATION-001, GC-DELIVERY-001 |
| 6R | E2E + Smoke + Integration + Acceptance | ✅ Closed | Tag v1.7.0, Nova ACCEPT WITH NOTES |

---

## Smoke Test Results (Sprint 6R)

**Sprint 2R — 7/7 pass (2026-04-12 21:22 GMT+8)**

| Test | Description | Result |
|------|-------------|--------|
| Case 1 | New game → CONCEPT | ✅ |
| Case 2 | CONCEPT → GAME_SPEC (no approval) blocked | ✅ |
| Case 3 | CONCEPT → GAME_SPEC (approved) | ✅ |
| Case 4 | GAME_SPEC → PRODUCTION_PREP | ✅ |
| Case 5 | GAME_SPEC → PRODUCTION_BUILD (skip) blocked | ✅ |
| Case 6 | PRODUCTION_PREP → PRODUCTION_BUILD | ✅ |
| Case 7 | PRODUCTION_BUILD → PRODUCTION_PREP (backward) blocked | ✅ |

**Sprint 4R — 9/9 pass (2026-04-12 21:22 GMT+8)**

| Test | Description | Result |
|------|-------------|--------|
| S4.1 | Create game | ✅ |
| S4.2 | Retrieve game | ✅ |
| S4.3 | Valid advance | ✅ |
| S4.4 | Invalid advance | ✅ |
| S4.5 | Invalid skip | ✅ |
| S4.6 | Invalid backward | ✅ |
| S4.7 | Trigger flag | ✅ |
| S4.8 | Escalation | ✅ |
| S4.9 | Status report | ✅ |

---

## Authority Model

**Tier 1 — Query only:** All roles can perform query actions (no mutations).

**Tier 2 — Management Layer:** Governance actions (create, assign, approve, gate, close).
- `alex` — final escalation, governance decisions
- `nova` — chief auditing officer
- `jarvis` — coordinator
- `maverick` — PMO

**Tier 3 — Delivery Layer:** Stage execution roles.
- `viper_ba`, `viper_sa`, `viper_dev`, `viper_qa` — stage owners

---

## Known Issues / Non-Blocking Notes

| Issue | Severity | Note |
|-------|----------|------|
| Python 3.14 / Pydantic V1 warning | Low | Non-blocking. Migrate to Pydantic V2 patterns before Python 3.14 baseline. |
| GitHub Issue #2 (workspaceShell) | ✅ Fixed | Fixed in commit `7254873`. Served runtime confirmed correct. |

---

## Data Storage

| Layer | Storage |
|-------|---------|
| Projects, WorkItems, TaskStates, Gates, Handoffs | `~/.gov_langgraph/state/*.json` |
| Checkpoints | `~/.gov_langgraph/checkpoints/*.json` |
| Event journal | `~/.gov_langgraph/events/*.jsonl` |
| Evidence | `~/.gov_langgraph/state/evidence/*.jsonl` |

---

## References

- Execution plan: `\\192.168.31.124\Nova-Jarvis-Shared\working\gov_langgraph\V1.7\V1_7_EXECUTION_PLAN.md`
- Sprint 6R log: `C:\Users\John\.openclaw\workspace\SPRINT_6R.md`
- Artifact chain: GC-BRIEF-001 → GC-SPEC-001 → GC-HANDOVER-001 → GC-BUILD-001 → GC-VALIDATION-001 → GC-DELIVERY-001