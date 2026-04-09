# STEP_7_V1_TECHNICAL_CONSTRAINTS_V0_1

**Step:** 7
**Version:** V0_1
**Status:** Draft for discussion with Jarvis
**Purpose:** Freeze Step 7 of the implementation-ready framework: V1 technical constraints.

---

## 1. Core purpose

V1 technical constraints define the implementation limits and assumptions Jarvis must respect while building V1.

They are intended to keep implementation:
- fast enough to deliver
- realistic enough to run
- disciplined enough to preserve architecture
- honest about current runtime/tooling reality

---

## 2. Constraint A — Current runtime base

V1 must use the **current OpenClaw mechanism** as the execution/coordinator base.

This means:
- no new runtime layer should be invented first
- no multi-instance orchestration should be required for V1
- V1 should be implementable with current OpenClaw capabilities
- Jarvis main session acts as the current coordination center for V1 delivery

---

## 3. Constraint B — No architecture dead-end hardcoding

V1 may narrow business scope, but must not hardcode architecture into a dead end.

This means:
- workflow must not exist only as invisible code branching
- platform objects must not be replaced by one-off ad hoc structures
- PMO_SMART_AGENT must not become the hidden real governance engine
- V1 shortcuts must not destroy future extensibility

So:
- narrow scope is allowed
- dead-end structure is not allowed

---

## 4. Constraint C — Platform Core remains the system of record

Platform Core must remain the single governed system of record in V1.

This applies to:
- project truth
- task truth
- workflow context
- task state
- handoff
- gate
- event

PMO_SMART_AGENT may display, query, suggest, and trigger actions, but it must not become an independent parallel truth owner.

---

## 5. Constraint D — Boundary remains hard by default

Platform Core vs PMO_SMART_AGENT boundary must remain hard by default.

If any exception is needed for implementation speed, it must be:
- explicitly identified
- explicitly discussed
- explicitly accepted

No silent mixing for convenience.

---

## 6. Constraint E — Governance truth must survive runtime simplification

Logical governance truth must be preserved even if runtime implementation is simplified.

Examples:
- Maverick remains logically part of the Management Layer authority
- V1 does not require full Maverick runtime participation
- role/governance truth must not be erased just because current runtime is simplified

This prevents implementation reality from rewriting governance design.

---

## 7. Constraint F — Action enforcement must respect frozen rules

Implementation must respect the frozen action and authority model.

This means:
- action behavior must align with Step 3
- action eligibility must align with Step 4
- gate/handoff/state logic must not bypass those rules through convenience coding

Jarvis should implement from the frozen model, not improvise a second one in code.

---

## 8. Constraint G — Visibility must come from structured state, not memory alone

V1 visibility must rely on structured governed records, not only chat/session memory.

This means:
- current status must come from Platform Core data/state
- blocker visibility must come from structured task state / events
- handoff/gate visibility must come from real governed records
- PMO_SMART_AGENT should not depend on narrative reconstruction alone

This is necessary if V1 is to be truly visible and auditable.

---

## 9. Constraint H — Optional items remain optional

Items intentionally out of V1 scope must not become hidden mandatory scope.

Examples:
- multi-instance orchestration
- full Maverick runtime independence
- full Skill/Agent/Team platform model
- heavy confidentiality partitioning
- full event framework infrastructure
- complete multi-domain generalization

If Jarvis needs one of these, it must be raised explicitly as a scope discussion.

---

## 10. Constraint I — Implementation should favor practical demonstrability

V1 should be built to demonstrate governed operation clearly, not to maximize architectural cleverness.

Meaning:
- prefer simpler implementable structure over elegant but unproven abstraction
- prefer governed visibility over hidden complexity
- prefer explicit records over implicit behavior

This protects V1 from overengineering.

---

## 11. One-line frozen definition

**V1 must be implemented on top of the current OpenClaw execution/coordinator mechanism, with Jarvis main session as the current coordination center, Platform Core as the single governed system of record, PMO_SMART_AGENT as a separate operator-facing surface, frozen action/authority rules respected, and no implementation shortcut allowed to hardcode V1 into a future architectural dead end.**
