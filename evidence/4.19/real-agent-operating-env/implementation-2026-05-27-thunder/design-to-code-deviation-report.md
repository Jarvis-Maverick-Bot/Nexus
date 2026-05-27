# Design-To-Code Deviation Report

Status: no blocking deviations.

- Candidate Adapter profile heartbeat defaults normalized to 15s interval / 60s TTL per approved policy values.
- Resident live loop uses an injected deterministic lifecycle provider for decision/lease data; missing provider fails closed instead of minting Dispatch/UAT lifecycle truth.
- CLI packaging remains bounded to existing module CLI; no global `nexus candidate` executable was added.
- No runtime/UAT, broker/config/credential mutation, private-agent invocation, deploy, merge, WBS PASS, or final readiness claim was performed.
