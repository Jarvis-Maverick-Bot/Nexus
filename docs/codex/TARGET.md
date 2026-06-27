# Nexus Agent Coding Team Delivery Console Target

Date: 2026-06-27
Branch: `codex/edc-governance-desktop`
Internal PR: `EDC-PR-001`
Base: `origin/master` at `35e64b842ca41feacc97df8ca3c52e48fed72cf2`

## Branch Decision

This branch supersedes GitHub PR #22, `edc-governance-desktop: L1 Governance Desktop UAT`, whose head was `4797ae15a266878ec491fa04d701dea2f98497bc`.

GitHub PR #22 is recorded as `EDC-PR-000` and is not the new EDC delivery baseline. It added some local test-bridge code, but the dominant branch shape was evidence-heavy and display-only. The new branch starts from `origin/master` and defines the next product-oriented EDC target.

## Target Outcome

Build the first credible Nexus Agent Coding Team Delivery Console: a local-first project delivery workspace where human owners and Codex agents can plan, execute, validate, review, and close out software delivery work.

The target experience is:

1. Alex can open a Nexus desktop delivery workspace for a real local project.
2. The workspace shows backlog items, active runs, agents, branch/PR status, validation evidence, and UAT gates.
3. Codex Planning can create bounded Execution task cards with explicit scope, non-goals, file boundaries, validation commands, and write-back locations.
4. Codex Execution can work in isolated project worktrees, report changed files, validation evidence, blockers, branch state, and PR readiness.
5. Owner UAT remains a separate manual acceptance step and is never replaced by local automated checks.
6. EDC remains the engineering delivery control layer for scope, validation, PR mapping, and closeout; it is not a claim of production readiness.

## Success Definition

EDC success means a bounded project delivery path is demonstrably usable by the owner: a task can move from planning to isolated execution, validation, review, PR tracking, UAT decision intake, and closeout without relying on OpenClaw private context.

It does not mean production readiness, live dispatch, default-on runtime control, private agent invocation, deployment, external adoption, autonomous merge authority, or final product acceptance.

## Product Positioning

Nexus should become an Agent Coding Team tool, not only a governance evidence viewer.

Reference direction from Multica and SecondBrain-curated agent workflow notes:

- agents are assignable delivery teammates;
- work is represented by durable issues/tasks, not private chat memory;
- runtime execution and workspace isolation are explicit;
- agent progress, blockers, comments, and completion claims are visible;
- owner review and UAT are first-class gates.
- multi-agent fan-out requires a named reducer/final owner;
- parallel agent work requires editable-scope boundaries, handoff rules, and merge-order visibility;
- current task packets take priority over broad shared-brain retrieval.

Nexus should translate those product ideas into the existing Nexus architecture instead of copying Multica's stack.

The current reference intake is tracked in `docs/codex/SECOND_BRAIN_REFERENCE_MAP.md`. That map is advisory design input only; Nexus repo facts and Alex's current instruction remain authoritative.

## Superseded Material

The old GitHub PR #22 / `EDC-PR-000` branch may be mined for lessons only:

- useful references: local test state shape, command bridge idea, relevant desktop self-checks;
- do not carry forward wholesale: display-only panel sprawl, evidence package mass, closeout assertions, old EDC numbering, or UAT PASS language.

## Immediate Next Decision

Complete `EDC-PR-001` as a planning reset, then execute `EDC-PR-002` as the first implementation slice only after Alex confirms the revised target, scope, spec, and PR plan.
