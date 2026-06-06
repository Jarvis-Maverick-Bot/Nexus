# Governance Modules

`governance` contains PMO, control, routing, collaboration, and dashboard support surfaces for governed delivery.

These modules coordinate work records, operator-visible state, and review/support workflows. They do not by themselves authorize production deployment, live runtime promotion, default-on dispatch, or final acceptance.

## Module Map

- `cli/` - PMO command-line surfaces and task/action inventory.
- `control/` - Local governance control records and task store helpers.
- `routing/` - Route selection and fail-closed routing decisions.
- `ui/` - Local dashboard surfaces for viewing governance state.
- `collab/` - Collaboration protocol experiments and workflow records.
- `data/` - Local JSON/JSONL state used by PMO and collaboration helpers.
- `docs/` - Historical governance foundation notes.

## Relationship To Runtime Modules

Governance modules may reference runtime evidence, task status, routing choices, and approval gates. Runtime lifecycle behavior itself lives in `nexus/mq`, especially the Runtime Lifecycle Controller, Dispatch Controller, Candidate Agent Adapter, and Resident Controller Service Package.
