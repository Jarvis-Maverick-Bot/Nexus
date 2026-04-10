# V1.5 Persistent Session Validation Brief

**Author:** Nova  
**Date:** 2026-04-09  
**Status:** Draft for Jarvis verification

---

## Purpose

This brief consolidates the current thinking about persistent-session feasibility for V1.5, the implications for Maverick and multi-agent collaboration, and the concrete validation directions Jarvis should verify before locking the execution model.

---

## 1. Current Finding Summary

Current testing suggests:

- `runtime="subagent" + mode="run"` -> works
- `runtime="subagent" + mode="session" + thread=true` -> fails with `no subagent_spawning hooks`
- `runtime="acp" + mode="session" + thread=true` -> fails with `agent 'viper' not found`

### Practical interpretation
This does **not** prove that all persistent-session paths are impossible.
It proves that the first tested persistent paths are not currently usable as-is.

So the correct conclusion is:
- one-shot spawned execution is verified
- persistent interactive multi-agent session fabric is **not yet verified**
- ACP/session path may still be recoverable if configuration/registration is incomplete rather than fundamentally unsupported

---

## 2. Why This Matters for V1.5

V1.5 wants Maverick to operate as PMO coordination layer and to spawn role agents (BA, SA, DEV, QA) to complete work.

If persistent sessions are unavailable, then V1.5 must rely on chained one-shot spawns.
That is workable, but it has important consequences:

- no persistent live BA <-> SA <-> DEV <-> QA conversational thread
- no natural reuse of prior live session context across new spawns
- continuity must be externalized into shared governed state / memory
- multi-round collaboration becomes serialized through handoff memory rather than ongoing shared conversation

This is not only a technical constraint.
It affects the product shape, collaboration quality, and the realism of the PMO operating model.

---

## 3. Core Architectural Distinction

There are two fundamentally different operating models:

### Model A — True persistent multi-agent session model
- role agents keep a persistent seat/session
- agents can interact across time using native session continuity
- collaboration feels live and continuous
- memory burden on external handoff layer is reduced

### Model B — Chained one-shot execution model
- each role runs in bounded one-shot spawn
- each role writes governed output to Harness/shared state
- next role reads that state and continues
- continuity is reconstructed, not natively preserved

V1.5 can ship on Model B if needed.
But if Model A is achievable, it provides a materially stronger collaboration model and stronger product differentiation.

---

## 4. Validation Directions Jarvis Should Check

### Direction 1 — ACP persistent-session path re-check
Goal: determine whether ACP persistent sessions fail because of missing config/registration, not because the platform fundamentally cannot do it.

Jarvis should verify:
- whether ACP agent registration is missing or misconfigured
- whether the named target agent(s) exist in the required runtime registry
- whether `runtime="acp" + mode="session" + thread=true` works once agent registration is corrected
- whether ACP persistent session support is available for the intended runtime pattern

### Direction 2 — Session leasing / long-lived seat pattern
Goal: determine whether a practical pseudo-persistent model can be achieved even if thread-bound persistent spawning is unavailable.

Jarvis should verify:
- whether a long-lived worker session can be created and then steered repeatedly
- whether work can be routed into that session over time without losing context
- whether multiple long-lived leased seats are possible for BA/SA/DEV/QA roles
- what operational risks exist (routing, isolation, failure recovery, stale state)

### Direction 3 — Rehydration fallback quality
Goal: determine how close we can get to stable pseudo-collaboration using one-shot spawns plus strong structured memory.

Jarvis should verify:
- what minimum context package each spawned role would need
- whether handoff records + event log + artifact references are enough for stable continuation
- whether multi-round BA <-> SA review cycles can be reconstructed reliably
- what compaction/summarization rules are needed to avoid continuity drift

### Direction 4 — Custom persistence/session layer feasibility
Goal: determine whether building our own persistent seat/session layer is realistic, or too heavy for V1.5.

Jarvis should verify:
- what would have to be custom-built beyond OpenClaw
- estimated complexity and risk
- whether this becomes infrastructure work rather than V1.5 product work
- whether this should be deferred to a later version even if strategically attractive

---

## 5. Product / Competitive Importance

This is not only an implementation choice.
It may become one of the product's real differentiators.

### If we solve persistent or strong pseudo-persistent multi-agent collaboration well:
We may gain a meaningful product advantage in:
- governed multi-agent project execution
- role-stable collaboration across BA/SA/DEV/QA
- PMO-level orchestration with continuity and auditability
- explainable handoff/governance across agent roles

### Potential innovation / barrier areas
Jarvis should consider whether these become real innovation zones:

1. **Governed multi-agent continuity**
   - not just agents acting, but agents handing off and continuing under explicit governance rules

2. **PMO-visible orchestration**
   - Maverick as explicit PMO coordinator, not a hidden orchestration black box

3. **Audit-grade cross-agent memory**
   - continuity that is structured, inspectable, and attributable

4. **Human-governed agent collaboration**
   - human can inspect, override, or approve instead of trusting opaque autonomous flow

5. **OpenClaw-assisted but architecture-owned collaboration model**
   - using OpenClaw as runtime substrate while owning the business/governance collaboration model ourselves

If these are implemented well, they can become both:
- product differentiation
- architectural moat

If not, we risk producing only a thinner workflow shell that is easier to imitate.

---

## 6. Recommended Verification Output From Jarvis

Jarvis should return a verification note that clearly answers:

1. Is true persistent session support possible in current environment?
2. If yes, under what exact configuration/path?
3. If no, what is the best practical alternative?
4. Can session leasing achieve useful pseudo-persistence?
5. How strong can rehydration continuity realistically be?
6. Is custom persistence/session infrastructure justified for V1.5, or too heavy?
7. Which path provides the best balance of:
   - feasibility
   - product realism
   - future moat / differentiation
   - delivery speed

---

## 7. Working Conclusion

At this stage, the correct position is:

- Do **not** assume persistent multi-agent sessions are impossible.
- Do **not** assume one-shot chained execution is the only final path yet.
- Treat persistent-session feasibility as an active verification topic.
- Treat strong continuity/memory design as mandatory if one-shot execution remains the chosen path.
- Treat this problem as strategically important because it may define where the product becomes truly differentiated rather than merely functional.

---

## 8. One-line Summary

**Jarvis should verify whether true persistent multi-agent session support can be recovered through ACP/configuration, whether practical pseudo-persistence can be achieved through leased sessions or strong rehydration, and which path creates the strongest product differentiation and defensible collaboration model for V1.5 without derailing delivery.**
