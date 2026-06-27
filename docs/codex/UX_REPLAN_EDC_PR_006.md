# EDC-PR-006 UX Replan

Date: 2026-06-27
Branch: `codex/edc-pr-006-ux-reset-workbench`
Base: `codex/edc-pr-003-codex-handoff-loop` at `a87d06efe85384b22f04ebc7b017870dc1bf8902`

## Decision

EDC-PR-004 / GitHub PR #30 and EDC-PR-005 / GitHub PR #31 are superseded as the Nexus desktop UX baseline.

They are not UAT-accepted. They should be treated as failed/obsolete read-model prototypes unless a later task explicitly mines fixture/verifier ideas from them.

## Why The Prior Direction Failed

The PR #30/#31 direction put too many operator jobs into one overloaded screen:

- delivery board;
- work item detail;
- agents/runtime;
- worktrees;
- evidence/runs;
- PR/UAT closeout;
- disabled unsafe commands;
- attention/no-go states.

That shape made scanning dense but not operationally clear. It did not provide stable page boundaries for the different jobs Alex needs to review.

## Accepted Replacement

The accepted replacement direction is `Nexus Agent Coding Team Workbench`.

It is inspired by Multica's product IA patterns: workspace, issues/tasks, agents, runtime visibility, and reviewable progress. Nexus will not copy Multica's implementation stack, service model, database, deployment, or code.

The Workbench should use these separate views:

1. Workspace shell / navigation
2. Work Items board/list
3. Work Item Detail
4. Agents / Team
5. Runtime / Worktrees
6. Evidence / Runs
7. PR / UAT Closeout
8. Inbox / Attention
9. Settings / Boundaries when needed

## Accepted Base

Continue implementation from EDC-PR-003 / GitHub PR #29:

- Branch: `codex/edc-pr-003-codex-handoff-loop`
- Commit: `a87d06efe85384b22f04ebc7b017870dc1bf8902`

This preserves delivery contracts and handoff records while bypassing the rejected UX implementation branches.

## New Stack

- `EDC-PR-006`: UX reset and PR stack replan.
- `EDC-PR-007`: desktop workspace shell and real navigation.
- `EDC-PR-008`: Work Items board/list/detail surface.
- `EDC-PR-009`: agents, runtime, and worktree surface.
- `EDC-PR-010`: evidence, PR/UAT closeout, and final UAT startup readiness.

## UAT Boundary

Alex should only be notified for owner UAT testing after the EDC-PR-010 stack is ready and Planning has reviewed the result.

Codex must not claim owner UAT acceptance, UAT PASS, merge approval, production readiness, live readiness, or closeout acceptance.
