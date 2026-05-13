"""Bounded Phase 3 UAT command execution bridge.

This module is intentionally narrow: it only executes the minimal Hello World
HTML UAT command after a real runtime intake has already created a pending task.
It is not a general dispatcher, scheduler, notification backend, or Phase 4
runtime controller.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from nexus.mq.durable_state import PendingTaskRecord


UTC = timezone.utc


@dataclass
class Phase3UatExecutionResult:
    executed: bool
    status: str
    artifact_path: Optional[str] = None
    runtime_record_id: Optional[str] = None
    outbox_id: Optional[str] = None
    error: Optional[str] = None


class Phase3UatCommandBridge:
    """Executes only the approved minimal Hello World HTML UAT command."""

    COMMAND_NAMES = {
        "hello_world",
        "hello_world_html",
        "create_hello_world_html",
        "generate_hello_world_html",
        "phase3_minimal_hello_world",
        "phase3_real_uat_hello_world",
    }

    PATH_KEYS = (
        "artifact_path",
        "output_path",
        "html_output_path",
        "shared_artifact_path",
        "wsl_artifact_path",
        "mounted_artifact_path",
    )

    def __init__(self, runtime):
        self.runtime = runtime

    def execute_if_supported(self, pending_task: PendingTaskRecord, envelope: Any) -> Phase3UatExecutionResult:
        if pending_task.state != "PENDING":
            return Phase3UatExecutionResult(executed=False, status="not_pending")

        payload = self._payload_from_pending_task(pending_task)
        if not self._is_supported_hello_world_command(payload):
            return Phase3UatExecutionResult(executed=False, status="unsupported_command")

        artifact_path = self._resolve_artifact_path(payload)
        if artifact_path is None:
            return self._mark_failed(
                pending_task,
                envelope,
                "MISSING_ARTIFACT_PATH",
                {"payload_keys": sorted(payload.keys())},
            )

        try:
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(self._html_document(payload, envelope), encoding="utf-8")
        except Exception as exc:
            return self._mark_failed(
                pending_task,
                envelope,
                f"ARTIFACT_WRITE_FAILED: {exc}",
                {"artifact_path": str(artifact_path)},
            )

        now_at = datetime.now(UTC).isoformat()
        result_payload = {
            "status": "artifact_generated",
            "artifact_path": str(artifact_path),
            "message_id": getattr(envelope, "message_id", pending_task.task_id.removeprefix("task-")),
            "correlation_id": pending_task.correlation_id,
            "generated_at": now_at,
            "scope": "phase3_minimal_uat_only",
        }
        outbox = self.runtime.state_store.create_outbox_record(
            side_effect_type="write_phase3_uat_artifact",
            target=str(artifact_path),
            correlation_id=pending_task.correlation_id,
            payload=result_payload,
            created_by=self.runtime.runtime_id,
            message_id=result_payload["message_id"],
            causation_id=getattr(envelope, "causation_id", None),
            max_retries=0,
        )
        self.runtime.state_store.mark_outbox_confirmed(outbox.outbox_id, confirmed_by=self.runtime.runtime_id)
        record = self.runtime.state_store.create_phase3_runtime_record(
            record_type="phase3_uat_command_execution_record",
            workflow_instance_id=pending_task.workflow_id,
            related_message_id=result_payload["message_id"],
            dedupe_key=f"phase3_uat_command_execution:{result_payload['message_id']}",
            status="artifact_generated",
            payload={
                **result_payload,
                "task_id": pending_task.task_id,
                "source_agent_id": getattr(envelope, "source_agent_id", None),
                "target_agent_id": getattr(envelope, "target_agent_id", None),
            },
        )
        self.runtime.mark_task_completed(
            task_id=pending_task.task_id,
            idempotency_key=getattr(envelope, "idempotency_key", f"phase3-uat:{result_payload['message_id']}"),
            message_id=result_payload["message_id"],
            workflow_id=pending_task.workflow_id,
            result_payload={
                **result_payload,
                "phase3_runtime_record_id": record.record_id,
                "side_effect_outbox_id": outbox.outbox_id,
            },
        )
        return Phase3UatExecutionResult(
            executed=True,
            status="artifact_generated",
            artifact_path=str(artifact_path),
            runtime_record_id=record.record_id,
            outbox_id=outbox.outbox_id,
        )

    def _mark_failed(
        self,
        pending_task: PendingTaskRecord,
        envelope: Any,
        error: str,
        details: dict,
    ) -> Phase3UatExecutionResult:
        message_id = getattr(envelope, "message_id", pending_task.task_id.removeprefix("task-"))
        self.runtime.state_store.update_pending_task(
            task_id=pending_task.task_id,
            state="FAILED",
            updated_by=self.runtime.runtime_id,
            error_payload={"error": error, **details},
            completed_at=datetime.now(UTC).isoformat(),
        )
        record = self.runtime.state_store.create_phase3_runtime_record(
            record_type="phase3_uat_command_execution_record",
            workflow_instance_id=pending_task.workflow_id,
            related_message_id=message_id,
            dedupe_key=f"phase3_uat_command_execution:{message_id}",
            status="failed",
            payload={"task_id": pending_task.task_id, "error": error, **details},
        )
        return Phase3UatExecutionResult(executed=True, status="failed", runtime_record_id=record.record_id, error=error)

    def _payload_from_pending_task(self, pending_task: PendingTaskRecord) -> dict:
        payload = pending_task.input_payload if isinstance(pending_task.input_payload, dict) else {}
        if payload.get("payload") and isinstance(payload["payload"], dict):
            return dict(payload["payload"])
        return dict(payload)

    def _is_supported_hello_world_command(self, payload: dict) -> bool:
        command = str(payload.get("command") or payload.get("task") or payload.get("action") or "").strip().lower()
        if command in self.COMMAND_NAMES:
            return True
        command_text = str(payload.get("command_text") or payload.get("instruction") or "").lower()
        return "hello world" in command_text and "html" in command_text

    def _resolve_artifact_path(self, payload: dict) -> Optional[Path]:
        for key in self.PATH_KEYS:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return self._normalize_path(value.strip())
        artifact = payload.get("artifact")
        if isinstance(artifact, dict):
            for key in self.PATH_KEYS + ("path",):
                value = artifact.get(key)
                if isinstance(value, str) and value.strip():
                    return self._normalize_path(value.strip())
        return None

    @staticmethod
    def _normalize_path(raw_path: str) -> Path:
        if raw_path.startswith("\\\\") and "\\Nova-Jarvis-Shared\\" in raw_path:
            suffix = raw_path.split("\\Nova-Jarvis-Shared\\", 1)[1].replace("\\", "/")
            return Path("/mnt/d/Nova-Jarvis-Shared") / suffix
        return Path(raw_path)

    @staticmethod
    def _html_document(payload: dict, envelope: Any) -> str:
        title = str(payload.get("title") or "Hello, World!")
        body = str(payload.get("body") or payload.get("text") or "Hello, World!")
        message_id = getattr(envelope, "message_id", "")
        correlation_id = getattr(envelope, "correlation_id", "")
        generated_at = datetime.now(UTC).isoformat()
        return (
            "<!doctype html>\n"
            "<html lang=\"en\">\n"
            "<head>\n"
            "  <meta charset=\"utf-8\">\n"
            "  <title>Hello, World!</title>\n"
            "  <style>body{font-family:Georgia,serif;margin:4rem;background:#f7efe3;color:#1d2528}"
            "main{max-width:720px}h1{font-size:3rem;margin-bottom:.5rem}</style>\n"
            "</head>\n"
            "<body>\n"
            "  <main>\n"
            f"    <h1>{title}</h1>\n"
            f"    <p>{body}</p>\n"
            f"    <small>message_id={message_id} correlation_id={correlation_id} generated_at={generated_at}</small>\n"
            "  </main>\n"
            "</body>\n"
            "</html>\n"
        )
