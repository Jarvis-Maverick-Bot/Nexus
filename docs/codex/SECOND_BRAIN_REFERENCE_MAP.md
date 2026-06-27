# SecondBrain Reference Map For EDC-PR-001

Date: 2026-06-27
Branch: `codex/edc-governance-desktop`
Internal PR: `EDC-PR-001`

## Purpose

This file records the bounded Shared Docs / SecondBrain references used to shape the Nexus Agent Coding Team Delivery Console design.

SecondBrain is curated reference memory only. It is not Nexus source authority, not a backlog, not a runtime owner, and not a reason to assign Nova/OpenClaw future Nexus planning, execution, delivery, review-ledger, or periodic-review duties.

## Authority Boundary

Authority order for this branch:

1. Alex's current explicit instruction.
2. Nexus repo current branch, PR state, tests, and repo-native docs.
3. Current accepted Nexus design or implementation-design documents.
4. Accepted historical review evidence and handoff indexes.
5. Approved organization governance doctrine when governance behavior is in scope.
6. Shared Docs `SecondBrain/` as reference patterns only.

If these conflict, Nexus repo facts and Alex's current instruction win.

## Corrected Handoff Boundary

The corrected handoff boundary says:

- Nexus repo is the source/code/test/delivery authority.
- Shared Docs is historical governance, design, and evidence context.
- SecondBrain is curated reference memory only.
- Nova/OpenClaw does not own Nexus planning, execution, delivery, review records, review ledgers, or periodic review.

## SecondBrain Inputs Read

The planning reset used these Shared Docs paths as reference inputs:

- `SecondBrain/Indexes/Action Value Register.md`
- `SecondBrain/Concepts/Governed Workflow Runtime Patterns.md`
- `SecondBrain/Concepts/Agent Safety and Guardrails.md`
- `SecondBrain/Concepts/Agent Skills and Memory Systems.md`
- `SecondBrain/Concepts/Agent Friendly Tooling.md`
- `SecondBrain/Articles/Multi-Agent Division of Work Engineering Survey.md`
- `SecondBrain/Articles/Building Multi-Agent Teams Course.md`
- `SecondBrain/Articles/Agent Inbox Before Shared Brain.md`
- `SecondBrain/Articles/Claude Code Parallel Agents Conflict Control.md`
- `SecondBrain/Articles/Agent Governance Layers.md`
- `SecondBrain/Repos/Multica.md`
- `SecondBrain/Repos/Trellis.md`
- `SecondBrain/Repos/CCB Visible Multi-Agent CLI Workspace.md`

These references are not copied implementation authority. They provide vocabulary and constraints for current Nexus design docs.

## Action Values Adopted Into This Design

| Action Value | Nexus interpretation |
| --- | --- |
| `AV-RCP-002` | Agent dispatch must pass a readiness gate before execution. |
| `AV-RCP-003` | Governed execution must produce validation/evidence records before completion claims. |
| `AV-RCP-005` | HITL and approval gates are governance decisions, not runtime decisions. |
| `AV-RCP-009` | Multi-agent fan-out requires a named reducer/final owner. |
| `AV-RCP-010` | Worktree, sandbox, network, egress, and credential isolation must match task risk. |
| `AV-RCP-011` | Operator surfaces should expose role, current task, liveness, trace, and history. |
| `AV-RCP-015` | UI-to-execution contracts need task identity, state, trace, permission, and result channels. |
| `AV-RCP-017` | Team orchestration requires assignment, liveness, fan-in, cancellation, and traceability before scaling agent count. |
| `AV-RCP-023` | Runtime identity, state, events, delivery/failure handling, and coordination come before role abstraction. |
| `AV-RCP-025` | Multi-agent workflows exchange bounded packets, evidence references, checkpoints, and output contracts. |
| `AV-RCP-026` | Missing authority, tools, tests, certainty, time, or runtime fit must produce blocked/defer states. |
| `AV-RCP-029` | Parallel agent work must declare editable scope, lock/handoff rules, and dependency-aware merge order. |
| `AV-AMR-001` | Preserve source-material vs derived-index boundaries. |
| `AV-AMR-006` | Agent inbox/current task packet comes before broad shared-brain retrieval. |
| `AV-AMR-007` | Separate episodic task state, durable knowledge, skill instructions, and governance decisions. |
| `AV-AMR-008` | Git-backed/file-backed memory needs provenance, review history, rollback, and human-readable diffs. |
| `AV-AMR-009` | Task/backlog memory is not long-term knowledge memory or formal project authority. |
| `AV-RG-003` | Producer, critic, adversarial reviewer, and final reducer roles should be separated when risk justifies it. |
| `AV-RG-004` | Subagents and multi-agent teams are admitted only for parallelization, specialization, or escalation fit. |
| `AV-RG-005` | External tools/frameworks need license, privacy, network, credential, sandbox, and output-behavior review. |
| `AV-STP-006` | Tooling skills must declare inspect-before-mutate behavior, permissions, data exposure, and verification outputs. |
| `AV-STP-010` | Agent-friendly tooling should optimize observable state, small commands, reversible edits, and explainable failures. |
| `AV-SBK-001` | Dashboards are read models over authoritative notes/state, not separate sources of truth. |

## Product Design Implications

For `EDC-PR-002` and later:

- Work items must carry a complete current task packet.
- Agent assignments must include role, editable scope, allowed actions, forbidden actions, stop conditions, output contract, and write-back location.
- Multi-agent execution must be justified by parallelization, specialization, or escalation fit.
- Fan-out requires a reducer owner before work starts.
- Parallel execution requires worktree isolation or an equivalent ownership mechanism.
- Shared resources need lock or handoff semantics.
- Completion reports must cite validation results or explicitly record validation gaps.
- Desktop operator views must show authoritative delivery state, not independent shadow state.
- External agent-platform patterns such as Multica, Trellis, and CCB are comparison inputs only; no install, code reuse, runtime adoption, or dependency change is authorized by this map.

## Explicit Non-Adoptions

This reference map does not approve:

- installing or initializing Trellis, CCB, Multica, or any external agent platform;
- copying external source code or templates;
- adding hooks, daemons, background dispatch, or local CLI orchestration;
- connecting credentials, APIs, brokers, accounts, or model providers;
- treating SecondBrain watchlist items as implementation requirements;
- giving Nova/OpenClaw Nexus planning, execution, delivery, review-ledger, or periodic-review ownership.
