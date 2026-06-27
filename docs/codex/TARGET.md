# Nexus Agent Coding Team Workbench Target

Date: 2026-06-27
Branch: `codex/edc-pr-006-ux-reset-workbench`
Internal PR: `EDC-PR-006`
Base: `codex/edc-pr-003-codex-handoff-loop` at `a87d06efe85384b22f04ebc7b017870dc1bf8902`

## Branch Decision

EDC-PR-006 resets the Nexus desktop UX direction after Alex rejected the EDC-PR-004 / GitHub PR #30 and EDC-PR-005 / GitHub PR #31 desktop direction.

PR #30 and PR #31 collapsed delivery board, work item detail, agents/runtime, evidence/runs, PR/UAT closeout, and blocked command state into one overloaded screen. They are draft PR prototypes that may be mined for fixture/verifier ideas, but they are not UAT-accepted and are not the new desktop implementation baseline.

The accepted continuation base is EDC-PR-003 / GitHub PR #29, `codex/edc-pr-003-codex-handoff-loop`, because it preserves the durable delivery contracts and handoff loop without inheriting the rejected desktop UX.

## Target Outcome

Build the first credible Nexus Agent Coding Team Workbench: a local-first desktop workspace where human owners and Codex agents can plan, execute, validate, review, and close out software delivery work through clear views instead of a single overloaded board.

The target experience is:

1. Alex can open a Nexus desktop workbench for a real local project.
2. The shell provides stable navigation and page boundaries for Work Items, Work Item Detail, Agents, Runtime/Worktrees, Evidence/Runs, PR/UAT Closeout, Inbox/Attention, and Settings/Boundaries.
3. Codex Planning creates bounded task cards with explicit scope, non-goals, file boundaries, validation commands, risks, and write-back locations.
4. Codex Execution works in isolated project worktrees and reports changed files, validation evidence, blockers, branch state, and PR readiness.
5. Owner UAT remains a separate manual acceptance step and is never replaced by automated validation.
6. The next owner UAT baseline is EDC-PR-010, not PR #31.

## Product Positioning

Nexus should become an Agent Coding Team Workbench, not only a governance evidence viewer and not a single-screen delivery dashboard.

Multica is a product and information-architecture reference only: persistent workspaces, visible issues/tasks, agent activity, runtime boundaries, and reviewable progress. Nexus must translate those product patterns into the existing Nexus local-first/Tauri/repo-governed architecture. Do not copy Multica's Next.js, Go, Postgres, deployment, or service stack.

## Success Definition

EDC success means a bounded project delivery path is demonstrably usable by the owner: work moves from planning to isolated execution, validation, review, PR tracking, owner UAT decision intake, and closeout with clear boundaries and evidence.

It does not mean production readiness, live dispatch, default-on runtime control, private agent invocation, deployment, external adoption, autonomous merge authority, or final product acceptance.

## Superseded Material

The following branches are reference-only:

- EDC-PR-000 / GitHub PR #22: superseded L1 Governance Desktop UAT attempt.
- EDC-PR-004 / GitHub PR #30: overloaded single-screen Desktop Delivery Board prototype.
- EDC-PR-005 / GitHub PR #31: overloaded single-screen Owner UAT Closeout prototype.

Do not treat these branches as the UAT baseline. Useful fixture safety checks, verifier assertions, and blocked-state language may be reused after review.

## Immediate Next Decision

Complete EDC-PR-006 as a docs-only UX reset and PR stack replan. EDC-PR-007 through EDC-PR-010 should then rebuild the desktop workbench in separate, reviewable implementation slices, with owner UAT only after EDC-PR-010 is ready.
