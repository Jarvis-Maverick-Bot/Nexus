# Maverick - PMO Coordinator Node
from typing import Literal
from datetime import datetime


def maverick_evaluate(state: dict) -> dict:
    """
    Maverick: PMO Coordinator
    
    Responsibilities:
    - Evaluate task against APQ (Approved Qualified Pipeline)
    - Decide: authorize routing or halt
    - Log governance decisions
    
    Rules:
    - If task not in APQ -> halt immediately
    - If task authorized -> route to BA
    - Track all decisions in audit log
    """
    task_id = state.get("task_id", "")
    task_desc = state.get("task_description", "")
    apq_authorized = state.get("apq_authorized", False)
    audit_log = state.get("audit_log", [])
    
    decision = {
        "node": "maverick",
        "timestamp": datetime.now().isoformat(),
        "task_id": task_id,
        "action": None,
        "result": None
    }
    
    # Check APQ authorization
    if not apq_authorized:
        decision["action"] = "APQ_CHECK"
        decision["result"] = "DENIED"
        decision["reason"] = "Task not in approved queue"
        
        audit_log.append(decision)
        
        return {
            **state,
            "pending_halt": True,
            "halt_reason": f"APQ authorization required for task: {task_id}",
            "governance_violations": state.get("governance_violations", []) + ["APQ_REQUIRED"],
            "audit_log": audit_log,
            "updated_at": datetime.now().isoformat()
        }
    
    # Authorized
    decision["action"] = "APQ_CHECK"
    decision["result"] = "APPROVED"
    decision["reason"] = "Task authorized by APQ"
    
    audit_log.append(decision)
    
    return {
        **state,
        "pending_halt": False,
        "current_stage": "BA",
        "audit_log": audit_log,
        "updated_at": datetime.now().isoformat()
    }


def maverick_route(state: dict) -> str:
    """
    Route to next stage based on current state.
    
    Returns:
    - "viper_ba" -> Start BA stage
    - "halted" -> Stop pipeline
    """
    if state.get("pending_halt"):
        return "halted"
    
    return "viper_ba"
