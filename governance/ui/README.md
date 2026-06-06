# Governance UI

`governance/ui` contains local dashboard surfaces for observing governance state.

## Files

- `dashboard_server.py` - Dashboard server helper.
- `main.py` - UI entry point.
- `pmo_dashboard.html` - PMO dashboard page.
- `v1_governance.py` - Earlier governance UI surface.

## Boundaries

- UI state is observational unless a specific command path is explicitly documented and authorized.
- Viewing or presenting evidence does not equal final acceptance.
- UI surfaces do not enable production deploy, live runtime promotion, credential mutation, or default-on dispatch.
