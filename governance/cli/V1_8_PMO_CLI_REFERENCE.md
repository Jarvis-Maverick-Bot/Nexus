# V1.8 PMO CLI Reference

**File:** `governance/pmo/pmo_cli.py`

All commands return JSON. Exit code 0 on success, non-zero on error.

---

## `pmo create-work-item <name>`

Create a new delivery work item.

```bash
python governance/pmo/pmo_cli.py create-work-item "Grid Escape M1"
```

**Output:**
```json
{
  "ok": true,
  "item_id": "WI-001",
  "name": "Grid Escape M1",
  "stage": "BACKLOG"
}
```

---

## `pmo submit-artifact <item_id> <path>`

Register an artifact against a delivery item.

```bash
python governance/pmo/pmo_cli.py submit-artifact WI-001 games/grid_escape/README.md
```

**Output:**
```json
{
  "ok": true,
  "artifact_id": "ART-c8a8b379",
  "item_id": "WI-001",
  "path": "D:\\Projects\\gov_langgraph\\games\\grid_escape\\README.md"
}
```

---

## `pmo request-transition <item_id> <stage>`

Request a stage transition for a delivery item.

```bash
python governance/pmo/pmo_cli.py request-transition WI-001 IN_PROGRESS
```

Valid stages: `BACKLOG`, `IN_PROGRESS`, `IN_REVIEW`, `APPROVED`, `DELIVERED`

**Output:**
```json
{
  "ok": true,
  "item_id": "WI-001",
  "from": "BACKLOG",
  "to": "IN_PROGRESS"
}
```

---

## `pmo record-validation <item_id> <result>`

Record a validation result for a delivery item.

```bash
python governance/pmo/pmo_cli.py record-validation WI-001 PASS
```

Valid results: `PASS`, `FAIL`, `PENDING`

**Output:**
```json
{
  "ok": true,
  "validation_id": "VAL-7605f0fe",
  "item_id": "WI-001",
  "result": "PASS"
}
```

---

## `pmo signal-blocker <item_id> <description>`

Signal a blocker or escalation against a delivery item.

```bash
python governance/pmo/pmo_cli.py signal-blocker WI-001 "Needs Nova review"
```

**Output:**
```json
{
  "ok": true,
  "blocker_id": "BLK-e5a4d5ad",
  "item_id": "WI-001",
  "description": "Needs Nova review"
}
```

---

## `pmo package-delivery <item_id>`

Package a delivery candidate — bundles all artifacts, validations, and open blockers.

```bash
python governance/pmo/pmo_cli.py package-delivery WI-001
```

**Output:**
```json
{
  "ok": true,
  "package_id": "PKG-49f64563",
  "item_id": "WI-001",
  "stage": "IN_PROGRESS"
}
```

---

## `pmo status [item_id]`

Show status of all items or a specific item.

```bash
python governance/pmo/pmo_cli.py status
python governance/pmo/pmo_cli.py status WI-001
```

**Output (all items):**
```json
{
  "ok": true,
  "items": [...],
  "total": 1
}
```

**Output (single item):**
```json
{
  "ok": true,
  "item": {
    "id": "WI-001",
    "name": "Grid Escape M1",
    "stage": "IN_PROGRESS",
    "artifacts": [...],
    "validations": [...],
    "blockers": [...],
    "transitions": [...],
    "delivery_package": {...}
  }
}
```

---

## Help

```bash
python governance/pmo/pmo_cli.py --help
```
