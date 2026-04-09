"""
PMO Web UI — FastAPI server
Serves the PMO dashboard and proxies gov_langgraph tool calls.

Port: configurable via PMO_PORT env (default 8000)
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager

_ROOT = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(_ROOT, ".."))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from gov_langgraph.openclaw_integration.tools import (
    init_harness,
    get_status_tool,
    get_gate_panel_tool,
    approve_gate_tool,
    reject_gate_tool,
    kickoff_task_tool,
    list_tasks_tool,
    create_project_tool,
    get_project_tool,
    list_projects_tool,
    spawn_agent_tool,
)

PORT = int(os.getenv("PMO_PORT", "8000"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_harness()
    yield


app = FastAPI(title="PMO Web UI", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=os.path.join(_ROOT, "static")), name="static")


@app.get("/")
def root():
    return FileResponse(os.path.join(_ROOT, "static", "index.html"))


# ---------------------------------------------------------------------------
# Error helpers
# ---------------------------------------------------------------------------

_ERROR_TYPE_STATUS = {
    "platform_unavailable": 503,
    "task_not_found": 404,
    "validation_error": 422,
    "already_decided": 409,
    "terminal_state": 409,
    "unknown": 500,
}


def _tool_error(result: dict) -> JSONResponse:
    """Convert a tool error dict to a JSONResponse with HTTP status mapped from error_type."""
    error_type = result.get("error_type", "unknown")
    status_code = _ERROR_TYPE_STATUS.get(error_type, 500)
    return JSONResponse(content=result, status_code=status_code)


# ---------------------------------------------------------------------------
# Tool endpoints
# ---------------------------------------------------------------------------

@app.get("/status/{task_id}")
def status(task_id: str):
    result = get_status_tool({"task_id": task_id})
    if not result.get("ok", False):
        return _tool_error(result)
    return result


@app.post("/gate/approve")
def gate_approve(body: dict):
    required = ["task_id", "gate_name", "actor"]
    for field in required:
        if field not in body:
            return JSONResponse(
                content={"ok": False, "error_type": "validation_error",
                         "message": f"Missing field: {field}"},
                status_code=422,
            )
    result = approve_gate_tool(body)
    if not result.get("ok", False):
        return _tool_error(result)
    return result


@app.post("/gate/reject")
def gate_reject(body: dict):
    required = ["task_id", "gate_name", "actor"]
    for field in required:
        if field not in body:
            return JSONResponse(
                content={"ok": False, "error_type": "validation_error",
                         "message": f"Missing field: {field}"},
                status_code=422,
            )
    result = reject_gate_tool(body)
    if not result.get("ok", False):
        return _tool_error(result)
    return result


@app.post("/kickoff")
def kickoff(body: dict):
    required = ["title", "description", "priority", "actor"]
    for field in required:
        if field not in body:
            return JSONResponse(
                content={"ok": False, "error_type": "validation_error",
                         "message": f"Missing field: {field}"},
                status_code=422,
            )
    result = kickoff_task_tool(body)
    if not result.get("ok", False):
        return _tool_error(result)
    return result


@app.get("/tasks/{project_id}")
def tasks(project_id: str):
    result = list_tasks_tool({"project_id": project_id})
    if not result.get("ok", False):
        return _tool_error(result)
    return result


@app.get("/gate/{task_id}")
def gate_panel(task_id: str):
    """Get gate panel for a task — PMO gate confirmation surface."""
    result = get_gate_panel_tool({"task_id": task_id})
    if not result.get("ok", False):
        return _tool_error(result)
    return result


# ---------------------------------------------------------------------------
# Project endpoints
# ---------------------------------------------------------------------------

@app.post("/projects")
def create_project(body: dict):
    """Create a new project."""
    required = ["project_name", "project_goal", "project_owner"]
    for field in required:
        if field not in body:
            return JSONResponse(
                content={"ok": False, "error_type": "validation_error",
                         "message": f"Missing field: {field}"},
                status_code=422,
            )
    result = create_project_tool(body)
    if not result.get("ok", False):
        return _tool_error(result)
    return result


@app.get("/projects")
def list_projects(status: str | None = None):
    """List all projects, optionally filtered by status."""
    result = list_projects_tool({"status": status})
    if not result.get("ok", False):
        return _tool_error(result)
    return result


@app.get("/projects/{project_id}")
def get_project(project_id: str):
    """Get details of a specific project."""
    result = get_project_tool({"project_id": project_id})
    if not result.get("ok", False):
        return _tool_error(result)
    return result


@app.post("/agents/spawn")
def spawn_agent(body: dict):
    """Spawn a known agent for a task via MaverickSpawner.

    Agent definitions are loaded from config/agents.yaml — no hardcoding.
    """
    required = ["project_id", "task_id"]
    for field in required:
        if field not in body:
            return JSONResponse(
                content={"ok": False, "error_type": "validation_error",
                         "message": f"Missing field: {field}"},
                status_code=422,
            )
    result = spawn_agent_tool(body)
    if not result.get("ok", False):
        return _tool_error(result)
    return result


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
