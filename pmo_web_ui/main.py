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
    get_artifact_tool,
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
    submit_prerequisite_tool,
    get_prerequisite_package_tool,
    get_output_package_tool,
    package_output_tool,
    request_ba_review_tool,
    request_sa_review_tool,
    request_qa_review_tool,
    record_review_outcome_tool,
    get_review_status_tool,
    recommend_kickoff_tool,
    create_game_tool,
    advance_game_stage_tool,
    get_game_tool,
    list_games_tool,
    raise_game_escalation_tool,
    submit_game_status_report_tool,
    approve_game_concept_tool,
)
from pmo_web_ui.v1_governance import router as v1_router

PORT = int(os.getenv("PMO_PORT", "8000"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_harness()
    yield


app = FastAPI(title="PMO Web UI", version="1.0.0", lifespan=lifespan)
app.include_router(v1_router)

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
    "reviews_incomplete": 409,
    "revision_needed": 409,
    "kickoff_blocked": 409,
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
    Create a new project in DRAFT state.

    V1.6: Required = project_name, project_goal, project_owner.
    Prerequisite package is initialized separately via POST /projects/{id}/prerequisites.
    """
    required = ["project_name", "project_goal", "project_owner"]
    for field in required:
        if field not in body or not str(body[field]).strip():
            return JSONResponse(
                content={"ok": False, "error_type": "validation_error",
                         "message": f"Missing required field: {field}"},
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


@app.get("/projects/{project_id}/prerequisites")
def get_prerequisites(project_id: str):
    """Get the prerequisite package state for a project (6 artifacts, submitted or pending)."""
    result = get_prerequisite_package_tool({"project_id": project_id})
    if not result.get("ok", False):
        return _tool_error(result)
    return result


@app.post("/projects/{project_id}/prerequisites")
def submit_prerequisite(project_id: str, body: dict):
    """
    Submit one prerequisite artifact.

    Required: artifact_type (scope|spec|arch|testcase|testreport|guideline)
    Optional: content_preview, producer, actor
    """
    required = ["artifact_type"]
    for field in required:
        if field not in body:
            return JSONResponse(
                content={"ok": False, "error_type": "validation_error",
                         "message": f"Missing field: {field}"},
                status_code=422,
            )
    body["project_id"] = project_id
    result = submit_prerequisite_tool(body)
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


@app.get("/projects/{project_id}/artifacts/{artifact_id}")
def get_artifact(project_id: str, artifact_id: str):
    """Get a single artifact by its artifact_id."""
    result = get_artifact_tool({"artifact_id": artifact_id})
    if not result.get("ok", False):
        return _tool_error(result)
    artifact = result.get("artifact")
    if artifact is None:
        return _tool_error({"error": "not_found", "message": "Artifact not found"})
    # Verify it belongs to the specified project
    if artifact.get("project_id") != project_id:
        return _tool_error({"error": "not_found", "message": "Artifact not found in this project"})
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
# Sprint 4R: Output Package endpoints
# ---------------------------------------------------------------------------

@app.get("/projects/{project_id}/output-package")
def get_output_package(project_id: str):
    """Get or build the output package for a project."""
    result = get_output_package_tool({"project_id": project_id})
    if not result.get("ok", False):
        return _tool_error(result)
    return result


@app.post("/projects/{project_id}/output-package")
def build_output_package(project_id: str):
    """Build (or rebuild) the output package from current delivered artifacts."""
    result = package_output_tool({"project_id": project_id})
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
# Sprint 2R: Pre-Kickoff Review Endpoints
# ---------------------------------------------------------------------------

@app.post("/projects/{project_id}/reviews/{reviewer}/request")
def request_review(project_id: str, reviewer: str, body: dict):
    """
    Request a pre-kickoff review from BA, SA, or QA.
    reviewer: 'ba' | 'sa' | 'qa'
    Required: actor
    """
    if reviewer not in ("ba", "sa", "qa"):
        return JSONResponse(
            content={"ok": False, "error_type": "validation_error",
                     "message": f"Invalid reviewer: {reviewer}. Must be ba, sa, or qa."},
            status_code=422,
        )
    body["project_id"] = project_id
    tool = {"ba": request_ba_review_tool, "sa": request_sa_review_tool, "qa": request_qa_review_tool}[reviewer]
    result = tool(body)
    if not result.get("ok", False):
        return _tool_error(result)
    return result


@app.post("/projects/{project_id}/reviews/{reviewer}/outcome")
def record_review_outcome(project_id: str, reviewer: str, body: dict):
    """
    Record a reviewer's outcome: APPROVED or REVISION_NEEDED.
    reviewer: 'ba' | 'sa' | 'qa'
    Required: outcome ('approved' | 'revision_needed'), actor
    Optional: note
    """
    if reviewer not in ("ba", "sa", "qa"):
        return JSONResponse(
            content={"ok": False, "error_type": "validation_error",
                     "message": f"Invalid reviewer: {reviewer}. Must be ba, sa, or qa."},
            status_code=422,
        )
    required = ["outcome", "actor"]
    for field in required:
        if field not in body:
            return JSONResponse(
                content={"ok": False, "error_type": "validation_error",
                         "message": f"Missing field: {field}"},
                status_code=422,
            )
    body["project_id"] = project_id
    body["reviewer"] = reviewer
    result = record_review_outcome_tool(body)
    if not result.get("ok", False):
        return _tool_error(result)
    return result


@app.get("/projects/{project_id}/review-status")
def get_review_status(project_id: str):
    """
    Get full pre-kickoff review status for a project.
    Returns BA/SA/QA review records + Maverick recommendation.
    """
    result = get_review_status_tool({"project_id": project_id})
    if not result.get("ok", False):
        return _tool_error(result)
    return result


@app.post("/projects/{project_id}/recommend-kickoff")
def recommend_kickoff(project_id: str, body: dict):
    """
    Maverick makes a kickoff recommendation: RECOMMEND_KICKOFF or RECOMMEND_REVISION.
    Required: recommendation ('recommend_kickoff' | 'recommend_revision'), actor
    Optional: note
    """
    required = ["recommendation", "actor"]
    for field in required:
        if field not in body:
            return JSONResponse(
                content={"ok": False, "error_type": "validation_error",
                         "message": f"Missing field: {field}"},
                status_code=422,
            )
    body["project_id"] = project_id
    result = recommend_kickoff_tool(body)
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
# Game production endpoints (Sprint 4R)
# ---------------------------------------------------------------------------

@app.post("/games")
def create_game(body: dict):
    """"Create a new game WorkItem at CONCEPT stage."""
    required = ["title", "owner"]
    for field in required:
        if field not in body or not str(body[field]).strip():
            return JSONResponse(
                content={"ok": False, "error_type": "validation_error",
                         "message": f"Missing required field: {field}"},
                status_code=422,
            )
    result = create_game_tool(body)
    if not result.get("ok", False):
        return _tool_error(result)
    return result


@app.get("/games")
def list_games(owner: str | None = None, stage: str | None = None):
    """List all game work items, optionally filtered."""
    input_dict = {}
    if owner:
        input_dict["owner"] = owner
    if stage:
        input_dict["stage"] = stage
    result = list_games_tool(input_dict)
    if not result.get("ok", False):
        return _tool_error(result)
    return result



@app.get("/games/{game_id}")
def get_game(game_id: str):
    """Get game details including game_fields."""
    result = get_game_tool({"game_id": game_id})
    if not result.get("ok", False):
        return _tool_error(result)
    return result


@app.post("/games/{game_id}/stage")
def advance_game_stage(game_id: str, body: dict):
    """
    Advance a game to a new stage.
    Required: new_stage, actor
    Optional: concept_approved, artifact_id, viper_triggered, trigger_note
    """
    required = ["new_stage", "actor"]
    for field in required:
        if field not in body:
            return JSONResponse(
                content={"ok": False, "error_type": "validation_error",
                         "message": f"Missing required field: {field}"},
                status_code=422,
            )
    body["game_id"] = game_id
    result = advance_game_stage_tool(body)
    if not result.get("ok", False):
        return _tool_error(result)
    return result


@app.post("/games/{game_id}/escalate")
def raise_game_escalation(game_id: str, body: dict):
    """PMO raises an escalation for a game."""
    required = ["reason"]
    for field in required:
        if field not in body:
            return JSONResponse(
                content={"ok": False, "error_type": "validation_error",
                         "message": f"Missing required field: {field}"},
                status_code=422,
            )
    body["game_id"] = game_id
    result = raise_game_escalation_tool(body)
    if not result.get("ok", False):
        return _tool_error(result)
    return result

@app.post("/games/{game_id}/status-report")
def submit_game_status_report(game_id: str, body: dict):
    """"Submit a status report for a game."""
    required = ["stage", "status", "progress", "next_action", "actor"]
    for field in required:
        if field not in body:
            return JSONResponse(
                content={"ok": False, "error_type": "validation_error",
                         "message": f"Missing required field: {field}"},
                status_code=422,
            )
    body["game_id"] = game_id
    result = submit_game_status_report_tool(body)
    if not result.get("ok", False):
        return _tool_error(result)
    return result

@app.post("/games/{game_id}/concept-approve")
def approve_game_concept(game_id: str, body: dict):
    """Record governance concept approval for a game."""
    body["game_id"] = game_id
    result = approve_game_concept_tool(body)
    if not result.get("ok", False):
        return _tool_error(result)
    return result


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
