# Viper BA - Business Analyst Node
from datetime import datetime


def viper_ba_execute(state: dict) -> dict:
    """
    Viper-BA: Business Analyst
    
    Responsibilities:
    - Create PRD (Product Requirements Document)
    - Capture task requirements
    - Output structured PRD content
    
    Rules:
    - Only create PRD content
    - Do not create specs or code
    - Return PRD in state
    """
    task_id = state.get("task_id", "unknown")
    task_desc = state.get("task_description", "")
    audit_log = state.get("audit_log", [])
    
    # Create PRD
    prd_content = f"""# Product Requirements Document

## Task: {task_id}

## Description
{task_desc}

## Requirements
- [ ] Requirement 1
- [ ] Requirement 2

## Acceptance Criteria
- [ ] Criteria 1
- [ ] Criteria 2

## Notes
- Created by Viper-BA
- Timestamp: {datetime.now().isoformat()}
"""
    
    decision = {
        "node": "viper_ba",
        "timestamp": datetime.now().isoformat(),
        "task_id": task_id,
        "action": "CREATE_PRD",
        "result": "SUCCESS",
        "stage_completed": "BA"
    }
    
    audit_log.append(decision)
    
    return {
        **state,
        "prd_content": prd_content,
        "current_stage": "SA",
        "audit_log": audit_log,
        "updated_at": datetime.now().isoformat()
    }
