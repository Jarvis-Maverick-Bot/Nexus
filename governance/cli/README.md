# Governance CLI

`governance/cli` contains PMO command-line surfaces for local governance state, task/action inventory, and event logging.

## Files

- `cli.py` - CLI commands.
- `store.py` - JSON-backed PMO state and log helpers.
- `V1_8_PMO_ACTION_INVENTORY.md` - Historical PMO action inventory.
- `V1_8_PMO_CLI_REFERENCE.md` - Historical PMO CLI reference.

## Boundaries

- CLI state is governance evidence/support state, not production release authority.
- CLI operations do not enable live runtime config, deploy services, mutate credentials, or claim final acceptance.
- Runtime lifecycle and dispatch authority remain with the runtime modules and explicit governance gates.
