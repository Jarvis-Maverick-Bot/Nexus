"""Sprint 5 E2E test script"""
from gov_langgraph.openclaw_integration import (
    init_harness, create_project_tool, kickoff_task_tool, list_tasks_tool,
    submit_handoff_tool, upsert_artifact_tool, get_gate_panel_tool,
    create_acceptance_package_tool, get_acceptance_package_tool,
    approve_acceptance_tool, reject_acceptance_tool,
    get_project_tool,
)
from gov_langgraph.openclaw_integration.tools import get_advisories_tool, raise_advisory_tool

def test_happy_path():
    print("=== HAPPY PATH E2E ===")
    init_harness()

    # 1. Create project Alpha
    r = create_project_tool({'project_name': 'Alpha', 'project_goal': 'Full E2E test', 'project_owner': 'alex'})
    assert r['ok'], f"Create project failed: {r}"
    pid = r['project_id']
    print(f"1. Create project: OK {pid[:8]}")

    # 2. Scope artifact
    r = upsert_artifact_tool({'project_id': pid, 'artifact_type': 'scope', 'content': 'Alpha scope', 'produced_by': 'alex'})
    assert r['ok'], f"Scope failed: {r}"
    print("2. Scope artifact: OK")

    # 3. Kickoff task
    r = kickoff_task_tool({'title': 'Alpha BA', 'project_id': pid, 'description': 'BA for Alpha', 'priority': 1, 'assignee': 'ba_agent', 'actor': 'alex'})
    assert r['ok'], f"Kickoff failed: {r}"
    tid = r['task_id']
    print(f"3. Kickoff: OK {tid[:8]}")

    # 4. Task in INTAKE
    r = list_tasks_tool({'project_id': pid})
    t = r['tasks'][0]
    assert t['current_stage'] == 'INTAKE', f"Expected INTAKE, got {t['current_stage']}"
    print(f"4. Task in INTAKE: OK stage={t['current_stage']} status={t['task_status']}")

    # 5. INTAKE->BA handoff
    r = submit_handoff_tool({'task_id': tid, 'from_owner': 'alex', 'to_owner': 'ba_agent', 'actor': 'alex'})
    assert r['ok'], f"INTAKE->BA failed: {r}"
    print("5. INTAKE->BA: OK")

    # 6. SPEC artifact
    r = upsert_artifact_tool({'project_id': pid, 'artifact_type': 'spec', 'content': 'Alpha spec', 'produced_by': 'ba_agent'})
    assert r['ok'], f"SPEC failed: {r}"
    print("6. SPEC artifact: OK")

    # 7. BA->SA handoff
    r = submit_handoff_tool({'task_id': tid, 'from_owner': 'ba_agent', 'to_owner': 'sa_agent', 'actor': 'ba_agent'})
    assert r['ok'], f"BA->SA failed: {r}"
    print("7. BA->SA: OK")

    # 8. ARCH artifact
    r = upsert_artifact_tool({'project_id': pid, 'artifact_type': 'arch', 'content': 'Alpha arch', 'produced_by': 'sa_agent'})
    assert r['ok'], f"ARCH failed: {r}"
    print("8. ARCH artifact: OK")

    # 9. SA->DEV handoff
    r = submit_handoff_tool({'task_id': tid, 'from_owner': 'sa_agent', 'to_owner': 'dev_agent', 'actor': 'sa_agent'})
    assert r['ok'], f"SA->DEV failed: {r}"
    print("9. SA->DEV: OK")

    # 10. TESTCASE artifact
    r = upsert_artifact_tool({'project_id': pid, 'artifact_type': 'testcase', 'content': 'Alpha testcases', 'produced_by': 'qa_agent'})
    assert r['ok'], f"TESTCASE failed: {r}"
    print("10. TESTCASE artifact: OK")

    # 11. DEV->QA handoff
    r = submit_handoff_tool({'task_id': tid, 'from_owner': 'dev_agent', 'to_owner': 'qa_agent', 'actor': 'dev_agent'})
    assert r['ok'], f"DEV->QA failed: {r}"
    print("11. DEV->QA: OK")

    # 12. TESTREPORT artifact
    r = upsert_artifact_tool({'project_id': pid, 'artifact_type': 'testreport', 'content': 'Alpha test report', 'produced_by': 'alex'})
    assert r['ok'], f"TESTREPORT failed: {r}"
    print("12. TESTREPORT artifact: OK")

    # 13. QA->DONE handoff
    r = submit_handoff_tool({'task_id': tid, 'from_owner': 'qa_agent', 'to_owner': 'alex', 'actor': 'qa_agent'})
    assert r['ok'], f"QA->DONE failed: {r}"
    print("13. QA->DONE: OK")

    # 13b. GUIDELINE artifact (produced on completion)
    r = upsert_artifact_tool({'project_id': pid, 'artifact_type': 'guideline', 'content': 'Alpha guideline: follow standard pipeline', 'produced_by': 'maverick'})
    assert r['ok'], f"GUIDELINE failed: {r}"
    print("13b. GUIDELINE artifact: OK")

    # 14. Gate panel (requires task_id)
    r = get_gate_panel_tool({'project_id': pid, 'task_id': tid})
    assert r['ok'], f"Gate panel failed: {r}"
    print(f"14. Gate: gate_status={r.get('gate_status')} stage={r.get('current_stage')}")

    # 15. Create acceptance package
    r = create_acceptance_package_tool({'project_id': pid, 'task_id': tid, 'verification_notes': 'All done', 'actor': 'alex'})
    assert r['ok'], f"Acceptance package failed: {r}"
    assert r.get('is_complete') == True, f"Expected complete=True, got {r.get('is_complete')}"
    assert len(r.get('missing_artifacts', [])) == 0, f"Missing artifacts: {r.get('missing_artifacts')}"
    print(f"15. Acceptance package: OK complete={r.get('is_complete')} missing={r.get('missing_artifacts', [])}")

    # 16. Approve acceptance
    r = approve_acceptance_tool({'project_id': pid, 'actor': 'alex', 'note': 'Looks good'})
    assert r['ok'], f"Approve failed: {r}"
    print(f"16. Approve: OK decision={r.get('decision')}")

    # 17. Final status
    r = list_tasks_tool({'project_id': pid})
    t = r['tasks'][0]
    print(f"17. Final: stage={t['current_stage']} status={t['task_status']}")

    print("\n=== HAPPY PATH E2E: ALL 17 STEPS PASSED ===")
    return pid, tid


