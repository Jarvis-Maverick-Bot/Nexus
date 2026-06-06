# Governance Control

`governance/control` contains local control models and task-store helpers used by governance workflows.

## Files

- `control.py` - Governance control records and helpers.
- `task_store.py` - Local task store access.

## Boundaries

- Control records are local governance state, not runtime execution authority.
- Changes here do not imply live-readiness, production deployment, or final PASS.
- Runtime lifecycle, dispatch, and Candidate Agent Adapter behavior remain under `nexus/mq`.
