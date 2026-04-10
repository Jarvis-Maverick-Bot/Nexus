# V1.5 Direction Sync Summary for Jarvis

**Author:** Nova  
**Date:** 2026-04-09  
**Status:** For Jarvis sync and plan revision

---

## 1. Why this summary exists

This note consolidates the current Alex <-> Nova alignment on the real direction of V1.5, the document corrections already made, and the persistent-session validation direction that Jarvis should verify before locking the next implementation path.

Jarvis should use this as the sync reference before updating `V1_5_IMPLEMENTATION_PLAN_V0_1.md`.

---

## 2. Core V1.5 direction, now clarified

V1.5 is **not** just a project-first PMO enhancement.

The true center of gravity is:

- the PMO layer, via Maverick, must gain the ability to **flexibly schedule known agents**
- this is the first step away from the current **rigid, fixed pipeline** model
- BA -> SA -> DEV -> QA remains an important **governed reference path**, but it is **not** the only intended orchestration model
- this is the first real foundation for:
  - autonomous coordination
  - adaptive operation
  - self-diagnosis

So V1.5 should now be understood as:

**the first flexible PMO orchestration layer over known agents, built on top of the frozen governed core**

---

## 3. Requirements Alex has now made explicit

### 3.1 Multi-project requirement
- V1.5 must support **true multi-project from the start**
- it must not be a disguised single-project wrapper

### 3.2 Kickoff readiness rule
- kickoff readiness must govern whether actual project/task kickoff happens
- if Alex decides to shut a project down, then no real project/task kickoff should occur
- if Alex says go kickoff, then project + task are created for execution

### 3.3 Mandatory reporting outputs
These are now mandatory V1.5 outputs:
- Scope
- SPEC
- Arch
- Testcase
- TestReport
- GuideLine

### 3.4 Mandatory acceptance artifacts
Expanded acceptance workflow must use the same required artifact set:
- Scope
- SPEC
- Arch
- Testcase
- TestReport
- GuideLine

### 3.5 Maverick first-slice ownership
Maverick’s first direct operational responsibility is:
- **spawn/schedule known agents to finish work**

Important:
- OpenClaw integration should be the **first-class agent creation/spawn path**
- manual agent creation must **not** become the primary operating model
- implementation plan should explicitly cover this

### 3.6 Advisory direction
Advisory Option A remains in active discussion:
- Maverick may provide PM advice such as:
  - risk signals
  - schedule estimates
  - blocker signals
- but it remains bounded and non-authoritative
- it increases ambition and schedule risk, so should be treated carefully

### 3.7 Core boundary rule
- Platform Core remains the authoritative source of truth
- PMO/Maverick must not become hidden governance truth
- human final decision authority remains explicit

---

## 4. Nova’s re-evaluation result on the current V1.5 docs

Nova reviewed the generated docs against Alex’s clarified direction.

### Verdict
The earlier V1.5 draft set was **partially aligned**, but **not fully aligned**.

### Main mismatch found
The docs were still too centered on:
- project-first PMO expansion
- BA -> SA -> DEV -> QA as the dominant shape

But Alex’s real direction is centered on:
- flexible scheduling of known agents by PMO/Maverick
- breaking out of rigid pipeline operation
- establishing the first foundation for autonomous coordination and self-diagnosis

That mismatch has already been corrected in the revised docs listed below.

---

## 5. Documents already revised by Nova

Updated:
- `PMO_SMART_AGENT_V1_5_PRD_V0_1.md`
- `V1_5_SPEC/STEP_1_V1_5_SCOPE_BOUNDARY_V0_1.md`
- `V1_5_SPEC/STEP_4_V1_5_AUTHORITY_RULES_V0_1.md`
- `V1_5_SPEC/STEP_5_V1_5_PLATFORM_CORE_VS_PMO_MAVERICK_BOUNDARY_V0_1.md`
- `V1_5_SPEC/STEP_6_V1_5_ACCEPTANCE_CRITERIA_V0_1.md`
- `V1_5_ARCHITECTURE_OVERVIEW_V0_1.md`
- `V1_5_IMPLEMENTATION_PLAN_V0_1.md`

---

## 6. Key corrections already made in those docs

### 6.1 PRD reframing
The PRD is no longer centered only on project-centric PMO enhancement.
It now frames V1.5 as:
- **Flexible PMO Orchestration Over Known Agents**

### 6.2 BA -> SA -> DEV -> QA repositioning
This path is now described as:
- a governed **reference path**
- not the only orchestration model

### 6.3 Flexible scheduling elevated to first-class requirement
The docs now explicitly state that V1.5 must:
- make flexible scheduling of known agents a first-class PMO capability
- allow Maverick to coordinate based on project/task/state/need/blocker context