def test_parallel_projects(pid_a, tid_a):
    print("\n=== PARALLEL PROJECTS ===")
    init_harness()

    # Create project Beta
    r = create_project_tool({'project_name': 'Beta', 'project_goal': 'Parallel test', 'project_owner': 'bob'})
    assert r['ok'], f"Beta create failed: {r}"
    pid_b = r['project_id']
    print(f"1. Create Beta: OK {pid_b[:8]}")

    # Alpha still exists and intact
    r = get_project_tool({'project_id': pid_a})
    assert r['ok'], f"Alpha disappeared: {r}"
    print(f"2. Alpha still OK: artifacts={len(r.get('artifacts', {}))}")

    # Beta has its own artifacts
    r = upsert_artifact_tool({'project_id': pid_b, 'artifact_type': 'scope', 'content': 'Beta scope', 'produced_by': 'bob'})
    print(f"3. Beta scope: {r['ok']}")

    # Beta kickoff
    r = kickoff_task_tool({'title': 'Beta BA', 'project_id': pid_b, 'description': 'Beta BA', 'priority': 1, 'assignee': 'ba_agent', 'actor': 'bob'})
    tid_b = r['task_id']
    print(f"4. Beta kickoff: {r['ok']} {tid_b[:8]}")

    # Both projects have distinct tasks
    r_a = list_tasks_tool({'project_id': pid_a})
    r_b = list_tasks_tool({'project_id': pid_b})
    assert r_a['tasks'][0]['task_id'] == tid_a
    assert r_b['tasks'][0]['task_id'] == tid_b
    print("5. Projects isolated: OK")

    print("\n=== PARALLEL PROJECTS: PASSED ===")


def test_rejection_path(pid, tid):
    print("\n=== REJECTION PATH ===")

    # Re-create acceptance (task already done, create fresh)
    r = create_acceptance_package_tool({'project_id': pid, 'task_id': tid, 'verification_notes': 'Review', 'actor': 'alex'})
    assert r['ok'], f"Acceptance package failed: {r}"
    print(f"1. Acceptance package: OK complete={r.get('is_complete')}")

    r = reject_acceptance_tool({'project_id': pid, 'actor': 'alex', 'reason': 'Test rejection — needs revision'})
    assert r['ok'], f"Reject failed: {r}"
    print(f"2. Reject: OK msg={r.get('message')}")

    # Verify rejection via get_acceptance_package_tool (correct surface)
    r = get_acceptance_package_tool({'project_id': pid})
    assert r['ok'], f"Get acceptance package failed: {r}"
    pkg = r.get('acceptance_package', {})
    assert pkg.get('acceptance_decision') == 'rejected', f"Expected rejected, got {pkg.get('acceptance_decision')}"
    print(f"3. Rejection verified: decision={pkg.get('acceptance_decision')}")

    print("\n=== REJECTION PATH: PASSED ===")


if __name__ == '__main__':
    pid, tid = test_happy_path()
    test_parallel_projects(pid, tid)
    test_rejection_path(pid, tid)
    print("\n\n=== ALL SPRINT 5 E2E TESTS PASSED ===")
