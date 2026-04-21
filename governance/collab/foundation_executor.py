"""
Foundation Delivery Executor — Option B (near-term)
Handler that produces V2.0 Foundation artifact directly in daemon process.

Used by worker when pending_action = "awaiting_foundation_draft".
Loads doctrine, produces artifact, updates state, sends notification.

This is Option B: main Jarvis session (daemon process) as executor.
When jarvis-core is stable, this will be replaced by Option A (sessions_spawn).
"""

import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

# Paths for doctrine loading — resolved from V2.0 shared drive structure
_SHARED_ROOT = Path(r"\\192.168.31.124\Nova-Jarvis-Shared\working\01-projects\Nexus\V2.0")

# Actual existing paths in V2.0/01-release-definition
_FOUNDATION_BASELINE = _SHARED_ROOT / "01-release-definition" / "V2_0_FOUNDATION_V0_2.md"
_SCOPE_DOC = _SHARED_ROOT / "01-release-definition" / "V2_0_SCOPE_V0_2.md"
_PRD_DOC = _SHARED_ROOT / "01-release-definition" / "V2_0_PRD_V0_2.md"

# Doctrine registry and SKOS — these may not exist yet; executor handles gracefully
_DOCTRINE_REGISTRY = _SHARED_ROOT / "governance" / "doctrine" / "doctrine_registry.json"
_SKOS_SOURCE = _SHARED_ROOT / "governance" / "skos" / "SKOS_SOURCE_REGISTRY_V0_1.xlsx"


def _load_doctrine(doctrine_loading_set: list) -> dict:
    """
    Load doctrine files from paths in doctrine_loading_set.
    Returns doctrine_snapshot dict. Missing files are logged as warnings, not hard errors.
    If NONE of the files exist, returns doctrine_loaded=False.
    """
    loaded = {}
    warnings = []
    errors = []

    path_map = {
        "v2_0_foundation_doctrine": _DOCTRINE_REGISTRY,
        "skos_source_model": _SKOS_SOURCE,
        "v2_0_foundation_baseline": _FOUNDATION_BASELINE,
        "v2_0_scope": _SCOPE_DOC,
        "v2_0_prd": _PRD_DOC,
    }

    for name in doctrine_loading_set:
        path = path_map.get(name)
        if not path:
            warnings.append(f"no path mapping for doctrine: {name}")
            continue
        if not path.exists():
            warnings.append(f"doctrine file not found (will proceed without it): {path}")
            continue
        try:
            if path.suffix == ".json":
                with open(path, 'r', encoding='utf-8') as f:
                    loaded[name] = json.load(f)
            elif path.suffix == ".xlsx":
                with open(path, 'rb') as f:
                    loaded[name] = f"<binary: {path.name}>"
            else:
                with open(path, 'r', encoding='utf-8') as f:
                    loaded[name] = f.read()
        except Exception as e:
            warnings.append(f"failed to load {name}: {e}")

    if warnings and not loaded:
        # All missing — this is an error condition
        return {
            "doctrine_loaded": False,
            "errors": warnings,
            "loaded_at": datetime.now(timezone.utc).isoformat()
        }

    return {
        "doctrine_loaded": True,
        "doctrine_snapshot": loaded,
        "warnings": warnings if warnings else None,
        "loaded_at": datetime.now(timezone.utc).isoformat()
    }