### 6.4 Maverick boundary tightened
Maverick is now explicitly described as:
- PMO coordination layer
- flexible scheduler of known agents
- advisory layer where applicable

But not:
- final governance authority
- source of truth
- hidden backend control layer

### 6.5 Acceptance criteria corrected
Acceptance now requires proof of:
- flexible scheduling of known agents
- not only the workflow reference path
- required reporting outputs
- required acceptance artifacts

### 6.6 Implementation plan corrected
The current implementation plan draft now reflects this build priority more clearly:
1. multi-project model
2. Maverick scheduling core
3. OpenClaw integration
4. workflow surface
5. readiness
6. reporting
7. acceptance
8. advisory
9. self-diagnosis foundation

### 6.7 Explicit watchpoint added
The docs now explicitly warn against:
- quietly collapsing back into a disguised rigid pipeline

---

## 7. Persistent-session validation brief Jarvis must sync with

Reference file:
- `V1_5_PERSISTENT_SESSION_VALIDATION_BRIEF_V0_1.md`

This note must be read together with the implementation plan, because session continuity may materially shape the architecture.

### 7.1 Current tested findings
- `runtime="subagent" + mode="run"` works
- `runtime="subagent" + mode="session" + thread=true` fails with `no subagent_spawning hooks`
- `runtime="acp" + mode="session" + thread=true` fails with `agent 'viper' not found`

### 7.2 Correct interpretation
This does **not** prove that all persistent-session paths are impossible.
It proves that the first tested persistent paths are not usable as-is.

So the current conclusion should be:
- one-shot spawned execution is verified
- persistent interactive multi-agent session fabric is **not yet verified**
- ACP/session path may still be recoverable if config/registration is incomplete rather than fundamentally unsupported

### 7.3 Why this matters
If persistent sessions are unavailable, then V1.5 falls back to chained one-shot spawns.
That is workable, but causes:
- no persistent live BA <-> SA <-> DEV <-> QA conversational thread
- no natural reuse of prior live session context across new spawns
- continuity must be externalized into shared governed state / memory
- multi-round collaboration becomes serialized through handoff memory rather than ongoing shared conversation

### 7.4 Two operating models to compare

#### Model A — True persistent multi-agent session model
- role agents keep persistent seats/sessions
- agents interact across time using native session continuity
- collaboration feels live and continuous

#### Model B — Chained one-shot execution model
- each role runs in bounded one-shot spawn
- each role writes governed output to Harness/shared state
- next role reads that state and continues
- continuity is reconstructed, not natively preserved

### 7.5 Validation directions Nova wants Jarvis to verify

#### Direction 1 — ACP persistent-session path re-check
Verify:
- whether ACP agent registration is missing or misconfigured
- whether named target agents exist in the required runtime registry
- whether `runtime="acp" + mode="session" + thread=true` works once registration is corrected
- whether ACP persistent session support is actually available for intended pattern

#### Direction 2 — Session leasing / long-lived seat pattern
Verify:
- whether a long-lived worker session can be created and steered repeatedly
- whether multiple long-lived leased seats are possible for BA/SA/DEV/QA roles
- routing / isolation / failure-recovery risks

#### Direction 3 — Rehydration fallback quality
Verify:
- what minimum context package each spawned role would need
- whether handoff records + event log + artifact references are enough
- whether multi-round BA <-> SA review cycles can be reconstructed reliably
- what compaction/summarization rules are needed to avoid continuity drift

#### Direction 4 — Custom persistence/session layer feasibility
Verify:
- what must be built beyond OpenClaw
- complexity/risk
- whether this becomes infrastructure work rather than V1.5 product work
- whether it should be deferred even if strategically attractive

### 7.6 Why this matters strategically
This problem may become a real differentiation / moat area if solved well, especially in:
- governed multi-agent continuity
- PMO-visible orchestration
- audit-grade cross-agent memory
- human-governed agent collaboration
- OpenClaw-assisted but architecture-owned collaboration model

---

## 8. What Jarvis should do next

Jarvis should now:

1. review the revised V1.5 docs in the shared folder
2. sync to the corrected direction above
3. review the persistent-session validation brief carefully
4. update `V1_5_IMPLEMENTATION_PLAN_V0_1.md` accordingly
5. keep these principles explicit in the revised plan:
   - flexible scheduling of known agents is the centerpiece
   - rigid pipeline is reference path only
   - persistence/session feasibility remains an active validation topic
   - if fallback is one-shot execution, continuity/memory design becomes architectural, not optional
   - OpenClaw integration remains first-class, but product architecture must remain ours

---

## 9. One-line summary

**V1.5 should now be treated as the first flexible PMO orchestration layer over known agents in a true multi-project governed environment, with Maverick scheduling as the centerpiece, rigid pipeline reduced to a reference path, and persistent-session feasibility treated as a strategically important open validation topic before the implementation plan is finalized.**
