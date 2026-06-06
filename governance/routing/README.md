# Governance Routing

`governance/routing` contains route-selection logic for governed workflows.

## Files

- `engine.py` - Routing engine components.

## Boundaries

- Routing selects or records an intended path. It does not execute the task, publish assignments, or approve production promotion.
- Unsafe, incomplete, or ambiguous routing prerequisites should fail closed.
- Dispatch execution terms should use the active design vocabulary: Dispatch Controller for dispatch-side assignment flow, Runtime Lifecycle Controller for runtime supply state.
