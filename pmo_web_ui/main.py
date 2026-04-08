"""
PMO Web UI — FastAPI server
Serves the PMO dashboard and proxies gov_langgraph tool calls.

Port: configurable via PMO_PORT env (default 8000)
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager

# Ensure gov_langgraph is on path
_ROOT = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(_ROOT, ".."))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from gov_langgraph.openclaw_integration.tools import (
    init_harness,
    get_status_tool,
    approve_gate_tool,
    reject_gate_tool,
    create_task_tool,
    list_tasks_tool,
)

# ---------------------------------------------------------------------------
# App init
# ---------------------------------------------------------------------------

PORT = int(os.getenv("PMO_PORT", "8000"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_harness()
    yield

app = FastAPI(title="PMO Web UI", version="1.0.0", lifespan=lifespan)

# CORS — allow local browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

app.mount("/static", StaticFiles(directory=os.path.join(_ROOT, "static")), name="static")


@app.get("/")
def root():
    return FileResponse(os.path.join(_ROOT, "static", "index.html"))


# ---------------------------------------------------------------------------
# Tool endpoints
# ---------------------------------------------------------------------------

@app.get("/status/{task_id}")
def status(task_id: str):
    result = get_status_tool({"task_id": task_id})
    if not result.get("ok", False):
        raise HTTPException(status_code=404, detail=result.get("message", "Task not found"))
    return result


@app.post("/gate/approve")
def gate_approve(body: dict):
    required = ["task_id", "gate_name", "actor"]
    for field in required:
        if field not in body:
            raise HTTPException(status_code=422, detail=f"Missing field: {field}")
    result = approve_gate_tool(body)
    if not result.get("ok", False):
        raise HTTPException(status_code=400, detail=result.get("message", "Approval failed"))
    return result


@app.post("/gate/reject")
def gate_reject(body: dict):
    required = ["task_id", "gate_name", "actor"]
    for field in required:
        if field not in body:
            raise HTTPException(status_code=422, detail=f"Missing field: {field}")
    result = reject_gate_tool(body)
    if not result.get("ok", False):
        raise HTTPException(status_code=400, detail=result.get("message", "Rejection failed"))
    return result


@app.post("/kickoff")
def kickoff(body: dict):
    required = ["task_title", "project_id", "current_owner", "current_stage", "actor"]
    for field in required:
        if field not in body:
            raise HTTPException(status_code=422, detail=f"Missing field: {field}")
    result = create_task_tool(body)
    if not result.get("ok", False):
        raise HTTPException(status_code=400, detail=result.get("message", "Kickoff failed"))
    return result


@app.get("/tasks/{project_id}")
def tasks(project_id: str):
    result = list_tasks_tool({"project_id": project_id})
    if not result.get("ok", False):
        raise HTTPException(status_code=400, detail=result.get("message", "Failed to list tasks"))
    return result


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
