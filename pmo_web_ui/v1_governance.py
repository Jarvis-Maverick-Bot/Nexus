"""
V1.8 Governance UI — Thin visibility layer for V1.8 delivery.

Adds V1.8-specific routes on top of existing PMO Web UI:
  /v1.8/workflow   — active delivery items with status
  /v1.8/queue      — V1.8 delivery queue
  /v1.8/artifacts  — artifact/review visibility
  /v1.8/approvals  — human approval surfaces

Data served from PMO CLI state store (governance/pmo/data/).

Port: configurable via PMO_PORT env (default 8000)
"""

import sys
import json
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT))

from fastapi import APIRouter
from governance.pmo.pmo_cli import status, get_event_log, get_task_log

router = APIRouter(prefix="/v1.8", tags=["V1.8 Delivery"])


@router.get("/workflow")
def workflow():
    """Active delivery items with current stage."""
    result = status()
    if not result.get("ok"):
        return {"items": [], "error": result.get("error", "unknown")}
    items = result.get("items", [])
    # Add human-readable stage labels
    stage_labels = {
        "BACKLOG": "Backlog",
        "IN_PROGRESS": "In Progress",
        "IN_REVIEW": "In Review",
        "APPROVED": "Approved",
        "DELIVERED": "Delivered",
    }
    enriched = []
    for item in items:
        stage = item.get("stage", "UNKNOWN")
        enriched.append({
            "id": item.get("id"),
            "name": item.get("name"),
            "stage": stage,
            "stage_label": stage_labels.get(stage, stage),
            "artifacts": len(item.get("artifacts", [])),
            "validations": len(item.get("validations", [])),
            "blockers": len([b for b in item.get("blockers", []) if not b.get("resolved")]),
            "updated_at": item.get("updated_at"),
        })
    return {
        "ok": True,
        "total": len(enriched),
        "items": enriched,
        "note": "Data sourced from PMO CLI state store",
    }


@router.get("/queue")
def queue():
    """V1.8 delivery queue — items not yet delivered."""
    result = status()
    if not result.get("ok"):
        return {"items": [], "error": result.get("error", "unknown")}
    items = result.get("items", [])
    queue_items = [i for i in items if i.get("stage") != "DELIVERED"]
    stage_order = ["IN_REVIEW", "IN_PROGRESS", "BACKLOG"]
    queue_items.sort(key=lambda x: stage_order.index(x.get("stage", "")) if x.get("stage") in stage_order else 99)
    return {
        "ok": True,
        "total": len(queue_items),
        "items": [{
            "id": i.get("id"),
            "name": i.get("name"),
            "stage": i.get("stage"),
            "waiting_on": "PMO" if i.get("stage") == "IN_REVIEW" else "DEV",
        } for i in queue_items],
    }


@router.get("/artifacts")
def artifacts():
    """Artifact/review visibility — all items with artifact counts."""
    result = status()
    if not result.get("ok"):
        return {"items": [], "error": result.get("error", "unknown")}
    items = result.get("items", [])
    artifact_list = []
    for item in items:
        for art in item.get("artifacts", []):
            artifact_list.append({
                "item_id": item.get("id"),
                "item_name": item.get("name"),
                "artifact_id": art.get("id"),
                "path": art.get("path"),
                "name": art.get("name"),
                "submitted_at": art.get("submitted_at"),
            })
    return {
        "ok": True,
        "total": len(artifact_list),
        "artifacts": artifact_list,
        "note": "Each artifact links to a delivery item",
    }


@router.get("/approvals")
def approvals():
    """Human approval surfaces — items currently in IN_REVIEW."""
    result = status()
    if not result.get("ok"):
        return {"items": [], "error": result.get("error", "unknown")}
    items = result.get("items", [])
    review_items = [i for i in items if i.get("stage") == "IN_REVIEW"]
    return {
        "ok": True,
        "total": len(review_items),
        "items": [{
            "id": item.get("id"),
            "name": item.get("name"),
            "stage": item.get("stage"),
            "artifacts": len(item.get("artifacts", [])),
            "validations": item.get("validations", []),
            "updated_at": item.get("updated_at"),
        } for item in review_items],
        "note": "These items require human sign-off before transition to APPROVED",
    }


@router.get("/events")
def events():
    """V1.8 event log summary — last 20 events."""
    log = get_event_log()
    events = log.get("events", [])[-20:]
    return {
        "ok": True,
        "total": len(events),
        "events": events,
    }


@router.get("/tasks")
def tasks():
    """V1.8 task control log — recent task actions."""
    log = get_task_log()
    return {
        "ok": True,
        "total": log.get("total", 0),
        "log": log.get("log", []),
    }


@router.get("/health")
def health():
    """Lightweight health check for the governance UI."""
    return {"ok": True, "service": "v1.8-governance-ui", "status": "healthy"}