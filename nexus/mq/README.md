# Nexus MQ Runtime Module

`nexus/mq` contains the runtime and messaging layer for governed agent execution. It is where runtime lifecycle, dispatch, Candidate Agent Adapter, Resident Controller Service Package, message contract, heartbeat, evidence, and transport-boundary code lives.

The module supports the 4.19 multi-channel agent runtime compatibility work. That WBS is officially complete from the governance and controlled-validation perspective, but live-readiness promotion, production deployment, always-on runtime operation, and default-on dispatch remain separate future gates.

## Core Components

- **Runtime Lifecycle Controller**: `runtime_lifecycle_controller.py` owns runtime registration, readiness, heartbeat freshness, lifecycle controls, eligibility decisions, and reservation leases.
- **Dispatch Controller**: `controller_bridge_dispatch.py`, `controller_bridge_cli.py`, `controller_bridge_models.py`, and `controller_bridge_state_store.py` own dispatch-side intent validation, dispatch run records, assignment publish requests, duplicate replay handling, and dispatch evidence.
- **Candidate Agent Adapter**: `candidate_adapter_*.py` exposes candidate-facing connection, registration, readiness, heartbeat, assignment intake, result publication, and state reconciliation surfaces.
- **Resident Controller Service Package**: `resident_controller/` contains the default-off resident controller package, including CLI, config validation, service shell, live-loop guard, observer, dispatcher, recovery, and evidence packaging.
- **External Agent Runtime contracts**: runtime adapter, startup packet, readiness taxonomy, private-agent boundaries, heartbeat, and dispatch eligibility modules describe how bounded runtimes interact with the governance core.
- **Transport and message contracts**: `adapter_*.py`, `protocol*.py`, `message_contracts.py`, `message_families.py`, `envelope.py`, and `payloads.py` define transport-facing contracts and message families.

## Authority Boundaries

- Runtime Lifecycle Controller does not publish assignments or claim business completion.
- Dispatch Controller does not register runtimes, submit readiness, record heartbeat, mint lifecycle decisions, or mutate broker configuration.
- Candidate Agent Adapter does not bypass assignment guards, reservation leases, subject policy, or privacy/authority scopes.
- Resident Controller Service Package is default-off unless an explicit authorization, configuration update, and fresh verification gate enables it.
- MQ transport is a boundary for delivery contracts, not a source of final acceptance.

## Test Focus

Focused tests live under `nexus/mq/tests/` and cover lifecycle, heartbeat, dispatch, Resident Controller Service Package, Candidate Agent Adapter, private-agent boundaries, transport contracts, and evidence generation.

Common local command:

```bash
python -m pytest nexus/mq/tests
```

Some live or historical evidence paths require the original governed environment. Do not infer production readiness from source-only or default-off tests.
