# PMO Smart Agent V1.5 — Architecture Overview

**Author:** Nova
**Date:** 2026-04-09 | Updated: 2026-04-10
**Status:** DRAFT — updated per corrected governance model (2026-04-10)

---

## Purpose

This document provides the canonical V1.5 architecture overview: the layer model, the split of responsibilities between PMO surface, Maverick PMO layer, and Platform Core, and the source-of-truth boundaries that must remain intact as V1.5 expands beyond V1.

---

## Authority Order in the V1.5 Draft Set

1. `V1_5_SPEC/STEP_1..STEP_7` — authoritative scope, boundary, acceptance, and constraint baseline
2. `PMO_SMART_AGENT_V1_5_PRD_V0_1.md` — product intent and scope framing
3. `V1_5_IMPLEMENTATION_PLAN_V0_1.md` — planned delivery path for V1.5
4. `V1_5_ARCHITECTURE_OVERVIEW_V0_1.md` — this top-level architecture explanation

---

## Layer Model

V1.5 is organized into 5 layers (from outer to inner):

```
Layer 1: PMO Operator Surface      — Web UI / API / control console (status display, human decisions)
Layer 2: Maverick Coordination Layer — internal coordination, status reporting, advisory signals
Layer 3: Harness / Integration     — state access, evidence access, event access, tool bridge
Layer 4: Platform Model            — governance objects, authority, state machine, acceptance objects
Layer 5: Workflow Engine           — BA / SA / DEV / QA progression and execution
```

---

## Source of Truth Boundary

**Authoritative truth remains inside Platform Core / governed layers:**
- project
- task
- workflow
- task state
- handoff
- gate
- event
- acceptance state

**PMO / Maverick do not own independent governance truth.**
They coordinate, display, synthesize, and assist. Humans decide at intake/gates.

---

## Responsibility Split

### PMO Operator Surface
Owns:
- operator visibility
- review/control entry
- reporting display
- readiness display
- acceptance display

### Maverick Coordination Layer
Owns:
- Internal coordination of known agents (executes assigned coordination)
- Status reporting back to PMO surface
- Reporting synthesis
- Acceptance-package coordination
- Advisory support (non-blocking, informational only)

### Platform Core
Owns:
- governance truth
- authority enforcement
- workflow rules
- gate logic
- acceptance logic
- readiness truth where modeled

### Workflow Engine
Owns:
- stage execution behavior
- BA -> SA -> DEV -> QA progression logic
- execution routing

---

## Main V1.5 Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| True multi-project PMO expansion from the start | closes V1 single-project limitation |
| PMO Web UI becomes the primary governance surface | makes status visible and human-decisions accessible |
| Maverick is internal coordinator + status reporter | not autonomous scheduler — humans remain decision authority |
| Human-governed intake control (kickoff blocked without project) | no automated readiness engine in V1.5 |
| BA→SA→DEV→QA is the governed reference path | canonical delivery shape, not flexible orchestration |
| Reporting/acceptance added as structured capabilities | closes major deferred V1 gaps |
| Platform Core remains source of truth | prevents PMO/Maverick drift into hidden backend |
| Advisory remains bounded and non-blocking | informational only, no authority |
| Spawn via Telegram relay — message middleware deferred to V2.0 | clean V1.5 scope boundary |

---

## One-line Definition

**V1.5 architecture expands V1 into a multi-project PMO governance surface + internal coordination layer: Alex/Jarvis assign to Maverick, Maverick coordinates known agents internally and returns status, PMO Web UI aggregates and displays status, humans decide at intake/gates, BA→SA→DEV→QA is the governed reference path, Platform Core remains the only authoritative governance/state layer, and advisory support is bounded and non-authoritative.****
