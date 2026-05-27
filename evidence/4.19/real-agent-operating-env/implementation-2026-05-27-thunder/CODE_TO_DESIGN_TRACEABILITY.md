# Code-To-Design Traceability Matrix

| Task | Design requirement | Code paths | Test/evidence |
| --- | --- | --- | --- |
| T-ARA-10 | Candidate Adapter local API/profile policy | `nexus/mq/candidate_adapter_profile_loader.py` | `test_candidate_adapter_profile_loader.py`; `candidate-resident-focused-pytest.txt` |
| T-ARA-11 | Bounded Candidate Adapter run-loop | `nexus/mq/candidate_adapter_run_loop.py`; existing API modules | `test_candidate_adapter_run_loop.py`; `candidate-resident-focused-pytest.txt` |
| T-ARA-12 | Runtime lifecycle monitoring/management | `nexus/mq/runtime_lifecycle_controller.py`; `nexus/mq/heartbeat_presence_controller.py`; `nexus/mq/agent_access_read_model.py`; `nexus/mq/runtime_metrics_projection.py` | `test_real_agent_runtime_lifecycle_controller.py`; `test_heartbeat_presence_controller.py`; `test_agent_access_real_agent_projection.py` |
| T-ARA-13 | Eligibility and reservation lease enforcement | `nexus/mq/eligibility_reservation_policy.py`; `nexus/mq/resident_controller/dispatcher.py`; `nexus/mq/resident_controller/live_loop.py` | `test_eligibility_reservation_policy.py`; `test_resident_controller_real_agent_dispatch.py`; resident-controller regression tests |
| T-ARA-14 | Integrated evidence package generator | `nexus/mq/integrated_evidence_package_generator.py`; evidence package files | `test_integrated_evidence_package_generator.py`; `secret-scan.txt`; `SHA256SUMS.txt`; `sha256-verify.txt` |
| T-ARA-15 | Role-aware normal operating Runbook | `docs/runbooks/4.19_REAL_AGENT_OPERATING_ENVIRONMENT_RUNBOOK.md` | `test_real_agent_operating_runbook.py`; `runbook-completeness.txt` |
| T-ARA-16 | A2A placeholder-only boundary | `nexus/mq/a2a_placeholder_marker.py` | `test_a2a_placeholder_boundary.py`; `no-a2a-evidence.txt` |
| T-ARA-17 | Diagnostic-only readiness guard | `nexus/mq/readiness_taxonomy.py` | `test_real_agent_readiness_taxonomy.py`; `diagnostic-readiness-evidence.txt` |
| T-CB-04 | Dispatch requests lifecycle eligibility before assignment | `nexus/mq/resident_controller/dispatcher.py`; `nexus/mq/resident_controller/live_loop.py` | `test_resident_controller_real_agent_dispatch.py`; `test_resident_controller_live_loop.py` |
| T-CB-05 | Assignment publish requires active reservation lease | `nexus/mq/eligibility_reservation_policy.py`; `nexus/mq/resident_controller/dispatcher.py` | `test_assignment_publish_requires_active_reservation_lease`; duplicate replay negative tests |
| T-CB-08 | Diagnostic evidence cannot mark real operating readiness | `nexus/mq/readiness_taxonomy.py`; `nexus/mq/integrated_evidence_package_generator.py` | `test_phase3_minitest_evidence_is_diagnostic_only`; `diagnostic-readiness-evidence.txt` |

## No-Go Boundary Evidence

- No production broker/config/credential files were modified.
- No Shared Docs files were modified.
- No runtime/UAT/deploy/private-agent invocation/live business execution was performed.
- Resident live-loop lifecycle truth is injected via a deterministic provider in tests; missing provider fails closed.
