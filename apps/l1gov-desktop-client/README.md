# Nexus Agent Coding Team Workbench

Slice: `EDC-PR-009`

This is the Windows-first desktop Workbench surface for the Nexus Agent Coding Team Workbench. It uses deterministic fixture data and does not connect to any daemon, controller, transport, route, private agent, broker, NATS endpoint, or canonical state writer.

## Runtime Boundary

EDC-PR-009 does not authorize desktop startup, dependency installation, Tauri dev/build, Cargo commands, broker/NATS mutation, live dispatch, merge approval, owner UAT acceptance, UAT PASS, production readiness, or live readiness.

The surface is fixture-only and non-authoritative. Repository docs, task cards, validation evidence, GitHub PR mappings, and owner decisions remain authoritative.

## Current Scope

The first screen identifies `Nexus Agent Coding Team Workbench` and provides real stateful navigation for these shell-level views:

- Work Items
- Work Item Detail
- Agents
- Runtime / Worktrees
- Evidence / Runs
- PR / UAT Closeout
- Inbox / Attention
- Settings / Boundaries

EDC-PR-008 implemented the Work Items board/list and selected Work Item Detail read model. EDC-PR-009 implements the Agents/Team and Runtime/Worktrees read-model views, including assignment boundaries, worktree inspection, runtime hold state, and NATS boundary notes. Evidence/Runs, PR/UAT Closeout, Inbox/Attention, and Settings/Boundaries remain shallow placeholders for EDC-PR-010.

## Launch Notes

Future startup commands require explicit task-card authorization. When later authorized, a reviewer workstation needs Node/npm, Rust/Cargo, and WebView2 runtime available for Tauri startup.

Dedicated Nexus local-test NATS is `127.0.0.1:7422` with monitor `http://127.0.0.1:8422/varz`, but this slice does not start or mutate it. OpenClaw live NATS `127.0.0.1:4222` must not be used or modified unless Alex explicitly authorizes it.

## Superseded Prototype Boundary

EDC-PR-004 / GitHub PR #30 and EDC-PR-005 / GitHub PR #31 are superseded UX prototypes. They are not the active implementation baseline and not the UAT baseline.
