# Design Change Impact Response

## Accepted Change

CP-004 replaces the CP-001 MQ placeholder with MQ Management child panels under the existing Operation Panel Host.

## User-Facing Impact

- MQ menu now opens a child-panel menu inside Operation Panel Host.
- Queue Overview, Message Detail, Dispatch No-Go Diagnostics, and Replay Evidence panels are available for UX review.
- ContextEnvelope and shell status remain visible while MQ panels are open.

## Authority Impact

No authority change. Kernel and Governance Service remain authoritative. MQ panels render deterministic view-model data and local display state only.

## Technical Impact

- Adds deterministic `mq_management` fixture data.
- Adds MQ panel registry entries and renderer functions.
- Extends desktop surface tests and fixture verifier.
- Adds CP-004 screenshot/evidence package.

## Explicit Non-Impact

No `nexus.mq` import, real MQ runtime, Tauri bridge expansion, dispatch/controller/route/adapter/transport activation, live/private-agent invocation, deploy/config/credential mutation, production readiness, final PASS, 4.21 closeout, or CP-005+ work.