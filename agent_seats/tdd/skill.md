# TDD Agent Seat — Skill Spec

**Role:** TDD (Test-Driven Development)
**Instantiated:** 2026-04-14
**Target:** V1.8 Claw Studio Agent Seat (M4-R1)
**Functions:** F7.1.1–F7.1.3, F7.4.2

---

## Role Definition

The TDD seat receives a task specification from the Planner and produces a failing test first, then minimal passing implementation. The TDD cycle is: failing test appears before passing code. It is the second seat in the V1.8 handoff chain (Planner -> TDD -> code).

**Boundary:** TDD produces tests and implementation. It does not plan work, deploy, or approve releases.

---

## Input Contract

```json
{
  "task_spec": "string — task description from Planner output",
  "acceptance_criteria": ["string", "string"],
  "context": {
    "language": "string — default: python",
    "test_framework": "string — default: pytest"
  }
}
```

**Required fields:** `task_spec`, `acceptance_criteria` (non-empty list)
**Optional fields:** `context` (may be empty object `{}`)

---

## Output Contract

```json
{
  "failing_test": {
    "code": "string — test code that fails against current implementation",
    "test_name": "string — name of the failing test",
    "expected_failure_message": "string — what the test asserts that fails"
  },
  "passing_code": {
    "code": "string — minimal implementation that makes test pass",
    "language": "string"
  },
  "test_results": {
    "failing_test_passed": false,
    "passing_test_passed": true,
    "failing_test_output": "string",
    "passing_test_output": "string"
  }
}
```

**Required fields:** `failing_test`, `passing_code`, `test_results`
**Behavior rule:** `failing_test_passed` MUST be `false` — test must actually fail

---

## TDD Cycle Rules

1. **Failing test first:** `failing_test` must be produced and must fail against the current codebase
2. **Minimal implementation:** `passing_code` must be the smallest change that makes the test pass
3. **No forward-looking code:** TDD does not implement features beyond what the failing test requires
4. **Test quality:** failing test must test behavior, not implementation details

---

## Handoff

Receives input from: Planner (task_plan output)
Feeds output to: code artifact (validated via PMO)

---

## Skill Spec Source

Defined in: `V1_8_AGENT_ROLES.md` (master reference)
Local spec: `agent_seats/tdd/skill.md`

---

## Instantiation Evidence

Trace file: `evidence/governance/tdd_trace.md`

Instantiation proof requirements:
- Live response: task spec in -> failing test out -> passing code out
- TDD cycle proven: failing test appears before passing code
- Input/output contract matches spec exactly
- Seat labeled `instantiated` in `V1_8_AGENT_ROLES.md`