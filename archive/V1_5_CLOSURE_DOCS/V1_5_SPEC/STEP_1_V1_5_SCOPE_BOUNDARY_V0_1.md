# STEP_1_V1_5_SCOPE_BOUNDARY_V0_1

**Step:** 1
**Version:** V0_2
**Date:** 2026-04-09 | Updated: 2026-04-10
**Status:** Updated per corrected governance model (Nova 2026-04-10)
**Purpose:** Freeze Step 1 of the implementation-ready framework: V1.5 scope boundary.

---

## 1. V1.5 Domain Boundary

V1.5 remains within the software delivery domain, but expands the operational surface from V1's narrow task-shell into a true multi-project PMO workflow.

V1.5 is still not a finished cross-industry platform.
It is the next governed release that proves the system can manage software delivery as real projects rather than only as isolated task kickoff/control.

---

## 2. V1.5 Capability Boundary

V1.5 must prove that the following capabilities are real:

- a project can be explicitly initiated by Alex in a true multi-project environment
- governed tasks can be created and managed within that project
- the platform represents a canonical BA -> SA -> DEV -> QA delivery path as the governed reference shape
- human-governed intake control: kickoff blocked without project selection (no automated readiness engine)
- PMO Web UI shows aggregated status from Maverick's internal coordination
- PMO can provide required reporting outputs: Scope, SPEC, Arch, Testcase, TestReport, GuideLine
- acceptance operates as a structured workflow using required artifacts
- Maverick coordinates known agents internally and returns status to PMO surface
- PMO remains operator-facing and does not become the hidden system of record

---

## 3. V1.5 Anti-Scope

V1.5 should not silently expand into:

- full portfolio/program management
- full enterprise hierarchy simulation
- fully autonomous PM decision authority
- hidden replacement of Platform Core by PMO logic
- complete multi-tenant/multi-user productization
- unconstrained advisory intelligence that blurs governance authority

---

## 4. V1.5 Canonical Scenario

V1.5 must be able to run at least one complete software-delivery project scenario such as:

- Alex / Jarvis initiates a project (requires project_name, project_owner, project_goal)
- human-governed intake: kickoff blocked without active project selection
- if Alex decides to shut the project down, no project/task kickoff occurs
- if Alex says go kickoff, project and task are created for execution
- tasks move through BA -> SA -> DEV -> QA as a governed reference path
- handoff, gate, blocker, and state behavior remain explicit
- Maverick coordinates known agents internally and returns coordination status to PMO
- PMO Web UI displays aggregated project status, task, stage, blockers, reporting, and acceptance state clearly

---

## 5. One-line Frozen Definition

**V1.5 is the PMO governance surface + internal coordination layer: Alex/Jarvis assign to Maverick, Maverick coordinates known agents internally and returns status, humans decide at intake/gates, BA->SA->DEV->QA is the governed reference path, PMO Web UI aggregates and displays status, and Platform Core remains the sole authoritative governance/state layer.****
