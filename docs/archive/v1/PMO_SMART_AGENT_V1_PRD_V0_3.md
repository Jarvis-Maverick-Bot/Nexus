# PMO Smart Agent — V1 PRD

**Product:** PMO Smart Agent  
**Feature:** V1 — Core Governance Interface  
**Author:** Nova (CAO) for Alex  
**Date:** 2026-04-07  
**Status:** FINAL — Corrections applied 2026-04-08

---

## 1. Problem Statement

Alex needs a direct control surface for the gov_langgraph governance pipeline — a way to view workitem status, confirm gates, and announce kickoffs — without logging into the platform directly or relying on a human assistant.

Currently:
- gov_langgraph owns all authoritative pipeline state
- There is no clean interface for Alex to interact with it as an operator
- The PMO Smart Agent V2 (previous attempt) tried to do too much and created a data ownership mess

This PRD defines V1: a narrow, disciplined interface that treats gov_langgraph as the single source of truth and PMO Smart Agent as a read/write shell around it.

---

## 2. Goals

### 2.1 Success Metrics

| Metric | Baseline | Target | How We Measure |
|--------|----------|--------|----------------|
| Alex can view any active workitem state | Manual check via logs | Single UI action | Functional test |
| Alex confirms gate → pipeline advances | Manual intervention | One API call | E2E test |
| Alex announces kickoff → workitem enters INTAKE | Manual creation | One API call | E2E test |
| PMO stores zero authoritative data | N/A | Zero copies | Code audit |
| V1 scope creep | N/A | Zero unauthorized expansions | Change log |

### 2.2 Non-Goals

- Multi-user support (V1: Alex only)
- Local database or offline mode
- Full project reports (risks, issues, solutions, impact analysis — future phase)
- Intelligent PM feedback / decision support (future phase)
- Governance rule configuration UI (configured in gov_langgraph directly)
- Artifact upload or management
- Non-Alex user management

---

## 3. User Stories

- **As Alex**  
  I want to see all active workitems and their current pipeline stage  
  So I can understand project health without asking an assistant

- **As Alex**  
  I want to formally confirm a governance gate after reviewing evidence  
  So the pipeline advances with my explicit approval on record

- **As Alex**  
  I want to formally reject a gate with a documented reason  
  So work halts with a clear record of why and what needs fixing

- **As Alex**  
  I want to announce a new project kickoff  
  So new work enters the governed pipeline from the start

---

## 4. Requirements

### 4.1 Functional Requirements

1. PMO Smart Agent shall display all active workitems with: task_id, title, current stage, owner, gate status (pending/passed/rejected/N/A)
2. PMO Smart Agent shall display a single workitem's full detail: stage, owner, gate statuses, last updated, blocker (if any)
3. PMO Smart Agent shall allow Alex to confirm a governance gate via explicit action (button + confirmation)
4. PMO Smart Agent shall allow Alex to reject a gate with a required free-text reason
5. PMO Smart Agent shall create a new workitem at INTAKE stage upon kickoff announcement (title, description, priority, owner)
6. PMO Smart Agent shall show a clear error state when gov_langgraph is unreachable — no stale data, no retry
7. PMO Smart Agent shall display evidence summary for each gate before Alex makes a confirm/reject decision
8. PMO Smart Agent shall disable confirm button for workitems already at terminal state
9. PMO Smart Agent shall return an error on double-confirm attempt — no silent overwrite

### 4.2 Edge Cases

| Case | Handling |
|------|----------|
| gov_langgraph unreachable | Show "Platform unavailable" error. No stale data. No retry. |
| Workitem at terminal state | Confirm button disabled. UI shows "Already completed/closed". |
| Workitem blocked | Status view shows blocked clearly. Kickoff still available. |
| Double confirm attempt | Return error. No silent overwrite. |
| Reject without reason | Form validation requires reason before submit. |
| Evidence incomplete | Display "Evidence pending" note. Does not block Alex's decision. |

### 4.3 Not in Scope

