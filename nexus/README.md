# Nexus Python Package

`nexus` is the Python package root for runtime and messaging code used by the governed delivery system.

The active runtime implementation lives primarily under `nexus/mq`. Keep package-level documentation thin and point detailed runtime terms to the module README.

## Modules

- `mq/` - Runtime lifecycle, dispatch, Candidate Agent Adapter, Resident Controller Service Package, message contract, heartbeat, evidence, and transport-boundary code.

## Current Vocabulary

Use the accepted design terms in active docs and task names:

- Runtime Lifecycle Controller
- Dispatch Controller
- Candidate Agent Adapter
- External Agent Runtime
- Resident Controller Service Package

Older names may appear in historical evidence or legacy source file names. Do not treat those as current design terminology unless a design document explicitly says so.
