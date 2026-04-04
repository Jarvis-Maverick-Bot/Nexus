# Nova - Auditor Node
from datetime import datetime


def nova_audit(state: dict) -> dict:
    """
    Nova: Chief Auditor
    
    Responsibilities:
    - Review governance compliance
    - File issues for violations
    - Produce audit summary
    """
    task_id = state.get("task_id", "unknown")
    audit_log = state.get("audit_log", [])
    governance_violations = state.get("governance_violations", [])
    current_stage = state.get("current_stage", "UNKNOWN")
    pending_halt = state.get("pending_halt", False)
    nova_findings = state.get("nova_findings", [])
    
    # Audit findings
    findings = []
    
    # Check governance violations
    if governance_violations:
        for violation in governance_violations:
            findings.append({
                "severity": "HIGH",
                "rule": violation,
                "description": f"Governance rule violated: {violation}",
                "recommendation": "Review and remediate"
            })
    
    # Check stage completion
    expected_stages = ["INTAKE", "BA", "SA", "DEV", "QA", "DONE"]
    if current_stage not in expected_stages:
        findings.append({
            "severity": "MEDIUM",
            "rule": "STAGE_COMPLETION",
            "description": f"Unexpected stage: {current_stage}",
            "recommendation": "Investigate stage progression"
        })
    
    # Check audit log completeness
    expected_nodes = ["maverick", "viper_ba", "viper_sa", "viper_dev", "viper_qa"]
    logged_nodes = set(entry.get("node") for entry in audit_log)
    
    for node in expected_nodes:
        if node not in logged_nodes:
            findings.append({
                "severity": "LOW",
                "rule": "AUDIT_LOG",
                "description": f"Node {node} did not log: {node} in audit_log",
                "recommendation": "Ensure all nodes log properly"
            })
    
    # Create audit summary
    audit_summary = {
        "task_id": task_id,
        "timestamp": datetime.now().isoformat(),
        "stage_reached": current_stage,
        "halted": pending_halt,
        "total_findings": len(findings),
        "high_severity": len([f for f in findings if f["severity"] == "HIGH"]),
        "medium_severity": len([f for f in findings if f["severity"] == "MEDIUM"]),
        "low_severity": len([f for f in findings if f["severity"] == "LOW"]),
        "findings": findings,
        "audited_by": "Nova"
    }
    
    nova_findings.append(audit_summary)
    audit_log.append({
        "node": "nova",
        "timestamp": datetime.now().isoformat(),
        "action": "AUDIT_COMPLETE",
        "result": "ISSUES_FOUND" if findings else "CLEAN",
        "findings_count": len(findings)
    })
    
    return {
        **state,
        "nova_findings": nova_findings,
        "audit_log": audit_log,
        "updated_at": datetime.now().isoformat()
    }
