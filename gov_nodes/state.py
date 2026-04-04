# Governance State Definition
from typing import TypedDict, Literal
from datetime import datetime

class GovernanceState(TypedDict, total=False):
    # 任务信息
    task_id: str
    task_description: str
    current_stage: str  # "INTAKE" | "BA" | "SA" | "DEV" | "QA" | "DONE" | "HALTED"
    
    # APQ 授权
    apq_authorized: bool
    authorization_source: str | None  # APQ item ID or None
    
    # 治理状�?    pending_halt: bool
    halt_reason: str | None
    governance_violations: list[str]
    
    # 执行状�?(artifacts)
    prd_content: str | None
    spec_content: str | None
    deliverable_content: str | None
    qa_report: str | None
    qa_approved: bool | None
    
    # 审计
    audit_log: list[dict]
    nova_findings: list[dict]
    
    # 元数�?    created_at: str
    updated_at: str
    created_by: str | None
