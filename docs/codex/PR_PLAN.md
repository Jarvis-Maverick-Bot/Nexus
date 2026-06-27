# Nexus Agent Coding Team Workbench PR Plan

Date: 2026-06-27
Branch: `codex/edc-pr-006-ux-reset-workbench`

## Numbering Rule

Internal delivery sequence uses `EDC-PR-###`.

GitHub PR numbers are external identifiers assigned by GitHub and must be recorded as mappings. Do not use GitHub PR numbers as the internal delivery order.

## Current PR State

- GitHub PR #22 is closed and superseded by the EDC planning reset path.
- GitHub PR #27 / EDC-PR-001 established the planning reset and UX reference docs.
- GitHub PR #28 / EDC-PR-002 established delivery domain contracts.
- GitHub PR #29 / EDC-PR-003 established durable Codex handoff records and is the accepted base for the workbench rebuild.
- GitHub PR #30 / EDC-PR-004 and GitHub PR #31 / EDC-PR-005 are draft PRs but are superseded as UX implementation baseline because Alex rejected the overloaded single-screen direction.
- EDC-PR-006 starts a docs-only UX reset and stack replan from EDC-PR-003/#29.

## PR Mapping

| Internal PR | GitHub PR | Branch | Purpose | Status |
| --- | ---: | --- | --- | --- |
| `EDC-PR-000` | #22 | `codex/4.21-real-testproject-e2e-uat` | Superseded L1 Governance Desktop UAT attempt | Closed / superseded |
| `EDC-PR-001` | #27 | `codex/edc-governance-desktop` | Early planning reset and reference docs | Draft PR open / active foundation |
| `EDC-PR-002` | #28 | `codex/edc-pr-002-delivery-domain-contracts` | Delivery domain contracts | Draft PR open / active foundation |
| `EDC-PR-003` | #29 | `codex/edc-pr-003-codex-handoff-loop` | Codex execution handoff loop | Draft PR open / active implementation base |
| `EDC-PR-004` | #30 | `codex/edc-pr-004-desktop-delivery-board` | Desktop delivery board MVP prototype | Draft PR open / superseded UX prototype, not UAT baseline |
| `EDC-PR-005` | #31 | `codex/edc-pr-005-owner-uat-closeout` | Owner UAT closeout prototype | Draft PR open / superseded UX prototype, not UAT baseline |
| `EDC-PR-006` | #32 | `codex/edc-pr-006-ux-reset-workbench` | Multica-style UX reset and PR stack replan | Draft PR open |
| `EDC-PR-007` | #33 | `codex/edc-pr-007-desktop-workbench-shell` | Desktop workspace shell and real navigation | Draft PR open |
| `EDC-PR-008` | #34 | `codex/edc-pr-008-work-items-surface` | Work items board/list/detail surface | Draft PR open |
| `EDC-PR-009` | TBD | `codex/edc-pr-009-agents-runtime-worktrees` | Agents, runtime, and worktree surface | Implementation in review |
| `EDC-PR-010` | TBD | TBD | Evidence, PR/UAT closeout, and final UAT startup readiness | Planned |

## Proposed PR Sequence

### EDC-PR-006: Multica-style UX Reset And PR Stack Replan

Goal: reset the desktop UX plan after rejecting the overloaded PR #30/#31 direction, preserve EDC-PR-002/003 foundations, and define the EDC-PR-007..010 workbench stack.

Expected files:

- `docs/codex/TARGET.md`
- `docs/codex/SCOPE.md`
- `docs/codex/SPEC.md`
- `docs/codex/UX_SPEC.md`
- `docs/codex/PR_PLAN.md`
- `docs/codex/UX_REPLAN_EDC_PR_006.md`

Acceptance:

- product target is `Nexus Agent Coding Team Workbench`;
- #30/#31 are recorded as superseded UX prototypes, not UAT baseline;
- #29 is recorded as the next implementation base;
- Multica is recorded as IA/product reference only, not copied stack;
- EDC-PR-007..010 implementation slices are defined;
- no product source, dependency, runtime, cleanup, GitHub PR mutation, or generated output is included.

Validation:

```powershell
git status --short --branch
git diff --check
git diff -- docs/codex/TARGET.md docs/codex/SCOPE.md docs/codex/SPEC.md docs/codex/UX_SPEC.md docs/codex/PR_PLAN.md docs/codex/UX_REPLAN_EDC_PR_006.md
```

### EDC-PR-007: Desktop Workspace Shell And Real Navigation

Goal: replace the old L1 Governance test surface with the Workbench shell and actual navigation/page boundaries.

Expected files:

- `apps/l1gov-desktop-client/src/index.html`
- `apps/l1gov-desktop-client/src/main.js`
- `apps/l1gov-desktop-client/src/styles.css`
- fixture/verifier files only as needed
- docs only for branch/status mapping

Acceptance:

- first screen identifies `Nexus Agent Coding Team Workbench`;
- navigation switches between real views/pages, not scroll anchors;
- shell shows project, branch/worktree, internal sequence, and authority chips;
- no runtime startup, dispatch, dependency install, or owner UAT claim is added.

Validation:

```powershell
node apps/l1gov-desktop-client/scripts/verify-fixture.mjs
python -m pytest nexus/governance/tests -q
git diff --check
```

### EDC-PR-008: Work Items Board/List/Detail Surface

Goal: implement Work Items board/list and Work Item Detail as separate surfaces backed by deterministic read-model data.

Acceptance:

- board/list shows internal IDs separately from GitHub PR numbers;
- detail view shows full task-card contract, readiness, assignment, validation, blockers, and write-back state;
- unsafe actions remain blocked or read-only;
- no owner UAT or merge readiness is claimed.

### EDC-PR-009: Agents, Runtime, And Worktree Surface

Goal: implement agent/team, runtime authorization, and worktree state surfaces.

Acceptance:

- Planning, Execution, reviewer/reducer, and owner UAT roles are visible;
- worktree/branch state and assignment boundaries are visible;
- runtime authorization states are explicit;
- startup/dependency/broker/dispatch actions remain blocked unless a task card authorizes a named command.

### EDC-PR-010: Evidence, PR/UAT Closeout, And Final UAT Startup Readiness

Goal: implement Evidence/Runs and PR/UAT Closeout views and prepare the first owner UAT-ready stack.

Acceptance:

- evidence gates and run records support evidence-before-claim;
- PR mapping is separate from internal EDC IDs;
- owner UAT decision intake is separate from automated validation;
- startup readiness can be documented for Alex, but Codex does not claim owner UAT acceptance, UAT PASS, merge approval, production readiness, or live readiness;
- after Planning review, Alex can be notified for UAT testing.

## UX Implementation Mapping

Use `docs/codex/UX_SPEC.md` as the durable UX reference for future task cards:

- `EDC-PR-006`: docs-only UX reset and PR stack replan.
- `EDC-PR-007`: workspace shell and real navigation.
- `EDC-PR-008`: Work Items board/list and Work Item Detail.
- `EDC-PR-009`: Agents/team, runtime authorization, and worktree state.
- `EDC-PR-010`: Evidence/Runs, PR/UAT closeout, final startup readiness, and owner UAT preparation.

The recommended next Execution task after EDC-PR-006 is `EDC-PR-007: Desktop Workspace Shell And Real Navigation`.
