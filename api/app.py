"""
FastAPI Application for Governance LangGraph
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
import uuid

from gov_nodes.pipeline import run_pipeline

app = FastAPI(title="Governance LangGraph API")


class TaskRequest(BaseModel):
    task_description: str
    apq_authorized: bool = False
    created_by: str | None = None


class TaskResponse(BaseModel):
    task_id: str
    status: str
    current_stage: str
    apq_authorized: bool
    qa_approved: bool | None
    qa_report: str | None
    pending_halt: bool
    halt_reason: str | None
    nova_findings: list


@app.get("/")
async def root():
    return {
        "name": "Governance LangGraph API",
        "version": "0.1",
        "status": "running"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/task")
async def create_task(request: TaskRequest):
    """Create and run a governance pipeline task."""
    
    task_id = f"task-{uuid.uuid4().hex[:8]}"
    
    try:
        result = run_pipeline(
            task_id=task_id,
            task_description=request.task_description,
            apq_authorized=request.apq_authorized,
            created_by=request.created_by
        )
        
        return TaskResponse(
            task_id=task_id,
            status="completed" if result.get('current_stage') == "DONE" else "halted",
            current_stage=result.get('current_stage', 'UNKNOWN'),
            apq_authorized=result.get('apq_authorized', False),
            qa_approved=result.get('qa_approved'),
            qa_report=result.get('qa_report'),
            pending_halt=result.get('pending_halt', False),
            halt_reason=result.get('halt_reason'),
            nova_findings=result.get('nova_findings', [])
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/task/{task_id}")
async def get_task(task_id: str):
    """Get task status (placeholder - tasks are in-memory)."""
    return {
        "task_id": task_id,
        "status": "not_implemented",
        "message": "Task state persistence not yet implemented"
    }
