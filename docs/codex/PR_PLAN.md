# Nexus Agent Coding Team Delivery PR Plan

Date: 2026-06-27
Branch: `codex/edc-governance-desktop`

## Numbering Rule

Internal delivery sequence uses `EDC-PR-###`.

GitHub PR numbers are external identifiers assigned by GitHub and must be recorded as mappings. Do not use GitHub PR numbers as the internal delivery order.

## Current PR State

- GitHub PR #22 is closed as superseded by this branch.
- This branch starts from `origin/master`, not from PR #22.
- Draft GitHub PR #27 is open for this branch after Alex confirmed this PR plan.

## PR Mapping

| Internal PR | GitHub PR | Branch | Purpose | Status |
| --- | ---: | --- | --- | --- |
| `EDC-PR-000` | #22 | `codex/4.21-real-testproject-e2e-uat` | Superseded L1 Governance Desktop UAT attempt | Closed / superseded |
| `EDC-PR-001` | #27 | `codex/edc-governance-desktop` | Planning reset for Agent Coding Team Delivery Console | Draft PR open |
| `EDC-PR-002` | #28 | `codex/edc-pr-002-delivery-domain-contracts` | Delivery domain contracts | Draft PR open |
| `EDC-PR-003` | TBD | `codex/edc-pr-003-codex-handoff-loop` | Codex execution handoff loop | Implementation in review |
| `EDC-PR-004` | TBD | TBD | Desktop delivery board MVP | Planned |
| `EDC-PR-005` | TBD | TBD | Owner UAT closeout | Planned |

## Proposed PR Sequence

### EDC-PR-001: Planning Reset

Goal: establish the Agent Coding Team Delivery Console target, scope, spec, and PR plan.

Expected files:

- `AGENTS.md`
- `docs/codex/TARGET.md`
- `docs/codex/SCOPE.md`
- `docs/codex/SPEC.md`
- `docs/codex/UX_SPEC.md`
- `docs/codex/PR_PLAN.md`
- `docs/codex/SECOND_BRAIN_REFERENCE_MAP.md`

Validation:

```powershell
git diff --check
```

Acceptance:

- target, scope, spec, and PR plan describe Nexus as an Agent Coding Team Delivery Console;
- internal numbering uses `EDC-PR-###`;
- Shared Docs and SecondBrain are documented as reference sources, not delivery authorities;
- selected SecondBrain action values are mapped to Nexus design constraints;
- Figma UX intent is captured in `docs/codex/UX_SPEC.md` as a durable repo spec;
- no product source, dependency, runtime, evidence cleanup, or branch mutation is included.

Exit: Alex confirms or revises this plan.

### EDC-PR-002: Delivery Domain Contracts

Goal: define the minimal durable model for project delivery work.

Expected files:

- `nexus/governance/**`
- `nexus/governance/tests/**`
- `docs/codex/**` if task card templates need adjustment

Acceptance:

- delivery project, work item, agent, assignment, run, validation, PR mapping, and UAT state are represented by named contracts;
- contracts reject missing task-card fields and unsafe file/worktree boundaries;
- contracts include source-authority, reducer-owner, blocked-state, and evidence-before-claim fields where relevant;
- tests cover status transitions and evidence-before-claim rules.

Validation:

```powershell
python -m pytest nexus/governance/tests
```

### EDC-PR-003: Codex Execution Handoff Loop

Goal: make Planning-to-Execution handoff and Execution-to-Planning completion reports durable.

Expected files:

- `docs/codex/**`
- `nexus/governance/**`
- `nexus/governance/tests/**`
- scripts only if explicitly needed for local non-runtime validation

Acceptance:

- Planning can emit a complete task card from a work item;
- Execution can write back changed files, validation commands, command results, blockers, and PR readiness;
- runtime startup and dependency installation remain blocked unless explicitly authorized;
- stale or missing validation evidence is visible as incomplete.
- cross-agent handoffs use bounded packets, evidence references, checkpoints, and output contracts rather than unbounded conversation state.

Validation:

```powershell
python -m pytest nexus/governance/tests
```

### EDC-PR-004: Desktop Delivery Board MVP

Goal: turn the desktop client into the first visible Agent Coding Team console.

Expected files:

- `apps/l1gov-desktop-client/src/**`
- `apps/l1gov-desktop-client/scripts/**`
- `apps/l1gov-desktop-client/src-tauri/src/**` if desktop commands are required
- `nexus/governance/**` and tests if contracts change

Acceptance:

- desktop shows backlog/work items, active runs, agents, validation/evidence, branch/PR mapping, and UAT state;
- fixture/reference data is clearly distinguished from active delivery state;
- blocked actions are visibly blocked rather than silently absent;
- reducer ownership, editable scope, lock/handoff status, and merge readiness are visible when multiple agents or branches are active;
- no live runtime dispatch is added.

Validation:

```powershell
npm test --prefix apps/l1gov-desktop-client
python -m pytest nexus/governance/tests
```

Desktop startup command: future-authorized-only.

### EDC-PR-005: Owner UAT Closeout

Goal: prepare and run the bounded UAT round after Alex authorizes startup.

Expected files:

- `docs/codex/UAT_*.md`
- minimal `verification/` evidence if explicitly authorized

Acceptance:

- startup command, side effects, and cleanup expectations are documented;
- Alex owner observations are recorded separately from Codex automated checks;
- no UAT PASS is claimed without Alex confirmation;
- GitHub PR mapping and merge/closeout recommendation are updated after review.

Validation:

```powershell
git diff --check
```

Desktop startup command: future-authorized-only.

## Recommendation

Complete `EDC-PR-001` first. Do not open `EDC-PR-002` until `EDC-PR-001` is reviewed, because implementation scope needs owner agreement before code changes begin.

## UX Implementation Mapping

Use `docs/codex/UX_SPEC.md` as the durable UX reference for future task cards:

- `EDC-PR-002`: delivery domain contracts for work item detail, readiness, runtime authorization, evidence, PR mapping, and owner UAT state.
- `EDC-PR-003`: Planning-to-Execution and Execution-to-Planning handoff loop for task-card emission, completion reports, blockers, and evidence freshness.
- `EDC-PR-004`: desktop Delivery Board MVP for project summary, lanes, work cards, validation chips, attention rail, and visible blocked/hold states.
- `EDC-PR-005`: PR/UAT closeout surface for internal-to-GitHub PR mapping, evidence gate, owner UAT decision intake, and bounded closeout recommendation.

The recommended next Execution task after `EDC-PR-001` is `EDC-PR-002: Delivery Domain Contracts`.
