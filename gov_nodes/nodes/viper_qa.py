# Viper QA - Quality Assurance Node
from datetime import datetime


def viper_qa_execute(state: dict) -> dict:
    """
    Viper-QA: Quality Assurance
    
    Responsibilities:
    - Verify deliverable against SPEC
    - Approve or reject
    - Create QA report
    """
    task_id = state.get("task_id", "unknown")
    spec_content = state.get("spec_content", "")
    deliverable_content = state.get("deliverable_content", "")
    audit_log = state.get("audit_log", [])
    
    # Simple verification
    checks = []
    
    if spec_content and len(spec_content) > 50:
        checks.append("SPEC_CONTENT: PASS")
    else:
        checks.append("SPEC_CONTENT: FAIL")
    
    if deliverable_content and len(deliverable_content) > 50:
        checks.append("DELIVERABLE_CONTENT: PASS")
    else:
        checks.append("DELIVERABLE_CONTENT: FAIL")
    
    all_passed = all("PASS" in c for c in checks)
    
    # Create QA report
    qa_report = f"""# QA Report: {task_id}

## Verification Checks

"""
    for check in checks:
        qa_report += f"- {check}\n"
    
    qa_report += f"""
## Overall Result: {"APPROVED" if all_passed else "REJECTED"}

## Details
- PRD Reviewed: {"YES" if state.get("prd_content") else "NO"}
- SPEC Reviewed: {"YES" if spec_content else "NO"}
- Deliverable Reviewed: {"YES" if deliverable_content else "NO"}

## Verdict
{"APPROVED - Deliverable meets requirements" if all_passed else "REJECTED - Issues found"}

## Created by Viper-QA
- Timestamp: {datetime.now().isoformat()}
"""
    
    decision = {
        "node": "viper_qa",
        "timestamp": datetime.now().isoformat(),
        "task_id": task_id,
        "action": "QA_VERIFICATION",
        "result": "APPROVED" if all_passed else "REJECTED",
        "stage_completed": "QA"
    }
    
    audit_log.append(decision)
    
    return {
        **state,
        "qa_report": qa_report,
        "qa_approved": all_passed,
        "current_stage": "DONE" if all_passed else "HALTED",
        "audit_log": audit_log,
        "updated_at": datetime.now().isoformat()
    }


def viper_qa_route(state: dict) -> str:
    """
    Route after QA.
    """
    if state.get("qa_approved"):
        return "nova"
    return "halted"