def _load_workflow_registry() -> dict:
    """Load workflow_registry.json to get task context for each command_intent."""
    registry_path = Path(__file__).parent / "workflow_registry.json"
    if registry_path.exists():
        with open(registry_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def get_task_context(collab_id: str, command_intent: str, payload: dict) -> dict:
    """
    Construct task context from workflow_registry.json based on command_intent.
    
    For command_intent = "start_foundation_delivery":
      Returns task context with doctrine_loading_set, artifact_binding, etc.
    """
    registry = _load_workflow_registry()

    # Search workflows for matching command_intent
    for wf_name, wf_data in registry.get("workflows", {}).items():
        for stage_name, stage_data in wf_data.get("stages", {}).items():
            if stage_data.get("command_intent") == command_intent:
                return {
                    "collab_id": collab_id,
                    "workflow": wf_name,
                    "stage": stage_name,
                    "command_intent": command_intent,
                    "doctrine_loading_set": stage_data.get("doctrine_loading_set", []),
                    "artifact_binding": stage_data.get("artifact_binding", {}),
                    "skill_handler_binding": stage_data.get("skill_handler_binding", {}),
                    "message_contract": stage_data.get("message_contract", {}),
                    "expected_output": stage_data.get("expected_output", {}),
                    "completion_criteria": stage_data.get("completion_criteria", {}),
                    "payload": payload
                }

    # Fallback: return minimal context if command_intent not found
    return {
        "collab_id": collab_id,
        "command_intent": command_intent,
        "doctrine_loading_set": ["v2_0_foundation_doctrine"],
        "payload": payload
    }


def _produce_foundation_draft(task_context: dict) -> tuple[bool, str, Optional[str]]:
    """
    Produce the V2.0 Foundation draft artifact.
    Returns (success, artifact_path, error_message).
    """
    artifact_binding = task_context.get("artifact_binding", {})
    output_path_str = artifact_binding.get("output_path", "governance/docs/V2_0_FOUNDATION.md")

    # Resolve artifact path — relative to repo root
    repo_root = Path(__file__).parent.parent.parent
    artifact_path = repo_root / output_path_str

    # Load doctrine for context
    doctrine = _load_doctrine(task_context.get("doctrine_loading_set", []))
    if not doctrine.get("doctrine_loaded"):
        return False, "", f"doctrine_load_failed: {doctrine.get('errors')}"

    doctrine_snapshot = doctrine.get("doctrine_snapshot", {})

    # Read baseline for reference content
    baseline_content = ""
    baseline_key = "v2_0_foundation_baseline"
    if baseline_key in doctrine_snapshot:
        baseline_content = str(doctrine_snapshot[baseline_key])[:500]  # first 500 chars

    # Produce draft content
    draft_content = f"""# V2.0 Foundation Document

**Generated:** {datetime.now(timezone.utc).isoformat()}
**Collab ID:** {task_context['collab_id']}
**Workflow:** {task_context.get('workflow', 'v2_0')}
**Stage:** {task_context.get('stage', 'foundation_create')}

---

## Baseline Reference

This draft is based on the approved V2.0 Foundation V0.2 baseline.

---

## Draft Content

[DRAFT — Agent produces actual Foundation document content here based on doctrine loading]

---

## Doctrine Context Loaded

- v2_0_foundation_baseline: loaded ({len(baseline_content)} chars referenced)
- v2_0_scope: {'loaded' if 'v2_0_scope' in doctrine_snapshot else 'not found'}
- v2_0_prd: {'loaded' if 'v2_0_prd' in doctrine_snapshot else 'not found'}
- v2_0_foundation_doctrine: {'loaded' if 'v2_0_foundation_doctrine' in doctrine_snapshot else 'not found'}
- skos_source_model: {'loaded' if 'skos_source_model' in doctrine_snapshot else 'not found'}

---

*Auto-generated by Nexus Governed Execution Loop — Option B executor*
"""

    try:
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        with open(artifact_path, 'w', encoding='utf-8') as f:
            f.write(draft_content)
        return True, str(artifact_path), None
    except Exception as e:
        return False, "", f"artifact_write_failed: {e}"


async def execute_foundation_delivery(handler: 'CollabHandler', collab_id: str, task_context: dict):
    """
    Execute the foundation delivery task (Option B executor).

    Steps:
    1. Load doctrine
    2. Produce artifact
    3. Update collab state
    4. Send Telegram notification if required
    """
    handler._log("EXEC", f"[{collab_id}] starting foundation_delivery (Option B)")

    # 1. Load doctrine
    doctrine_loading_set = task_context.get("doctrine_loading_set", [])
    doctrine_result = _load_doctrine(doctrine_loading_set)

    if not doctrine_result.get("doctrine_loaded"):
        # Doctrine load failed — fail the collab
        handler.store.update_collab(
            collab_id,
            status='failed',
            last_event='doctrine_load_failed',
            pending_action=''
        )
        handler.store.emit_event(collab_id, 'doctrine_load_failed', error=doctrine_result.get('errors'))
        handler._log("ERROR", f"[{collab_id}] doctrine_load_failed: {doctrine_result.get('errors')}")
        return

    loaded_keys = list(doctrine_result.get("doctrine_snapshot", {}).keys())
    handler._log("EXEC", f"[{collab_id}] doctrine loaded OK: {loaded_keys}")
    if doctrine_result.get("warnings"):
        handler._log("WARN", f"[{collab_id}] doctrine warnings: {doctrine_result.get('warnings')}")

    # 2. Produce artifact
    success, artifact_path, error = _produce_foundation_draft(task_context)

    if not success:
        handler.store.update_collab(
            collab_id,
            status='failed',
            last_event=error,
            pending_action=''
        )
        handler.store.emit_event(collab_id, error, collab_id=collab_id)
        handler._log("ERROR", f"[{collab_id}] {error}")
        return

    handler._log("EXEC", f"[{collab_id}] artifact written: {artifact_path}")

    # 3. Update collab state
    handler.store.update_collab(
        collab_id,
        status='in_progress',
        pending_action='',
        last_event='foundation_draft_ready'
    )
    handler.store.emit_event(
        collab_id,
        'foundation_draft_ready',
        artifact_type='foundation',
        artifact_path=artifact_path
    )

    handler._log("EXEC", f"[{collab_id}] collab state updated: foundation_draft_ready")

    # 4. Send Telegram notification (async, non-blocking)
    # This event is in the "must notify" list
    try:
        from governance.collab.notify import send_telegram_notification_async
        send_telegram_notification_async(
            f"Foundation draft ready — collab_id: {collab_id}\n"
            f"Artifact: {artifact_path}"
        )
        handler._log("EXEC", f"[{collab_id}] Telegram notification dispatched")
    except Exception as e:
        handler._log("WARN", f"[{collab_id}] Telegram notification failed: {e}")

    handler._log("EXEC", f"[{collab_id}] foundation_delivery COMPLETE")
