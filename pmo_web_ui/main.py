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
    upsert_artifact_tool,
    get_artifacts_tool,
    create_acceptance_package_tool,
    get_acceptance_package_tool,
    approve_acceptance_tool,
    reject_acceptance_tool,
    get_advisories_tool,
    raise_advisory_tool,
    acknowledge_advisory_tool,
    get_blockers_tool,
    raise_blocker_tool,
    resolve_blocker_tool,
    validate_intake_tool,
    complete_intake_tool,
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
    "project_not_found": 404,
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
    """Announce kickoff — requires project_id (V1.5: explicit project required)."""
    required = ["title", "project_id", "description", "priority", "actor"]
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
    """
    Create a new project with structured intake.
    
    Enforces that intake_summary, intake_deliverable, intake_business_context
    are present and non-empty at creation time (governed intake contract).
    """
    required = ["project_name", "project_goal", "project_owner",
                "intake_summary", "intake_deliverable", "intake_business_context"]
    for field in required:
        if field not in body or not str(body[field]).strip():
            return JSONResponse(
                content={"ok": False, "error_type": "validation_error",
                         "message": f"Missing required intake field: {field}"},
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


# ---------------------------------------------------------------------------
# Artifact endpoints
# ---------------------------------------------------------------------------

@app.get("/projects/{project_id}/artifacts")
def get_project_artifacts(project_id: str):
    """Get all artifacts for a project with completeness status."""
    result = get_artifacts_tool({"project_id": project_id})
    if not result.get("ok", False):
        return _tool_error(result)
    return result


@app.post("/projects/{project_id}/artifacts")
def upsert_artifact(project_id: str, body: dict):
    """Add or update an artifact for a project."""
    required = ["artifact_type", "produced_by"]
    for field in required:
        if field not in body:
            return JSONResponse(
                content={"ok": False, "error_type": "validation_error",
                         "message": f"Missing field: {field}"},
                status_code=422,
            )
    body["project_id"] = project_id
    result = upsert_artifact_tool(body)
    if not result.get("ok", False):
        return _tool_error(result)
    return result


# ---------------------------------------------------------------------------
# Acceptance endpoints
# ---------------------------------------------------------------------------

@app.get("/projects/{project_id}/acceptance-package")
def get_acceptance_package(project_id: str):
    """Get acceptance package for a project."""
    result = get_acceptance_package_tool({"project_id": project_id})
    if not result.get("ok", False):
        return _tool_error(result)
    return result


@app.post("/projects/{project_id}/acceptance-package")
def create_acceptance_package(project_id: str, body: dict):
    """Create or update acceptance package for a project."""
    body["project_id"] = project_id
    result = create_acceptance_package_tool(body)
    if not result.get("ok", False):
        return _tool_error(result)
    return result


@app.post("/projects/{project_id}/acceptance-package/approve")
def approve_acceptance(project_id: str, body: dict):
    """Approve an acceptance package."""
    required = ["actor"]
    for field in required:
        if field not in body:
            return JSONResponse(
                content={"ok": False, "error_type": "validation_error",
                         "message": f"Missing field: {field}"},
                status_code=422,
            )
    body["project_id"] = project_id
    result = approve_acceptance_tool(body)
    if not result.get("ok", False):
        return _tool_error(result)
    return result


@app.post("/projects/{project_id}/acceptance-package/reject")
def reject_acceptance(project_id: str, body: dict):
    """Reject an acceptance package and request revision."""
    required = ["actor", "reason"]
    for field in required:
        if field not in body:
            return JSONResponse(
                content={"ok": False, "error_type": "validation_error",
                         "message": f"Missing field: {field}"},
                status_code=422,
            )
    body["project_id"] = project_id
    result = reject_acceptance_tool(body)
    if not result.get("ok", False):
        return _tool_error(result)
    return result


# ---------------------------------------------------------------------------
# Advisory endpoints
# ---------------------------------------------------------------------------

@app.get("/projects/{project_id}/advisories")
def get_advisories(project_id: str):
    """Get active advisory signals for a project."""
    result = get_advisories_tool({"project_id": project_id})
    if not result.get("ok", False):
        return _tool_error(result)
    return result


@app.post("/projects/{project_id}/advisories")
def raise_advisory(project_id: str, body: dict):
    """Raise an advisory signal for a project."""
    body["project_id"] = project_id
    result = raise_advisory_tool(body)
    if not result.get("ok", False):
        return _tool_error(result)
    return result


@app.post("/projects/{project_id}/advisories/{advisory_id}/acknowledge")
def acknowledge_advisory(project_id: str, advisory_id: str):
    """Acknowledge/dismiss an advisory signal."""
    result = acknowledge_advisory_tool({"project_id": project_id, "advisory_id": advisory_id})
    if not result.get("ok", False):
        return _tool_error(result)
    return result


# ---------------------------------------------------------------------------
# Blocker endpoints
# ---------------------------------------------------------------------------

@app.get("/projects/{project_id}/blockers")
def get_blockers(project_id: str, task_id: str | None = None):
    """Get active blockers for a project (optionally filtered by task)."""
    result = get_blockers_tool({"project_id": project_id, "task_id": task_id})
    if not result.get("ok", False):
        return _tool_error(result)
    return result


@app.post("/projects/{project_id}/blockers")
def raise_blocker(project_id: str, body: dict):
    """Raise a blocker for a task."""
    body["project_id"] = project_id
    result = raise_blocker_tool(body)
    if not result.get("ok", False):
        return _tool_error(result)
    return result


@app.post("/projects/{project_id}/blockers/{blocker_id}/resolve")
def resolve_blocker(project_id: str, blocker_id: str, body: dict):
    """Resolve/dismiss a blocker."""
    body["project_id"] = project_id
    body["blocker_id"] = blocker_id
    result = resolve_blocker_tool(body)
    if not result.get("ok", False):
        return _tool_error(result)
    return result


# ---------------------------------------------------------------------------
# Intake endpoints (V1.6)
# ---------------------------------------------------------------------------

@app.post("/intake/validate")
def intake_validate(body: dict):
    """
    Validate whether a project has all required intake fields present.

    Required: project_id
    Returns: {ok, project_id, intake_complete, missing_fields, message}
    """
    required = ["project_id"]
    for field in required:
        if field not in body:
            return JSONResponse(
                content={"ok": False, "error_type": "validation_error",
                         "message": f"Missing field: {field}"},
                status_code=422,
            )
    result = validate_intake_tool(body)
    if not result.get("ok", False):
        return _tool_error(result)
    return result


@app.post("/intake/complete")
def intake_complete(body: dict):
    """
    Mark a project's structured intake as complete.
    Validates all required fields are present before marking complete.
    Once complete, enables kickoff.

    Required: project_id, actor
    Returns: {ok, project_id, intake_complete, message}
    """
    required = ["project_id", "actor"]
    for field in required:
        if field not in body:
            return JSONResponse(
                content={"ok": False, "error_type": "validation_error",
                         "message": f"Missing field: {field}"},
                status_code=422,
            )
    result = complete_intake_tool(body)
    if not result.get("ok", False):
        return _tool_error(result)
    return result


# ---------------------------------------------------------------------------
# Agent spawn endpoint
# ---------------------------------------------------------------------------


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


@app.get("/test-spawn")
def test_spawn():
    """EXPERIMENTAL runtime verification endpoint — remove or protect before production.

    Tests sessions_spawn import + call from FastAPI process.
    Not part of V1.5 product surface.
    """
    try:
        from openclaw import sessions_spawn
        import_result = {"ok": True, "imported": True}
    except ImportError as e:
        return {
            "ok": False,
            "sessions_spawn_imported": False,
            "error": f"ImportError: {e}",
        }

    try:
        result = sessions_spawn(
            task="You are a test agent. Reply with the word 'ping' only.",
            runtime="subagent",
            agentId="viper",
            mode="run",
        )
        return {
            "ok": True,
            "sessions_spawn_imported": True,
            "spawned": True,
            "session_key": result.get("sessionKey"),
            "agentId": "viper",
        }
    except Exception as e:
        return {
            "ok": True,
            "sessions_spawn_imported": True,
            "spawned": False,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
