# V1_8_DELIVERY_PACKAGE.md

**Version:** 1.0  
**Date:** 2026-04-14  
**Status:** CLOSED — Nova final sign-off received (2026-04-14T18:53 GMT+8)

---

## Game: Grid Escape

Grid Escape is an AI-native maze navigation game. The agent starts in a grid and must find the exit using navigation commands.

**CLI:** `python games/grid_escape.py --grid ge-001`  
**Grids:** ge-001 (7x7), ge-002 (8x8), ge-003 (10x10)  
**Commands:** look, move <n/s/e/w>, status, restart, quit

---

## Package Contents

### 1. Game Brief

Grid Escape is the V1.8 game product — first AI-native game through the Claw Studio + Viper operating model. CLI-first, governed by PMO event routing and bounded command/control loop.

Full spec location: `\\192.168.31.124\Nova-Jarvis-Shared\working\gov_langgraph\V1.8\V1_8_SPEC.md`

### 2. Production Handoff Package

- `games/grid_escape.py` — top-level runner script (adds repo root to sys.path)
- `games/grid_escape/__main__.py` — CLI entry point with `_display_escaped` (tier display for player)
- `games/grid_escape/engine.py` — game engine with `_signal_escaped` (tier computation)
- `games/grid_escape/grids.py` — grid definitions (ge-001, ge-002, ge-003)
- `games/grid_escape/scoring.py` — `compute_tier(steps, optimal)` function

### 3. Build/Output Evidence

- `evidence/gameplay/M1_R2_EVIDENCE.md` — ge-001 and ge-002 completion logs
- `games/grid_escape/tests/` — 55 tests, all passing

### 4. PMO CLI Reference

- `governance/pmo/V1_8_PMO_CLI_REFERENCE.md` — full command reference
- `governance/pmo/V1_8_PMO_ACTION_INVENTORY.md` — action inventory

### 5. PMO Event Routing Evidence

- `evidence/routing/routing_proof_case.log` — routing decision trace (INTAKE→DETERMINE→ROUTE→RESOLVE→RELAY)
- `evidence/routing/control_loop_trace.log` — command/control loop trace (LAUNCH→INSPECT→PAUSE→INSPECT→INVOKE→TERMINATE→INSPECT)
- `governance/pmo/data/pmo_event_log.json` — live event log
- `governance/pmo/data/pmo_task_log.json` — live task log

### 6. Agent Seats Evidence

- `V1_8_AGENT_ROLES.md` — Planner and TDD role definitions, approved by Nova
- `evidence/governance/planner_trace.md` — Planner seat trace
- `evidence/governance/tdd_trace.md` — TDD seat trace
- `evidence/governance/handoff_chain_trace.md` — seat handoff chain

### 7. Claw <> Viper Handoff Evidence

- `handoff/evidence/handoff_001.md` — HANDOVER-001 (Claw→Viper, WI-003)
- `handoff/evidence/return_receipt_001.md` — RETURN-001 (Viper→Claw, real outputs delivered)

### 8. Closure Test (10 Foundation Questions)

Each question must be answered "yes" with specific evidence before V1.8 can be formally closed.

| # | Closure Question | Required Answer | Evidence |
|---|----------------|-----------------|---------|
| 1 | Is the game deliverable and demonstrably runnable? | YES | `python games/grid_escape.py --grid ge-001` runs; ge-001 and ge-002 completion logs in `evidence/gameplay/M1_R2_EVIDENCE.md` |
| 2 | Do all CLI commands work as specified? | YES | `look`, `move <n/s/e/w>`, `status`, `restart`, `quit` — 55 tests passing including command tests |
| 3 | Is the completion signal correctly formed and emitted? | YES | `ESCAPED|<steps>|<grid>|<ts>|<tier>` format; `_signal_escaped` in `engine.py`; `compute_tier` wired in |
| 4 | Are scoring tiers computed and displayed correctly? | YES | `compute_tier` in `scoring.py`; 5 tiers (PERFECT/EXCELLENT/GOOD/COMPLETED/OVERMOVED); tier displayed to player via `_display_escaped` in `__main__.py` |
| 5 | Do all 7 PMO CLI base commands function correctly? | YES | `governance/pmo/pmo_cli.py`; trace in `evidence/pmo_cli/pmo_cli_trace.log` |
| 6 | Does PMO event routing correctly classify and forward events? | YES | Routing rules in `pmo_cli.py`; trace in `evidence/routing/routing_proof_case.log`; live event log `governance/pmo/data/pmo_event_log.json` |
| 7 | Is the bounded command/control loop operational? | YES | 5 control commands (launch-subagent/pause-task/inspect-task/terminate-task/invoke-command); trace in `evidence/routing/control_loop_trace.log`; live task log `governance/pmo/data/pmo_task_log.json` |
| 8 | Are Planner and TDD seats instantiated and proven with live traces? | YES | `V1_8_AGENT_ROLES.md` (Nova approved); `evidence/governance/planner_trace.md`; `evidence/governance/tdd_trace.md`; `evidence/governance/handoff_chain_trace.md` |
| 9 | Was the Claw <> Viper handoff exercised with real cross-boundary outputs? | YES | WI-003 created via PMO CLI; Viper executed real code change; `handoff/evidence/handoff_001.md` + `return_receipt_001.md`; code changes in `engine.py` + `__main__.py` |
| 10 | Is the full evidence chain complete, linked, and accessible? | YES | This document references all evidence files; all 11 referenced files verified present in repo |

---

**V1.8 formally closed 2026-04-14T18:53 GMT+8 per Nova final approval.**  
Execution plan: `\\192.168.31.124\Nova-Jarvis-Shared\working\gov_langgraph\V1.8\V1_8_EXECUTION_PLAN.md` (v1.13)