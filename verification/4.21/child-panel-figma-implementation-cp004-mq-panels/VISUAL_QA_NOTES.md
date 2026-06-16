# Visual QA Notes

## Checked

- MQ top menu opens the MQ Management host state.
- Queue Overview renders projected queue rows and disabled execution flags.
- Message Detail renders correlation, idempotency, expected version, and payload summary.
- Dispatch No-Go Diagnostics renders blocked diagnostic state only.
- Replay Evidence renders evidence-only references and disabled replay state.
- Compact MQ menu open screenshot is nonblank.
- ContextEnvelope, Main Cockpit, Operation Panel Host, Inspector, and status bar remain visible.

## Notes

- The renderer is still a non-authoritative UX/client test surface.
- MQ child panel buttons produce local preview or blocked-display behavior only.
- No MQ runtime, dispatch execution, controller call, route activation, adapter/transport activation, private-agent invocation, production readiness, continuity activation, deploy, or final PASS claim is exposed.