- Telegram as primary interface (web UI is primary; Telegram is secondary mirror for read-only status checks)
- Multi-user auth or permissions beyond Alex
- Project reports (progress, risks, issues, solutions)
- Acceptance workflow with artifact review
- Intelligent feedback from Maverick
- Doc readiness check before kickoff
- Gate evidence drafting (produced by BA/Jarvis roles, PMO displays only)

---

## 5. Design

### 5.1 Architecture

```
Alex ←→ PMO Smart Agent (Web UI / API)
              ↓ read/write
         gov_langgraph (authoritative state)
              ↓
         EvidenceStore + StateStore + EventJournal
```

PMO Smart Agent is a shell. It has no local database. All state flows through gov_langgraph.

### 5.2 Routing

- **Primary:** Web UI (port configurable, default 8000 or 3000 — Jarvis confirms)
- **Secondary:** Telegram — same-session desirable, web-first if not feasible (SA to verify feasibility)

### 5.3 Permission Model

PMO Smart Agent operates at the **Governance Layer** — higher than Maverick.

The PMO V1 permission model has two levels:

**PMO V1 operator surface (this PRD):**
- Alex is the only intended PMO V1 product operator
- Nova exercises governance review, audit, and intervention authority when required
- Nova is NOT a routine PMO V1 operator — governance involvement is event-driven

**Broader authority model (gov_langgraph):**
- The full role-based authority model (ALEX, NOVA, JARVIS, MAVERICK, VIPER_*) lives in gov_langgraph Platform Core
- PMO V1 is an Alex-facing interface into that system
- gov_langgraph enforces authority boundaries; PMO V1 does not re-implement them
- See `WEEK5_TRACK2_PERMISSION_MATRIX.md` for the complete authority cross-reference

---

## 6. Dependencies

| Dependency | Owner | Status |
|------------|-------|--------|
| gov_langgraph V1 complete | Jarvis | ✅ Done |
| gov_langgraph read/write API | Jarvis | ✅ Done |
| PMO Smart Agent V1 PRD (this doc) | Alex + Nova | ✅ Approved — 2026-04-08 |
| Telegram ↔ Web UI same-session feasibility | Jarvis | ✅ Resolved — Web UI chosen, Telegram secondary |

---

## 7. Open Questions

| # | Question | Owner | Status |
|---|----------|-------|--------|
| 1 | Telegram ↔ Web UI same-session: feasible? | Jarvis | ✅ Resolved — Web UI primary, Telegram secondary |
| 2 | Port: 8000 or 3000? | Jarvis | ✅ Resolved — 8000 |

---

## 8. Resolution Log (Previously Open)

| Question | Answer |
|----------|--------|
| Telegram routing | Web UI primary. Telegram secondary mirror. Same-session desirable, web-first if conflict. |
| Port | Configurable. Default 8000 or 3000. Jarvis confirms. |
| Evidence format | Drafted by BA/Jarvis role. PMO displays only. |
| Owner model | gov_langgraph owns authoritative state. PMO mirrors only — no local DB. |
| Permission matrix | PMO V1 is Alex-facing. Broader authority boundaries enforced in gov_langgraph Platform Core — not reduced to "Alex + Nova only" here. |

---

## 9. V1 vs Future Phase

This PRD defines V1 only. The following are **future phase** — not included in V1 scope:

| Future Phase Item | Description |
|-------------------|-------------|
| Intelligent PM feedback | Maverick understands project context and provides proactive decision support |
| Full project reports | Progress, risks, issues, solutions, change requests, impact analysis |
| Acceptance workflow | User guide review, test report review, formal acceptance artifact checklist |
| Kickoff readiness check | Verify scope/spec/plan/test cases / use cases are ready before kickoff |
| Multi-user support | Non-Alex users with role-based permissions |
| Desktop client | Native desktop app alongside web UI |

---

## 10. Approval

| Role | Name | Decision | Date |
|------|------|---------|------|
| Alex (Owner) | Alex Lin | ✅ Approved | 2026-04-08 |
| Nova (CAO) | Nova | ✅ APPROVED — §10 signed | 2026-04-08 |
| Tech Lead | Jarvis | ✅ Signed off | 2026-04-08 |
