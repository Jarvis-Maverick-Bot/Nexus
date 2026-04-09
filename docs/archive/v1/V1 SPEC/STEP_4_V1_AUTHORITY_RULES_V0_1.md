# STEP_4_V1_AUTHORITY_RULES_V0_1

**Step:** 4
**Version:** V0_1
**Status:** Draft for discussion with Jarvis
**Purpose:** Freeze Step 4 of the implementation-ready framework: V1 authority rules.

---

## 1. Purpose

Step 4 defines who is allowed to do what in V1.

If:
- Step 2 defines what exists
- Step 3 defines what actions exist

then:
Step 4 defines action eligibility over governed objects.

This is the minimum authority model needed to make V1 truly controllable.

---

## 2. Core authority principle

V1 authority rules should be:

- explicit enough to constrain implementation
- simple enough to remain practical
- based on role and stage responsibility
- not overbuilt into a full enterprise permission engine

---

## 3. V1 authority layers

### A. Management Layer
Includes:
- Alex
- Nova
- Jarvis
- Maverick (**logical PMO authority role; runtime involvement is not required for V1 implementation**)

#### Management Layer authority
Can:
- create / update / close project
- create / update / close task
- assign owner
- update task state when acting with management authority
- record / resolve blocker
- submit handoff when acting with explicit management authority
- make gate decisions
- access full project/task visibility

---

### B. Delivery Layer
Includes:
- BA
- SA
- DEV
- QA

#### Delivery Layer authority
Can:
- update task state for owned task
- record blocker for owned task
- resolve blocker for owned task
- submit handoff for owned task/stage
- query relevant task/workflow visibility

#### Delivery Layer default restrictions
Cannot by default:
- create project
- close project
- assign ownership broadly
- make gate decisions outside defined authority
- freely mutate unrelated tasks

---

## 4. Object/action authority rules

### Project-level authority
- `create_project` → Management Layer only
- `update_project` → Management Layer only
- `close_project` → Management Layer only

### Task-level authority
- `create_task` → Management Layer only
- `update_task` → Management Layer and authorized current owner where appropriate
- `assign_owner` → Management Layer only
- `close_task` → Management Layer or explicitly authorized closing authority

### Task-state authority
- `update_task_state` → current owner and Management Layer
- `record_blocker` → current owner and Management Layer
- `resolve_blocker` → current owner and Management Layer

### Handoff authority
- `submit_handoff` → current owner of the task/stage, or Management Layer acting with explicit authority

### Gate authority
- `approve` → Management Layer gate authority only
- `reject` → Management Layer gate authority only
- `hold` → Management Layer gate authority only
- `stop` → Management Layer gate authority only
- `return` → Management Layer gate authority only

### Query authority
- Management Layer → full visibility
- Delivery Layer → visibility for relevant assigned or participating tasks
- V1 does not require a heavy confidentiality/partitioning model unless later needed

---

## 5. Maverick position in V1

Maverick is included in V1 as:

**a logical Management Layer / PMO authority role**

However:

V1 implementation does not require Maverick to be a fully runtime-independent active participant.

This means:
- Maverick is part of the governance design
- Maverick is part of the intended PMO authority structure
- but V1 runtime delivery does not depend on full Maverick runtime involvement yet

This preserves:
- governance truth
- implementation realism

---

## 6. One-line frozen definition

**V1 authority is role-based and action-bounded: Management Layer controls project/task creation, ownership, gate decisions, and full visibility; Delivery Layer controls owned-task execution, state updates, blocker handling, and handoff submission; Maverick is included logically in the Management Layer, but V1 implementation does not depend on his full runtime participation yet.**
