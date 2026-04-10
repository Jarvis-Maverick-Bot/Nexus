# STEP_5_V1_5_PLATFORM_CORE_VS_PMO_MAVERICK_BOUNDARY_V0_1

**Step:** 5
**Version:** V0_2
**Date:** 2026-04-09 | Updated: 2026-04-10
**Status:** Updated per corrected governance model (Nova 2026-04-10)
**Purpose:** Freeze Step 5 of the implementation-ready framework: Platform Core vs PMO/Maverick boundary.

---

## 1. Core principle

### Platform Core
Platform Core remains the governed system of record and control logic.

### PMO Smart Agent
PMO Smart Agent remains the operator-facing management, reporting, review, and control surface.

### Maverick
Maverick becomes the PMO coordination and analysis layer inside the PMO operating surface.

---

## 2. Platform Core responsibilities in V1.5

Platform Core owns:
- project truth
- task truth
- workflow truth
- task state truth
- handoff truth
- gate truth
- event truth
- acceptance-state truth where modeled as governed object
- authority enforcement
- action execution logic

**Note:** Automated readiness-state is not modeled in V1.5. Human-governed intake replaces automated readiness checks.

---

## 3. PMO Smart Agent responsibilities in V1.5

PMO Smart Agent owns:
- project visibility surface
- task visibility surface
- workflow progress display
- blocker / pending item display
- reporting display
- human-governed intake control (kickoff blocked without project selection)
- acceptance display
- control / review action entry

---

## 4. Maverick responsibilities in V1.5

Maverick owns:
- Internal coordination of known agents (executes assigned coordination)
- Status reporting back to PMO surface
- Project-level PM synthesis
- Reporting synthesis
- Acceptance-package coordination
- Advisory support (non-blocking, informational only)

Maverick does NOT own:
- Autonomous decision authority (coordinates only, humans decide)
- Platform Core state truth
- Automated readiness evaluation (human-governed intake, not automated)

---

## 5. What PMO / Maverick should NOT own in V1.5

They must not become the system of record for:
- project truth
- task truth
- workflow truth
- gate logic
- authority logic
- event truth

They must not silently absorb Platform Core responsibilities for speed.

---

## 6. Human final decision authority

Human operators retain final verification and decision authority.
Recommendations from PMO/Maverick are advisory unless explicitly executed through governed authorized action paths.

---

## 7. Boundary rule

Platform Core vs PMO/Maverick boundary remains hard by default.
Any exception must be explicit, discussed, and accepted deliberately.

---

## 8. One-line frozen definition

**In V1.5, Platform Core remains the governed system of record; PMO Smart Agent is the operator-facing management surface; Maverick coordinates known agents internally and returns status (not an autonomous scheduler); human operators retain final decision authority at intake and gates; and none of them may silently collapse into one another.****
