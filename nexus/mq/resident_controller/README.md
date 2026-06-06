# Resident Controller Service Package

`nexus/mq/resident_controller` contains the default-off Resident Controller Service Package.

This package provides bounded service, CLI, observer, dispatcher, live-loop, recovery, configuration, and evidence surfaces. It is documented as a package because it can support resident operation after explicit authorization, but committed defaults must remain safe and non-promotional.

## Files

- `cli.py` - Command-line entry point for validation, status, drain, recovery, evidence package generation, and bounded start-once checks.
- `config.py` - Config validation, redaction, launch-mode checks, and secret-material safety checks.
- `service.py` - Default-off service shell and status/drain output.
- `live_loop.py` - Bounded live-loop preparation and guarded run-window behavior.
- `observer.py` - Registry, readiness, and heartbeat observation for runtime eligibility decisions.
- `dispatcher.py` - Dispatch guard checks and subject policy.
- `recovery.py` - Restart and checkpoint recovery classification.
- `evidence.py` - Evidence package and manifest generation.

## Boundaries

- Default state is disabled/default-off.
- Bounded UAT requires explicit authorization and config.
- Service status, route readiness, and controller init do not equal final PASS.
- This package does not override Runtime Lifecycle Controller ownership of registration/readiness/heartbeat.
- This package does not override Dispatch Controller ownership of dispatch-side assignment publish requests.

## Tests

```bash
python -m pytest nexus/mq/tests/test_resident_controller_*.py
```
