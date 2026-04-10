# PMO Smart Agent — V1.5 PRD

**Product:** PMO Smart Agent  
**Feature:** V1.5 — Governance Surface + Internal Coordination Layer  
**Author:** Nova (CAO) for Alex  
**Date:** 2026-04-09 | Updated: 2026-04-10  
**Status:** DRAFT — updated per corrected governance model (2026-04-10)

---

## 1. Problem Statement

V1 proved a narrow PMO shell around governed task kickoff, status visibility, and gate confirmation.

However, V1 had architectural overreach in planning — assuming automated readiness engines and autonomous scheduling were required, when in fact:
- Alex / Jarvis assign tasks to Maverick
- Maverick coordinates internally and returns status
- Humans decide at intake and gates
- No automated readiness subsystem is required for V1.5

V1.5 exists to close the most important realism gap — status aggregation and human-readable project surface — without breaking the V1 governance boundary.

V1.5 establishes the first PMO governance surface + internal coordination layer where:
- Alex can initiate real projects in a multi-project environment
- PMO Web UI shows clear aggregated status per project
- Maverick coordinates known agents internally and returns coordination status
- BA -> SA -> DEV -> QA is the governed reference path
- Humans make go/no-go decisions at intake and gates (human-governed, not automated)
- Formal acceptance workflow with 6 required artifacts closes the loop

---

## 2. Goals

### 2.1 Success Metrics

| Metric | V1 Baseline | V1.5 Target | How We Measure |
|--------|-------------|-------------|----------------|
| Alex can initiate projects, not just tasks | No | Yes | Functional test |
| Platform shows project -> task -> stage relationship clearly | Partial | Yes | UI/API review |
| PMO Web UI shows aggregated project status from Maverick's coordination | No | Yes | Status surface review |
| BA -> SA -> DEV -> QA governed progression is visible as reference path | Partial | Yes | End-to-end test |
| Human-governed intake control (kickoff blocked without project selection) | Partial | Yes | Form-level enforcement test |
| Reporting includes required artifact outputs | No | Yes | Report output review |
| Acceptance workflow is expanded beyond simple gate action | No | Yes | Acceptance-flow test |
| Maverick coordinates agents internally and returns status | Logical only | Operationally visible | Architecture + coordination review |
| PMO stores zero independent authoritative governance truth | Yes | Must remain yes | Code / architecture audit |

### 2.2 Non-Goals

- Fully autonomous decision-making PMO
- Automated readiness-check subsystem (deferred to V2.0)
- Direct PMO → Maverick spawn without Telegram relay (V2.0 message middleware)
- Replacing human final decision authority
- Replacing Platform Core with PMO logic
- Collapsing governance, PMO, and advisory logic into one layer
- Shipping every future advisory/intelligence ambition in the first V1.5 slice

---

## 3. User Stories

- **As Alex**  
  I want to initiate a real project and see its governed delivery path  
  So PMO operation matches real project management rather than a narrow single-task shell

- **As Alex**  
  I want kickoff blocked without active project selection  
  So humans make go/no-go decisions at intake — not an automated engine

- **As Alex**  
  I want Maverick to coordinate known agents internally and return status  
  So coordination is visible and humans remain the decision authority

- **As Alex**  
  I want reporting that shows project progress, risks, blockers, and stage state  
  So I can manage delivery without reconstructing truth manually

- **As Alex**  
  I want acceptance workflow expansion beyond basic gate approval/rejection  
  So final delivery review has structure, evidence, and explicit completion logic

- **As Alex**  
  I want PMO to surface advisory signals from Maverick  
  So the system helps without quietly taking governance authority

- **As Alex**  
  I want the PMO layer to show clear aggregated status per project  
  So I can manage delivery through the PMO surface, not raw API calls

---

## 4. Requirements

### 4.1 Functional Requirements

1. PMO Smart Agent V1.5 shall support explicit project initiation as a first-class PMO action in a true multi-project model.
2. V1.5 shall support project-linked governed task creation and task progression inside each project.
3. V1.5 shall present BA -> SA -> DEV -> QA as a governed reference delivery path.
4. V1.5 shall enforce human-governed intake control: kickoff blocked without active project selection.
5. V1.5 shall provide expanded reporting through required artifact outputs: Scope, SPEC, Arch, Testcase, TestReport, and GuideLine.
6. V1.5 shall expand the acceptance workflow beyond the V1 gate-only surface using the same required artifact set.
7. V1.5 shall introduce Maverick as the internal coordination layer with explicit role and boundary.
8. V1.5 shall surface Maverick advisory signals (risk, schedule, stage) as non-blocking informational output.
9. V1.5 shall preserve Platform Core as the authoritative source of project, task, workflow, state, handoff, gate, and event truth.
10. V1.5 shall keep human final review and decision authority explicit at intake and gates.
11. V1.5 shall surface coordination status from Maverick to PMO Web UI for human review.

### 4.2 Edge Cases

| Case | Handling |
|------|----------|
| Project kickoff requested without active project selection | Kickoff form enforces project selection — human makes go/no-go decision |
| Project exists but tasks are incomplete or blocked | Reporting must show incomplete / blocked state clearly |
| Cross-stage progression attempted without required handoff/gate conditions | Platform Core rejects progression |
| Maverick unavailable | PMO must show coordination-layer unavailable state without fabricating outcomes |
| Acceptance package incomplete | Expanded acceptance workflow must block formal completion |
| Advisory output conflicts with human judgment | Human decision remains final and can override advice |

### 4.3 Explicitly Deferred / Out of First V1.5 Slice

- Full autonomous PM decision-making
- Full portfolio / program / multi-project governance suite
- Heavy permissions/multi-user enterprise model
- Deep predictive analytics layer
- Hidden recommendation-to-action automation without human confirmation

---

## 5. Design

### 5.1 Architecture

```
Alex ←→ PMO Smart Agent V1.5 (Web UI / API / PMO console)
                  ↓
             Maverick PMO Layer
                  ↓
        gov_langgraph Platform Core (authoritative truth)
                  ↓
     Workflow / State / Handoff / Gate / Event / Evidence surfaces
```

Core rule:
- PMO = operator-facing management and coordination surface
- Maverick = PMO coordination / analysis / orchestration layer
- Platform Core = authoritative governance and state layer

### 5.2 Routing

- **Primary:** Web UI / API PMO surface
- **Secondary:** tool-driven operator/control surface through OpenClaw integration
- **Future optional:** richer PM dashboards / messaging mirrors

### 5.3 Permission / Boundary Model

- Alex remains final human decision authority.
- Nova remains governance review / audit authority.
- Jarvis remains implementation and technical delivery authority.
- Maverick becomes the active PMO coordination layer in V1.5.
- Delivery roles BA / SA / DEV / QA remain delivery-stage actors.
- Advisory capability, if added, remains recommendation-only.

---

## 6. Dependencies

| Dependency | Owner | Status |
|------------|-------|--------|
| V1 frozen baseline | Completed | ✅ |
| V1 archive docs | Completed | ✅ |
| V1.5 scope and spec set | Nova | In progress |
| Maverick role/boundary agreement | Alex + Nova + Jarvis | Pending |
| V1.5 implementation plan | Nova/Jarvis | Pending |

---

## 7. Open Questions

| # | Question | Owner | Status |
|---|----------|-------|--------|
| 1 | Is first V1.5 slice single-project but project-first, or true multi-project from the start? | Alex / Nova / Jarvis | Resolved — true multi-project from the start |
| 2 | Should kickoff readiness block project creation, task activation, or both? | Alex / Nova / Jarvis | Resolved — readiness governs whether project + task are actually kicked off; if Alex decides to shut down, no project/task should be created |
| 3 | What minimum reporting outputs are mandatory for V1.5 acceptance? | Alex / Nova / Jarvis | Resolved — Scope, SPEC, Arch, Testcase, TestReport, GuideLine |
| 4 | What exact acceptance artifacts become mandatory in expanded acceptance workflow? | Alex / Nova / Jarvis | Resolved — same as mandatory reporting outputs: Scope, SPEC, Arch, Testcase, TestReport, GuideLine |
| 5 | What operational responsibilities Maverick owns directly in first V1.5 slice? | Alex / Nova / Jarvis | Resolved — Maverick coordinates known agents internally and returns status to PMO surface; spawn via Telegram relay (V2.0 = message middleware); implementation plan must cover status aggregation |
| 6 | Whether intelligent PM advisory is part of first V1.5 build or a separate later sub-slice? | Alex / Nova / Jarvis | Resolved — Option A under discussion: include advisory in V1.5 despite higher ambition and schedule risk |

---

## 8. V1.5 vs Future Phase

This PRD defines V1.5 direction only.

### In first V1.5 discussion scope
- true multi-project PMO framing from the start
- governed project/task linkage
- BA -> SA -> DEV -> QA visible reference scenario
- human-governed intake control (kickoff blocked without project selection)
- expanded reporting (Scope, SPEC, Arch, Testcase, TestReport, GuideLine)
- expanded acceptance workflow using required artifact set
- Maverick as internal coordination layer + status reporter
- advisory Option A (risk signals, schedule estimates, blockers) as non-blocking informational output
- PMO Web UI as primary governance/status surface

### Likely later than first V1.5 slice
- stronger autonomous intervention logic
- broad enterprise portfolio expansion beyond the initial multi-project foundation
- mature predictive planning package beyond first advisory scope
- fully mature enterprise reporting package beyond required baseline outputs

---

## 9. One-line Definition

**V1.5 is the PMO governance surface + internal coordination layer: Alex/Jarvis assign to Maverick, Maverick coordinates known agents internally and returns status, PMO Web UI aggregates and displays status, humans decide at intake/gates, BA->SA->DEV->QA is the governed reference path, Platform Core remains the sole authoritative governance/state layer, and advisory support is bounded and non-authoritative.****
