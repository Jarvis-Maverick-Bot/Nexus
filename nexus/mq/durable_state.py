"""
SQLite-backed durable local state for always-on coordination runtime work.

This module is the Phase 3 skeleton foundation for:
- pending inbox work
- callback waits
- side-effect outbox
- envelope intake log
- durable idempotency
- runtime quarantine / restart state

It is intentionally SQLite-first for skeleton implementation readiness.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Any
import json
import sqlite3
import uuid
import base64


UTC = timezone.utc


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_loads(value: Optional[str], default: Any) -> Any:
    if value in (None, ""):
        return default
    return json.loads(value)


def _serialize_raw_inbound(value: Any) -> str:
    if isinstance(value, bytes):
        return _json_dumps(
            {
                "__type__": "bytes",
                "encoding": "base64",
                "data": base64.b64encode(value).decode("ascii"),
            }
        )
    if isinstance(value, str):
        return _json_dumps({"__type__": "string", "data": value})
    return _json_dumps({"__type__": "json", "data": value})


def _deserialize_raw_inbound(value: Optional[str]) -> Any:
    if value in (None, ""):
        return None
    loaded = _json_loads(value, {})
    if not isinstance(loaded, dict):
        return loaded
    raw_type = loaded.get("__type__")
    if raw_type == "bytes":
        return base64.b64decode(loaded.get("data", ""))
    if raw_type in {"string", "json"}:
        return loaded.get("data")
    return loaded


@dataclass
class PendingTaskRecord:
    task_id: str
    task_type: str
    subject: str
    correlation_id: str
    workflow_id: str
    state: str
    input_payload: dict
    reply_to_subject: Optional[str] = None
    priority: int = 0
    skill_name: Optional[str] = None
    result_payload: Optional[dict] = None
    error_payload: Optional[dict] = None
    first_response_deadline: Optional[str] = None
    completion_deadline: Optional[str] = None
    received_at: str = now_iso()
    last_progress_at: str = now_iso()
    completed_at: Optional[str] = None
    created_by: str = ""
    updated_by: str = ""

    @property
    def payload(self) -> dict:
        return self.input_payload


@dataclass
class CallbackWaitRecord:
    callback_id: str
    correlation_id: str
    expected_subject: str
    expected_source_agent_id: str
    request_message_id: str
    task_id: str
    state: str
    callback_type: str
    request_payload: dict
    response_payload: Optional[dict] = None
    reply_subject: Optional[str] = None
    deadline: Optional[str] = None
    first_response_deadline: Optional[str] = None
    completion_deadline: Optional[str] = None
    received_at: str = now_iso()
    last_progress_at: str = now_iso()
    completed_at: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    error_summary: Optional[str] = None
    created_by: str = ""


@dataclass
class SideEffectOutboxRecord:
    outbox_id: str
    side_effect_type: str
    target: str
    correlation_id: str
    payload_summary: str
    payload: dict
    state: str = "PLANNED"
    message_id: Optional[str] = None
    causation_id: Optional[str] = None
    planned_at: str = now_iso()
    published_at: Optional[str] = None
    confirmed_at: Optional[str] = None
    confirmed_by: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    next_retry_at: Optional[str] = None
    error_summary: Optional[str] = None
    checksum: Optional[str] = None
    created_by: str = ""


@dataclass
class EnvelopeInboxRecord:
    record_id: str
    envelope_id: str
    subject: str
    state: str
    raw_inbound_envelope: Any
    normalized_execution_envelope: Optional[dict] = None
    validation_errors: list[str] = None
    failure_class: Optional[str] = None
    failure_subclass: Optional[str] = None
    broker_action: Optional[str] = None
    terminal_outcome: Optional[str] = None
    anomaly_id: Optional[str] = None
    abnormal_state_id: Optional[str] = None
    handler_exhausted: bool = False
    governed_state_store_ref: Optional[str] = None
    workflow_instance_id: Optional[str] = None
    message_id: Optional[str] = None
    causation_id: Optional[str] = None
    correlation_id: Optional[str] = None
    source_agent_id: Optional[str] = None
    target_agent_id: Optional[str] = None
    local_retry_count: int = 0
    max_local_retries: int = 3
    created_at: str = now_iso()
    completed_at: Optional[str] = None
    error: Optional[str] = None

    @property
    def payload(self) -> dict:
        if isinstance(self.normalized_execution_envelope, dict):
            return self.normalized_execution_envelope
        if isinstance(self.raw_inbound_envelope, dict):
            return self.raw_inbound_envelope
        return {}

    @property
    def received_at(self) -> str:
        return self.created_at


@dataclass
class DurableIdempotencyRecord:
    idempotency_key: str
    message_id: str
    workflow_id: str
    state: str
    result_detail: Optional[Any] = None
    recorded_at: str = now_iso()


@dataclass
class RuntimeStatusRecord:
    runtime_id: str
    agent_id: str
    status: str
    reason: Optional[str] = None
    quarantined_path: Optional[str] = None
    updated_at: str = now_iso()


@dataclass
class AuthorityWaitStateRecord:
    authority_wait_id: str
    workflow_instance_id: str
    checkpoint_id: str
    gate_id: str
    requested_actor_role: str
    status: str
    review_task_message_id: Optional[str] = None
    evidence_package_id: Optional[str] = None
    due_at: Optional[str] = None
    responded_at: Optional[str] = None
    resolved_at: Optional[str] = None
    hitl_decision_id: Optional[str] = None
    created_at: str = now_iso()
    payload: dict = None


@dataclass
class HitlDecisionStoreRecord:
    decision_id: str
    authority_wait_id: str
    workflow_instance_id: str
    checkpoint_id: str
    linked_gate_id: str
    decision_type: str
    decision_value: str
    responding_actor_id: str
    responding_actor_role: str
    state_transition_allowed: bool
    validation_status: str
    created_at: str
    payload: dict


@dataclass
class Phase3RuntimeRecord:
    record_id: str
    record_type: str
    workflow_instance_id: Optional[str]
    authority_wait_id: Optional[str]
    related_message_id: Optional[str]
    dedupe_key: Optional[str]
    status: str
    created_at: str
    payload: dict


@dataclass
class Phase5DurableRecord:
    record_id: str
    family: str
    workflow_instance_id: Optional[str]
    target_ref: Optional[str]
    authority_wait_id: Optional[str]
    related_record_id: Optional[str]
    dedupe_key: Optional[str]
    status: str
    created_at: str
    payload: dict


@dataclass
class CurrentProjectionRecord:
    workflow_instance_id: str
    projection_status: str
    source_record_id: Optional[str]
    source_family: Optional[str]
    version: int
    rebuilt_at: str
    payload: dict


@dataclass
class AbnormalStateStoreRecord:
    abnormal_state_id: str
    error_event_id: str
    workflow_instance_id: Optional[str]
    error_class: str
    abnormal_class: str
    resolved: bool
    notification_sent: bool
    resolution_record_id: Optional[str]
    escalation_timer_id: Optional[str]
    detected_at: str
    resolved_at: Optional[str]
    payload: dict


@dataclass
class ResolutionStoreRecord:
    resolution_id: str
    abnormal_state_id: str
    error_event_id: str
    workflow_instance_id: str
    resolved_by: str
    resolution_action: str
    created_at: str
    payload: dict


@dataclass
class EscalationTimerStoreRecord:
    escalation_timer_id: str
    workflow_instance_id: str
    trigger_type: str
    due_at: str
    status: str
    created_at: str
    payload: dict


class DurableStateStore:
    """
    SQLite durable local state for coordination runtime semantics.

    Design posture:
    - one store per runtime context
    - fail-closed integrity checks available before startup
    - JSON payloads stored durably for replay/recovery
    """

    def __init__(self, db_path: str | Path):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._initialize_schema()

    def close(self) -> None:
        self._conn.close()

    def verify_integrity(self) -> tuple[bool, list[str]]:
        rows = self._conn.execute("PRAGMA integrity_check").fetchall()
        results = [row[0] for row in rows]
        if results == ["ok"]:
            return True, []
        return False, results

    def quarantine_runtime(self, runtime_id: str, agent_id: str, reason: str) -> RuntimeStatusRecord:
        record = RuntimeStatusRecord(
            runtime_id=runtime_id,
            agent_id=agent_id,
            status="QUARANTINED",
            reason=reason,
            quarantined_path=str(self._db_path),
            updated_at=now_iso(),
        )
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO runtime_status(runtime_id, agent_id, status, reason, quarantined_path, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(runtime_id) DO UPDATE SET
                    agent_id=excluded.agent_id,
                    status=excluded.status,
                    reason=excluded.reason,
                    quarantined_path=excluded.quarantined_path,
                    updated_at=excluded.updated_at
                """,
                (
                    record.runtime_id,
                    record.agent_id,
                    record.status,
                    record.reason,
                    record.quarantined_path,
                    record.updated_at,
                ),
            )
        return record

    def set_runtime_status(self, runtime_id: str, agent_id: str, status: str, reason: Optional[str] = None) -> RuntimeStatusRecord:
        record = RuntimeStatusRecord(
            runtime_id=runtime_id,
            agent_id=agent_id,
            status=status,
            reason=reason,
            updated_at=now_iso(),
        )
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO runtime_status(runtime_id, agent_id, status, reason, quarantined_path, updated_at)
                VALUES (?, ?, ?, ?, COALESCE((SELECT quarantined_path FROM runtime_status WHERE runtime_id = ?), NULL), ?)
                ON CONFLICT(runtime_id) DO UPDATE SET
                    agent_id=excluded.agent_id,
                    status=excluded.status,
                    reason=excluded.reason,
                    updated_at=excluded.updated_at
                """,
                (
                    record.runtime_id,
                    record.agent_id,
                    record.status,
                    record.reason,
                    record.runtime_id,
                    record.updated_at,
                ),
            )
        return record

    def get_runtime_status(self, runtime_id: str) -> Optional[RuntimeStatusRecord]:
        row = self._conn.execute(
            "SELECT runtime_id, agent_id, status, reason, quarantined_path, updated_at FROM runtime_status WHERE runtime_id = ?",
            (runtime_id,),
        ).fetchone()
        if row is None:
            return None
        return RuntimeStatusRecord(
            runtime_id=row["runtime_id"],
            agent_id=row["agent_id"],
            status=row["status"],
            reason=row["reason"],
            quarantined_path=row["quarantined_path"],
            updated_at=row["updated_at"],
        )

    def create_pending_task(
        self,
        created_by: str,
        input_payload: Optional[dict] = None,
        task_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        task_type: str = "command",
        subject: str = "",
        correlation_id: str = "",
        payload: Optional[dict] = None,
        reply_to_subject: Optional[str] = None,
        deadline_at: Optional[str] = None,
        skill_name: Optional[str] = None,
        priority: int = 0,
        first_response_deadline: Optional[str] = None,
        completion_deadline: Optional[str] = None,
    ) -> PendingTaskRecord:
        payload = payload if payload is not None else input_payload
        if payload is None:
            raise ValueError("pending task payload is required")
        task_id = task_id or f"task-{uuid.uuid4().hex[:12]}"
        workflow_id = workflow_id or correlation_id or task_id
        if first_response_deadline is None:
            first_response_deadline = deadline_at
        if completion_deadline is None:
            completion_deadline = deadline_at
        existing = self.get_pending_task(task_id)
        if existing is not None:
            return existing
        record = PendingTaskRecord(
            task_id=task_id,
            task_type=task_type,
            subject=subject,
            correlation_id=correlation_id,
            workflow_id=workflow_id,
            state="PENDING",
            input_payload=payload,
            reply_to_subject=reply_to_subject,
            priority=priority,
            skill_name=skill_name,
            first_response_deadline=first_response_deadline,
            completion_deadline=completion_deadline,
            received_at=now_iso(),
            last_progress_at=now_iso(),
            created_by=created_by,
            updated_by=created_by,
        )
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO pending_task(
                    task_id, task_type, subject, correlation_id, workflow_id, skill_name, state,
                    input_payload, result_payload, error_payload, reply_to_subject, priority, received_at,
                    first_response_deadline, completion_deadline, last_progress_at, completed_at,
                    created_by, updated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    record.task_id,
                    record.task_type,
                    record.subject,
                    record.correlation_id,
                    record.workflow_id,
                    record.skill_name,
                    record.state,
                    _json_dumps(record.input_payload),
                    record.reply_to_subject,
                    record.priority,
                    record.received_at,
                    record.first_response_deadline,
                    record.completion_deadline,
                    record.last_progress_at,
                    record.created_by,
                    record.updated_by,
                ),
            )
        return record

    def update_pending_task(
        self,
        task_id: str,
        state: str,
        updated_by: str,
        result_payload: Optional[dict] = None,
        error_payload: Optional[dict] = None,
        completed_at: Optional[str] = None,
    ) -> PendingTaskRecord:
        last_progress_at = now_iso()
        with self._conn:
            self._conn.execute(
                """
                UPDATE pending_task
                SET state = ?,
                    result_payload = COALESCE(?, result_payload),
                    error_payload = COALESCE(?, error_payload),
                    last_progress_at = ?,
                    completed_at = COALESCE(?, completed_at),
                    updated_by = ?
                WHERE task_id = ?
                """,
                (
                    state,
                    _json_dumps(result_payload) if result_payload is not None else None,
                    _json_dumps(error_payload) if error_payload is not None else None,
                    last_progress_at,
                    completed_at,
                    updated_by,
                    task_id,
                ),
            )
        record = self.get_pending_task(task_id)
        if record is None:
            raise KeyError(f"pending_task not found: {task_id}")
        return record

    def get_pending_task(self, task_id: str) -> Optional[PendingTaskRecord]:
        row = self._conn.execute(
            """
            SELECT task_id, task_type, subject, correlation_id, workflow_id, skill_name, state,
                   input_payload, result_payload, error_payload, reply_to_subject, priority, received_at,
                   first_response_deadline, completion_deadline, last_progress_at, completed_at,
                   created_by, updated_by
            FROM pending_task
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()
        if row is None:
            return None
        return PendingTaskRecord(
            task_id=row["task_id"],
            task_type=row["task_type"],
            subject=row["subject"],
            correlation_id=row["correlation_id"],
            workflow_id=row["workflow_id"],
            skill_name=row["skill_name"],
            state=row["state"],
            input_payload=_json_loads(row["input_payload"], {}),
            result_payload=_json_loads(row["result_payload"], None),
            error_payload=_json_loads(row["error_payload"], None),
            reply_to_subject=row["reply_to_subject"],
            priority=row["priority"],
            received_at=row["received_at"],
            first_response_deadline=row["first_response_deadline"],
            completion_deadline=row["completion_deadline"],
            last_progress_at=row["last_progress_at"],
            completed_at=row["completed_at"],
            created_by=row["created_by"],
            updated_by=row["updated_by"],
        )

    def list_pending_tasks(self, states: Optional[list[str]] = None) -> list[PendingTaskRecord]:
        if states:
            placeholders = ", ".join("?" for _ in states)
            query = f"""
                SELECT task_id, workflow_id, skill_name, state, input_payload, result_payload, error_payload,
                       priority, received_at, first_response_deadline, completion_deadline, last_progress_at,
                       completed_at, created_by, updated_by, task_type, subject, correlation_id, reply_to_subject
                FROM pending_task
                WHERE state IN ({placeholders})
                ORDER BY priority DESC, received_at ASC
            """
            rows = self._conn.execute(query, tuple(states)).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT task_id, workflow_id, skill_name, state, input_payload, result_payload, error_payload,
                       priority, received_at, first_response_deadline, completion_deadline, last_progress_at,
                       completed_at, created_by, updated_by, task_type, subject, correlation_id, reply_to_subject
                FROM pending_task
                ORDER BY priority DESC, received_at ASC
                """
            ).fetchall()
        return [
            PendingTaskRecord(
                task_id=row["task_id"],
                task_type=row["task_type"],
                subject=row["subject"],
                correlation_id=row["correlation_id"],
                workflow_id=row["workflow_id"],
                skill_name=row["skill_name"],
                state=row["state"],
                input_payload=_json_loads(row["input_payload"], {}),
                result_payload=_json_loads(row["result_payload"], None),
                error_payload=_json_loads(row["error_payload"], None),
                reply_to_subject=row["reply_to_subject"],
                priority=row["priority"],
                received_at=row["received_at"],
                first_response_deadline=row["first_response_deadline"],
                completion_deadline=row["completion_deadline"],
                last_progress_at=row["last_progress_at"],
                completed_at=row["completed_at"],
                created_by=row["created_by"],
                updated_by=row["updated_by"],
            )
            for row in rows
        ]

    def list_overdue_pending_tasks(self, now_at: Optional[str] = None) -> list[PendingTaskRecord]:
        now_at = now_at or now_iso()
        rows = self._conn.execute(
            """
            SELECT task_id, workflow_id, skill_name, state, input_payload, result_payload, error_payload,
                   priority, received_at, first_response_deadline, completion_deadline, last_progress_at,
                   completed_at, created_by, updated_by, task_type, subject, correlation_id, reply_to_subject
            FROM pending_task
            WHERE state IN ('PENDING', 'PROCESSING')
              AND (
                    (first_response_deadline IS NOT NULL AND first_response_deadline < ?)
                 OR (completion_deadline IS NOT NULL AND completion_deadline < ?)
              )
            ORDER BY received_at ASC
            """,
            (now_at, now_at),
        ).fetchall()
        return [
            PendingTaskRecord(
                task_id=row["task_id"],
                task_type=row["task_type"],
                subject=row["subject"],
                correlation_id=row["correlation_id"],
                workflow_id=row["workflow_id"],
                skill_name=row["skill_name"],
                state=row["state"],
                input_payload=_json_loads(row["input_payload"], {}),
                result_payload=_json_loads(row["result_payload"], None),
                error_payload=_json_loads(row["error_payload"], None),
                reply_to_subject=row["reply_to_subject"],
                priority=row["priority"],
                received_at=row["received_at"],
                first_response_deadline=row["first_response_deadline"],
                completion_deadline=row["completion_deadline"],
                last_progress_at=row["last_progress_at"],
                completed_at=row["completed_at"],
                created_by=row["created_by"],
                updated_by=row["updated_by"],
            )
            for row in rows
        ]

    def create_callback_wait(
        self,
        request_payload: Optional[dict] = None,
        callback_id: Optional[str] = None,
        correlation_id: str = "",
        expected_subject: str = "",
        expected_source_agent_id: str = "",
        request_message_id: str = "",
        task_id: Optional[str] = None,
        callback_type: str = "callback",
        payload: Optional[dict] = None,
        reply_subject: Optional[str] = None,
        deadline: Optional[str] = None,
        deadline_at: Optional[str] = None,
        created_by: str = "",
        first_response_deadline: Optional[str] = None,
        completion_deadline: Optional[str] = None,
        max_retries: int = 3,
    ) -> CallbackWaitRecord:
        payload = payload if payload is not None else request_payload
        if payload is None:
            payload = {}
        deadline = deadline if deadline is not None else deadline_at
        callback_id = callback_id or f"callback-{uuid.uuid4().hex[:12]}"
        task_id = task_id or request_message_id or correlation_id or callback_id
        if first_response_deadline is None:
            first_response_deadline = deadline
        if completion_deadline is None:
            completion_deadline = deadline
        record = CallbackWaitRecord(
            callback_id=callback_id,
            correlation_id=correlation_id,
            expected_subject=expected_subject,
            expected_source_agent_id=expected_source_agent_id,
            request_message_id=request_message_id,
            task_id=task_id,
            state="WAITING",
            callback_type=callback_type,
            request_payload=payload,
            reply_subject=reply_subject,
            deadline=deadline,
            first_response_deadline=first_response_deadline,
            completion_deadline=completion_deadline,
            received_at=now_iso(),
            last_progress_at=now_iso(),
            max_retries=max_retries,
            created_by=created_by,
        )
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO callback_wait(
                    callback_id, correlation_id, expected_subject, expected_source_agent_id, request_message_id,
                    task_id, state, callback_type, request_payload, response_payload, reply_subject, deadline,
                    first_response_deadline, completion_deadline, last_progress_at, received_at, completed_at,
                    retry_count, max_retries, error_summary, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, NULL, 0, ?, NULL, ?)
                """,
                (
                    record.callback_id,
                    record.correlation_id,
                    record.expected_subject,
                    record.expected_source_agent_id,
                    record.request_message_id,
                    record.task_id,
                    record.state,
                    record.callback_type,
                    _json_dumps(record.request_payload),
                    record.reply_subject,
                    record.deadline,
                    record.first_response_deadline,
                    record.completion_deadline,
                    record.last_progress_at,
                    record.received_at,
                    record.max_retries,
                    record.created_by,
                ),
            )
        return record

    def complete_callback_wait(
        self,
        callback_id: str,
        response_payload: dict,
        state: str = "RECEIVED",
    ) -> CallbackWaitRecord:
        with self._conn:
            self._conn.execute(
                """
                UPDATE callback_wait
                SET state = ?,
                    response_payload = ?,
                    last_progress_at = ?,
                    completed_at = ?
                WHERE callback_id = ?
                """,
                (state, _json_dumps(response_payload), now_iso(), now_iso(), callback_id),
            )
        record = self.get_callback_wait(callback_id)
        if record is None:
            raise KeyError(f"callback_wait not found: {callback_id}")
        return record

    def expire_callback_wait(self, callback_id: str, error_summary: str) -> CallbackWaitRecord:
        with self._conn:
            self._conn.execute(
                """
                UPDATE callback_wait
                SET state = 'EXPIRED',
                    error_summary = ?,
                    last_progress_at = ?,
                    completed_at = ?
                WHERE callback_id = ?
                """,
                (error_summary, now_iso(), now_iso(), callback_id),
            )
        record = self.get_callback_wait(callback_id)
        if record is None:
            raise KeyError(f"callback_wait not found: {callback_id}")
        return record

    def get_callback_wait(self, callback_id: str) -> Optional[CallbackWaitRecord]:
        row = self._conn.execute(
            """
            SELECT callback_id, correlation_id, expected_subject, expected_source_agent_id, request_message_id,
                   task_id, state, callback_type, request_payload, response_payload, reply_subject, deadline,
                   first_response_deadline, completion_deadline, last_progress_at, received_at, completed_at,
                   retry_count, max_retries, error_summary, created_by
            FROM callback_wait
            WHERE callback_id = ?
            """,
            (callback_id,),
        ).fetchone()
        if row is None:
            return None
        return CallbackWaitRecord(
            callback_id=row["callback_id"],
            correlation_id=row["correlation_id"],
            expected_subject=row["expected_subject"],
            expected_source_agent_id=row["expected_source_agent_id"],
            request_message_id=row["request_message_id"],
            task_id=row["task_id"],
            state=row["state"],
            callback_type=row["callback_type"],
            request_payload=_json_loads(row["request_payload"], {}),
            response_payload=_json_loads(row["response_payload"], None),
            reply_subject=row["reply_subject"],
            deadline=row["deadline"],
            first_response_deadline=row["first_response_deadline"],
            completion_deadline=row["completion_deadline"],
            last_progress_at=row["last_progress_at"],
            received_at=row["received_at"],
            completed_at=row["completed_at"],
            retry_count=row["retry_count"],
            max_retries=row["max_retries"],
            error_summary=row["error_summary"],
            created_by=row["created_by"],
        )

    def list_waiting_callbacks(self) -> list[CallbackWaitRecord]:
        rows = self._conn.execute(
            """
            SELECT callback_id, correlation_id, expected_subject, expected_source_agent_id, request_message_id,
                   task_id, state, callback_type, request_payload, response_payload, reply_subject, deadline,
                   first_response_deadline, completion_deadline, last_progress_at, received_at, completed_at,
                   retry_count, max_retries, error_summary, created_by
            FROM callback_wait
            WHERE state IN ('WAITING', 'RETRYING')
            ORDER BY received_at ASC
            """
        ).fetchall()
        return [
            CallbackWaitRecord(
                callback_id=row["callback_id"],
                correlation_id=row["correlation_id"],
                expected_subject=row["expected_subject"],
                expected_source_agent_id=row["expected_source_agent_id"],
                request_message_id=row["request_message_id"],
                task_id=row["task_id"],
                state=row["state"],
                callback_type=row["callback_type"],
                request_payload=_json_loads(row["request_payload"], {}),
                response_payload=_json_loads(row["response_payload"], None),
                reply_subject=row["reply_subject"],
                deadline=row["deadline"],
                first_response_deadline=row["first_response_deadline"],
                completion_deadline=row["completion_deadline"],
                last_progress_at=row["last_progress_at"],
                received_at=row["received_at"],
                completed_at=row["completed_at"],
                retry_count=row["retry_count"],
                max_retries=row["max_retries"],
                error_summary=row["error_summary"],
                created_by=row["created_by"],
            )
            for row in rows
        ]

    def create_outbox_record(
        self,
        side_effect_type: str,
        target: str,
        correlation_id: str,
        payload: dict,
        created_by: str,
        message_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        max_retries: int = 3,
    ) -> SideEffectOutboxRecord:
        outbox_id = f"outbox-{uuid.uuid4().hex[:12]}"
        record = SideEffectOutboxRecord(
            outbox_id=outbox_id,
            side_effect_type=side_effect_type,
            target=target,
            correlation_id=correlation_id,
            payload_summary=_json_dumps(payload)[:256],
            payload=payload,
            message_id=message_id,
            causation_id=causation_id,
            max_retries=max_retries,
            created_by=created_by,
            planned_at=now_iso(),
        )
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO side_effect_outbox(
                    outbox_id, message_id, correlation_id, causation_id, side_effect_type, target,
                    payload_summary, payload, state, planned_at, published_at, confirmed_at, confirmed_by,
                    retry_count, max_retries, next_retry_at, error_summary, checksum, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, 0, ?, NULL, NULL, NULL, ?)
                """,
                (
                    record.outbox_id,
                    record.message_id,
                    record.correlation_id,
                    record.causation_id,
                    record.side_effect_type,
                    record.target,
                    record.payload_summary,
                    _json_dumps(record.payload),
                    record.state,
                    record.planned_at,
                    record.max_retries,
                    record.created_by,
                ),
            )
        return record

    def mark_outbox_published(self, outbox_id: str) -> SideEffectOutboxRecord:
        with self._conn:
            self._conn.execute(
                """
                UPDATE side_effect_outbox
                SET state = 'PUBLISHED',
                    published_at = ?,
                    error_summary = NULL
                WHERE outbox_id = ?
                """,
                (now_iso(), outbox_id),
            )
        record = self.get_outbox_record(outbox_id)
        if record is None:
            raise KeyError(f"side_effect_outbox not found: {outbox_id}")
        return record

    def mark_outbox_publish_in_flight(self, outbox_id: str, attempt_id: str) -> SideEffectOutboxRecord:
        with self._conn:
            self._conn.execute(
                """
                UPDATE side_effect_outbox
                SET state = 'PUBLISHED',
                    published_at = ?,
                    error_summary = ?,
                    retry_count = retry_count + 1
                WHERE outbox_id = ? AND state = 'PLANNED'
                """,
                (now_iso(), f"publish_in_flight:{attempt_id}", outbox_id),
            )
        record = self.get_outbox_record(outbox_id)
        if record is None:
            raise KeyError(f"side_effect_outbox not found: {outbox_id}")
        return record

    def mark_outbox_confirmed(self, outbox_id: str, confirmed_by: str) -> SideEffectOutboxRecord:
        with self._conn:
            self._conn.execute(
                """
                UPDATE side_effect_outbox
                SET state = 'CONFIRMED',
                    confirmed_at = ?,
                    confirmed_by = ?,
                    error_summary = NULL
                WHERE outbox_id = ?
                """,
                (now_iso(), confirmed_by, outbox_id),
            )
        record = self.get_outbox_record(outbox_id)
        if record is None:
            raise KeyError(f"side_effect_outbox not found: {outbox_id}")
        return record

    def mark_outbox_failed(self, outbox_id: str, error_summary: str) -> SideEffectOutboxRecord:
        with self._conn:
            self._conn.execute(
                """
                UPDATE side_effect_outbox
                SET state = 'FAILED',
                    error_summary = ?,
                    confirmed_at = ?
                WHERE outbox_id = ?
                """,
                (error_summary, now_iso(), outbox_id),
            )
        record = self.get_outbox_record(outbox_id)
        if record is None:
            raise KeyError(f"side_effect_outbox not found: {outbox_id}")
        return record

    def get_outbox_record(self, outbox_id: str) -> Optional[SideEffectOutboxRecord]:
        row = self._conn.execute(
            """
            SELECT outbox_id, message_id, correlation_id, causation_id, side_effect_type, target,
                   payload_summary, payload, state, planned_at, published_at, confirmed_at, confirmed_by,
                   retry_count, max_retries, next_retry_at, error_summary, checksum, created_by
            FROM side_effect_outbox
            WHERE outbox_id = ?
            """,
            (outbox_id,),
        ).fetchone()
        if row is None:
            return None
        return SideEffectOutboxRecord(
            outbox_id=row["outbox_id"],
            message_id=row["message_id"],
            correlation_id=row["correlation_id"],
            causation_id=row["causation_id"],
            side_effect_type=row["side_effect_type"],
            target=row["target"],
            payload_summary=row["payload_summary"],
            payload=_json_loads(row["payload"], {}),
            state=row["state"],
            planned_at=row["planned_at"],
            published_at=row["published_at"],
            confirmed_at=row["confirmed_at"],
            confirmed_by=row["confirmed_by"],
            retry_count=row["retry_count"],
            max_retries=row["max_retries"],
            next_retry_at=row["next_retry_at"],
            error_summary=row["error_summary"],
            checksum=row["checksum"],
            created_by=row["created_by"],
        )

    def list_outbox_requiring_reconciliation(self) -> list[SideEffectOutboxRecord]:
        rows = self._conn.execute(
            """
            SELECT outbox_id, message_id, correlation_id, causation_id, side_effect_type, target,
                   payload_summary, payload, state, planned_at, published_at, confirmed_at, confirmed_by,
                   retry_count, max_retries, next_retry_at, error_summary, checksum, created_by
            FROM side_effect_outbox
            WHERE state IN ('PLANNED', 'PUBLISHED')
            ORDER BY planned_at ASC
            """
        ).fetchall()
        return [
            SideEffectOutboxRecord(
                outbox_id=row["outbox_id"],
                message_id=row["message_id"],
                correlation_id=row["correlation_id"],
                causation_id=row["causation_id"],
                side_effect_type=row["side_effect_type"],
                target=row["target"],
                payload_summary=row["payload_summary"],
                payload=_json_loads(row["payload"], {}),
                state=row["state"],
                planned_at=row["planned_at"],
                published_at=row["published_at"],
                confirmed_at=row["confirmed_at"],
                confirmed_by=row["confirmed_by"],
                retry_count=row["retry_count"],
                max_retries=row["max_retries"],
                next_retry_at=row["next_retry_at"],
                error_summary=row["error_summary"],
                checksum=row["checksum"],
                created_by=row["created_by"],
            )
            for row in rows
        ]

    def record_envelope_inbox(
        self,
        envelope_id: str,
        subject: str,
        payload: Any,
        *,
        record_id: Optional[str] = None,
        normalized_execution_envelope: Optional[dict] = None,
        validation_errors: Optional[list[str]] = None,
        failure_class: Optional[str] = None,
        failure_subclass: Optional[str] = None,
        broker_action: Optional[str] = None,
        terminal_outcome: Optional[str] = None,
        anomaly_id: Optional[str] = None,
        abnormal_state_id: Optional[str] = None,
        handler_exhausted: bool = False,
        governed_state_store_ref: Optional[str] = None,
        workflow_instance_id: Optional[str] = None,
        message_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        source_agent_id: Optional[str] = None,
        target_agent_id: Optional[str] = None,
        local_retry_count: int = 0,
        max_local_retries: int = 3,
        state: str = "processing",
        error: Optional[str] = None,
    ) -> EnvelopeInboxRecord:
        existing = self.get_envelope_inbox(envelope_id)
        if existing is not None:
            return existing
        record = EnvelopeInboxRecord(
            record_id=record_id or f"intake-{uuid.uuid4().hex[:12]}",
            envelope_id=envelope_id,
            subject=subject,
            state=state,
            raw_inbound_envelope=payload,
            normalized_execution_envelope=normalized_execution_envelope,
            validation_errors=list(validation_errors or []),
            failure_class=failure_class,
            failure_subclass=failure_subclass,
            broker_action=broker_action,
            terminal_outcome=terminal_outcome,
            anomaly_id=anomaly_id,
            abnormal_state_id=abnormal_state_id,
            handler_exhausted=handler_exhausted,
            governed_state_store_ref=governed_state_store_ref or f"{self._db_path}#envelope_inbox/{envelope_id}",
            workflow_instance_id=workflow_instance_id,
            message_id=message_id,
            causation_id=causation_id,
            correlation_id=correlation_id,
            source_agent_id=source_agent_id,
            target_agent_id=target_agent_id,
            local_retry_count=local_retry_count,
            max_local_retries=max_local_retries,
            created_at=now_iso(),
            error=error,
        )
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO envelope_inbox(
                    record_id, envelope_id, subject, state, payload, raw_inbound_envelope,
                    normalized_execution_envelope, validation_errors, failure_class, failure_subclass,
                    broker_action, terminal_outcome, anomaly_id, abnormal_state_id, handler_exhausted,
                    governed_state_store_ref, workflow_instance_id, message_id, causation_id, correlation_id,
                    source_agent_id, target_agent_id, local_retry_count, max_local_retries,
                    received_at, completed_at, error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
                """,
                (
                    record.record_id,
                    record.envelope_id,
                    record.subject,
                    record.state,
                    _json_dumps(record.payload),
                    _serialize_raw_inbound(record.raw_inbound_envelope),
                    _json_dumps(record.normalized_execution_envelope) if record.normalized_execution_envelope is not None else None,
                    _json_dumps(record.validation_errors),
                    record.failure_class,
                    record.failure_subclass,
                    record.broker_action,
                    record.terminal_outcome,
                    record.anomaly_id,
                    record.abnormal_state_id,
                    1 if record.handler_exhausted else 0,
                    record.governed_state_store_ref,
                    record.workflow_instance_id,
                    record.message_id,
                    record.causation_id,
                    record.correlation_id,
                    record.source_agent_id,
                    record.target_agent_id,
                    record.local_retry_count,
                    record.max_local_retries,
                    record.created_at,
                    record.error,
                ),
            )
        return record

    def complete_envelope_inbox(self, envelope_id: str, state: str = "completed", error: Optional[str] = None) -> EnvelopeInboxRecord:
        with self._conn:
            self._conn.execute(
                """
                UPDATE envelope_inbox
                SET state = ?, completed_at = ?, error = ?
                WHERE envelope_id = ?
                """,
                (state, now_iso(), error, envelope_id),
            )
        record = self.get_envelope_inbox(envelope_id)
        if record is None:
            raise KeyError(f"envelope_inbox not found: {envelope_id}")
        return record

    def get_envelope_inbox(self, envelope_id: str) -> Optional[EnvelopeInboxRecord]:
        row = self._conn.execute(
            """
            SELECT record_id, envelope_id, subject, state, payload, raw_inbound_envelope,
                   normalized_execution_envelope, validation_errors, failure_class, failure_subclass,
                   broker_action, terminal_outcome, anomaly_id, abnormal_state_id, handler_exhausted,
                   governed_state_store_ref, workflow_instance_id, message_id, causation_id, correlation_id,
                   source_agent_id, target_agent_id, local_retry_count, max_local_retries,
                   received_at, completed_at, error
            FROM envelope_inbox
            WHERE envelope_id = ?
            """,
            (envelope_id,),
        ).fetchone()
        if row is None:
            return None
        return EnvelopeInboxRecord(
            record_id=row["record_id"],
            envelope_id=row["envelope_id"],
            subject=row["subject"],
            state=row["state"],
            raw_inbound_envelope=_deserialize_raw_inbound(row["raw_inbound_envelope"]),
            normalized_execution_envelope=_json_loads(row["normalized_execution_envelope"], None),
            validation_errors=_json_loads(row["validation_errors"], []),
            failure_class=row["failure_class"],
            failure_subclass=row["failure_subclass"],
            broker_action=row["broker_action"],
            terminal_outcome=row["terminal_outcome"],
            anomaly_id=row["anomaly_id"],
            abnormal_state_id=row["abnormal_state_id"],
            handler_exhausted=bool(row["handler_exhausted"]),
            governed_state_store_ref=row["governed_state_store_ref"],
            workflow_instance_id=row["workflow_instance_id"],
            message_id=row["message_id"],
            causation_id=row["causation_id"],
            correlation_id=row["correlation_id"],
            source_agent_id=row["source_agent_id"],
            target_agent_id=row["target_agent_id"],
            local_retry_count=row["local_retry_count"],
            max_local_retries=row["max_local_retries"],
            created_at=row["received_at"],
            completed_at=row["completed_at"],
            error=row["error"],
        )

    def list_envelope_inbox_for_local_recovery(self) -> list[EnvelopeInboxRecord]:
        rows = self._conn.execute(
            """
            SELECT record_id, envelope_id, subject, state, payload, raw_inbound_envelope,
                   normalized_execution_envelope, validation_errors, failure_class, failure_subclass,
                   broker_action, terminal_outcome, anomaly_id, abnormal_state_id, handler_exhausted,
                   governed_state_store_ref, workflow_instance_id, message_id, causation_id, correlation_id,
                   source_agent_id, target_agent_id, local_retry_count, max_local_retries,
                   received_at, completed_at, error
            FROM envelope_inbox
            WHERE state IN ('processing', 'failed', 'handler_running')
              AND handler_exhausted = 0
            ORDER BY received_at ASC
            """
        ).fetchall()
        return [
            EnvelopeInboxRecord(
                record_id=row["record_id"],
                envelope_id=row["envelope_id"],
                subject=row["subject"],
                state=row["state"],
                raw_inbound_envelope=_deserialize_raw_inbound(row["raw_inbound_envelope"]),
                normalized_execution_envelope=_json_loads(row["normalized_execution_envelope"], None),
                validation_errors=_json_loads(row["validation_errors"], []),
                failure_class=row["failure_class"],
                failure_subclass=row["failure_subclass"],
                broker_action=row["broker_action"],
                terminal_outcome=row["terminal_outcome"],
                anomaly_id=row["anomaly_id"],
                abnormal_state_id=row["abnormal_state_id"],
                handler_exhausted=bool(row["handler_exhausted"]),
                governed_state_store_ref=row["governed_state_store_ref"],
                workflow_instance_id=row["workflow_instance_id"],
                message_id=row["message_id"],
                causation_id=row["causation_id"],
                correlation_id=row["correlation_id"],
                source_agent_id=row["source_agent_id"],
                target_agent_id=row["target_agent_id"],
                local_retry_count=row["local_retry_count"],
                max_local_retries=row["max_local_retries"],
                created_at=row["received_at"],
                completed_at=row["completed_at"],
                error=row["error"],
            )
            for row in rows
        ]

    def mark_envelope_inbox_handler_running(self, envelope_id: str) -> EnvelopeInboxRecord:
        with self._conn:
            self._conn.execute(
                """
                UPDATE envelope_inbox
                SET state = 'handler_running', error = NULL
                WHERE envelope_id = ?
                """,
                (envelope_id,),
            )
        record = self.get_envelope_inbox(envelope_id)
        if record is None:
            raise KeyError(f"envelope_inbox not found: {envelope_id}")
        return record

    def mark_envelope_inbox_handler_failure(self, envelope_id: str, error: str) -> EnvelopeInboxRecord:
        current = self.get_envelope_inbox(envelope_id)
        if current is None:
            raise KeyError(f"envelope_inbox not found: {envelope_id}")
        next_retry_count = current.local_retry_count + 1
        exhausted = next_retry_count >= current.max_local_retries
        next_state = "handler_exhausted" if exhausted else "failed"
        next_broker_action = "QUARANTINE" if exhausted else "LOCAL_RECOVERY"
        next_terminal_outcome = "blocked" if exhausted else "retry"
        with self._conn:
            self._conn.execute(
                """
                UPDATE envelope_inbox
                SET state = ?, error = ?, local_retry_count = ?, handler_exhausted = ?,
                    broker_action = ?, terminal_outcome = ?, completed_at = ?
                WHERE envelope_id = ?
                """,
                (
                    next_state,
                    error,
                    next_retry_count,
                    1 if exhausted else 0,
                    next_broker_action,
                    next_terminal_outcome,
                    now_iso() if exhausted else None,
                    envelope_id,
                ),
            )
        record = self.get_envelope_inbox(envelope_id)
        if record is None:
            raise KeyError(f"envelope_inbox not found: {envelope_id}")
        return record

    def update_envelope_inbox_abnormal_state(self, envelope_id: str, abnormal_state_id: str) -> EnvelopeInboxRecord:
        with self._conn:
            self._conn.execute(
                """
                UPDATE envelope_inbox
                SET abnormal_state_id = ?
                WHERE envelope_id = ?
                """,
                (abnormal_state_id, envelope_id),
            )
        record = self.get_envelope_inbox(envelope_id)
        if record is None:
            raise KeyError(f"envelope_inbox not found: {envelope_id}")
        return record

    def mark_envelope_inbox_retry_exhausted(
        self,
        envelope_id: str,
        error: str,
        abnormal_state_id: Optional[str] = None,
    ) -> EnvelopeInboxRecord:
        with self._conn:
            self._conn.execute(
                """
                UPDATE envelope_inbox
                SET state = 'failed',
                    terminal_outcome = 'blocked',
                    error = ?,
                    abnormal_state_id = COALESCE(?, abnormal_state_id),
                    completed_at = ?
                WHERE envelope_id = ?
                """,
                (error, abnormal_state_id, now_iso(), envelope_id),
            )
        record = self.get_envelope_inbox(envelope_id)
        if record is None:
            raise KeyError(f"envelope_inbox not found: {envelope_id}")
        return record

    def record_idempotency(
        self,
        idempotency_key: str,
        message_id: str,
        workflow_id: str,
        state: str = "completed",
        result_detail: Optional[Any] = None,
    ) -> DurableIdempotencyRecord:
        record = DurableIdempotencyRecord(
            idempotency_key=idempotency_key,
            message_id=message_id,
            workflow_id=workflow_id,
            state=state,
            result_detail=result_detail,
            recorded_at=now_iso(),
        )
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO durable_idempotency(idempotency_key, message_id, workflow_id, state, result_detail, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(idempotency_key) DO UPDATE SET
                    message_id=excluded.message_id,
                    workflow_id=excluded.workflow_id,
                    state=excluded.state,
                    result_detail=excluded.result_detail,
                    recorded_at=excluded.recorded_at
                """,
                (
                    record.idempotency_key,
                    record.message_id,
                    record.workflow_id,
                    record.state,
                    _json_dumps(record.result_detail) if record.result_detail is not None else None,
                    record.recorded_at,
                ),
            )
        return record

    def get_idempotency(self, idempotency_key: str) -> Optional[DurableIdempotencyRecord]:
        row = self._conn.execute(
            """
            SELECT idempotency_key, message_id, workflow_id, state, result_detail, recorded_at
            FROM durable_idempotency
            WHERE idempotency_key = ?
            """,
            (idempotency_key,),
        ).fetchone()
        if row is None:
            return None
        return DurableIdempotencyRecord(
            idempotency_key=row["idempotency_key"],
            message_id=row["message_id"],
            workflow_id=row["workflow_id"],
            state=row["state"],
            result_detail=_json_loads(row["result_detail"], None),
            recorded_at=row["recorded_at"],
        )

    def create_authority_wait_state(
        self,
        authority_wait_id: str,
        workflow_instance_id: str,
        checkpoint_id: str,
        gate_id: str,
        requested_actor_role: str,
        status: str,
        payload: dict,
        review_task_message_id: Optional[str] = None,
        evidence_package_id: Optional[str] = None,
        due_at: Optional[str] = None,
        responded_at: Optional[str] = None,
        resolved_at: Optional[str] = None,
        hitl_decision_id: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> AuthorityWaitStateRecord:
        record = AuthorityWaitStateRecord(
            authority_wait_id=authority_wait_id,
            workflow_instance_id=workflow_instance_id,
            checkpoint_id=checkpoint_id,
            gate_id=gate_id,
            requested_actor_role=requested_actor_role,
            status=status,
            review_task_message_id=review_task_message_id,
            evidence_package_id=evidence_package_id,
            due_at=due_at,
            responded_at=responded_at,
            resolved_at=resolved_at,
            hitl_decision_id=hitl_decision_id,
            created_at=created_at or now_iso(),
            payload=payload,
        )
        try:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO authority_wait_state(
                        authority_wait_id, workflow_instance_id, checkpoint_id, gate_id, requested_actor_role,
                        status, review_task_message_id, evidence_package_id, due_at, responded_at, resolved_at,
                        hitl_decision_id, created_at, payload
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(authority_wait_id) DO UPDATE SET
                        workflow_instance_id=excluded.workflow_instance_id,
                        checkpoint_id=excluded.checkpoint_id,
                        gate_id=excluded.gate_id,
                        requested_actor_role=excluded.requested_actor_role,
                        status=excluded.status,
                        review_task_message_id=excluded.review_task_message_id,
                        evidence_package_id=excluded.evidence_package_id,
                        due_at=excluded.due_at,
                        responded_at=excluded.responded_at,
                        resolved_at=excluded.resolved_at,
                        hitl_decision_id=excluded.hitl_decision_id,
                        created_at=excluded.created_at,
                        payload=excluded.payload
                    """,
                    (
                        record.authority_wait_id,
                        record.workflow_instance_id,
                        record.checkpoint_id,
                        record.gate_id,
                        record.requested_actor_role,
                        record.status,
                        record.review_task_message_id,
                        record.evidence_package_id,
                        record.due_at,
                        record.responded_at,
                        record.resolved_at,
                        record.hitl_decision_id,
                        record.created_at,
                        _json_dumps(record.payload or {}),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            if "idx_authority_wait_active_unique" in str(exc) or "UNIQUE constraint failed" in str(exc):
                raise ValueError(
                    "ACTIVE_WAIT_UNIQUENESS_CONFLICT: one active wait already exists for "
                    f"{workflow_instance_id}/{checkpoint_id}/{gate_id}"
                ) from exc
            raise
        return record

    def get_authority_wait_state(self, authority_wait_id: str) -> Optional[AuthorityWaitStateRecord]:
        row = self._conn.execute(
            """
            SELECT authority_wait_id, workflow_instance_id, checkpoint_id, gate_id, requested_actor_role,
                   status, review_task_message_id, evidence_package_id, due_at, responded_at, resolved_at,
                   hitl_decision_id, created_at, payload
            FROM authority_wait_state
            WHERE authority_wait_id = ?
            """,
            (authority_wait_id,),
        ).fetchone()
        if row is None:
            return None
        return AuthorityWaitStateRecord(
            authority_wait_id=row["authority_wait_id"],
            workflow_instance_id=row["workflow_instance_id"],
            checkpoint_id=row["checkpoint_id"],
            gate_id=row["gate_id"],
            requested_actor_role=row["requested_actor_role"],
            status=row["status"],
            review_task_message_id=row["review_task_message_id"],
            evidence_package_id=row["evidence_package_id"],
            due_at=row["due_at"],
            responded_at=row["responded_at"],
            resolved_at=row["resolved_at"],
            hitl_decision_id=row["hitl_decision_id"],
            created_at=row["created_at"],
            payload=_json_loads(row["payload"], {}),
        )

    def list_active_authority_wait_states(self) -> list[AuthorityWaitStateRecord]:
        rows = self._conn.execute(
            """
            SELECT authority_wait_id, workflow_instance_id, checkpoint_id, gate_id, requested_actor_role,
                   status, review_task_message_id, evidence_package_id, due_at, responded_at, resolved_at,
                   hitl_decision_id, created_at, payload
            FROM authority_wait_state
            WHERE status IN (
                'created', 'waiting', 'publication_failed', 'feedback_received',
                'validated', 'resumed', 'responded'
            )
            ORDER BY created_at ASC
            """
        ).fetchall()
        return [
            AuthorityWaitStateRecord(
                authority_wait_id=row["authority_wait_id"],
                workflow_instance_id=row["workflow_instance_id"],
                checkpoint_id=row["checkpoint_id"],
                gate_id=row["gate_id"],
                requested_actor_role=row["requested_actor_role"],
                status=row["status"],
                review_task_message_id=row["review_task_message_id"],
                evidence_package_id=row["evidence_package_id"],
                due_at=row["due_at"],
                responded_at=row["responded_at"],
                resolved_at=row["resolved_at"],
                hitl_decision_id=row["hitl_decision_id"],
                created_at=row["created_at"],
                payload=_json_loads(row["payload"], {}),
            )
            for row in rows
        ]

    def list_overdue_authority_wait_states(self, now_at: Optional[str] = None) -> list[AuthorityWaitStateRecord]:
        now_at = now_at or now_iso()
        rows = self._conn.execute(
            """
            SELECT authority_wait_id, workflow_instance_id, checkpoint_id, gate_id, requested_actor_role,
                   status, review_task_message_id, evidence_package_id, due_at, responded_at, resolved_at,
                   hitl_decision_id, created_at, payload
            FROM authority_wait_state
            WHERE status = 'waiting'
              AND due_at IS NOT NULL
              AND due_at < ?
            ORDER BY due_at ASC
            """,
            (now_at,),
        ).fetchall()
        return [
            AuthorityWaitStateRecord(
                authority_wait_id=row["authority_wait_id"],
                workflow_instance_id=row["workflow_instance_id"],
                checkpoint_id=row["checkpoint_id"],
                gate_id=row["gate_id"],
                requested_actor_role=row["requested_actor_role"],
                status=row["status"],
                review_task_message_id=row["review_task_message_id"],
                evidence_package_id=row["evidence_package_id"],
                due_at=row["due_at"],
                responded_at=row["responded_at"],
                resolved_at=row["resolved_at"],
                hitl_decision_id=row["hitl_decision_id"],
                created_at=row["created_at"],
                payload=_json_loads(row["payload"], {}),
            )
            for row in rows
        ]

    def create_hitl_decision_record(
        self,
        decision_id: str,
        authority_wait_id: str,
        workflow_instance_id: str,
        checkpoint_id: str,
        linked_gate_id: str,
        decision_type: str,
        decision_value: str,
        responding_actor_id: str,
        responding_actor_role: str,
        state_transition_allowed: bool,
        validation_status: str,
        created_at: str,
        payload: dict,
    ) -> HitlDecisionStoreRecord:
        record = HitlDecisionStoreRecord(
            decision_id=decision_id,
            authority_wait_id=authority_wait_id,
            workflow_instance_id=workflow_instance_id,
            checkpoint_id=checkpoint_id,
            linked_gate_id=linked_gate_id,
            decision_type=decision_type,
            decision_value=decision_value,
            responding_actor_id=responding_actor_id,
            responding_actor_role=responding_actor_role,
            state_transition_allowed=state_transition_allowed,
            validation_status=validation_status,
            created_at=created_at,
            payload=payload,
        )
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO hitl_decision_record(
                    decision_id, authority_wait_id, workflow_instance_id, checkpoint_id, linked_gate_id,
                    decision_type, decision_value, responding_actor_id, responding_actor_role,
                    state_transition_allowed, validation_status, created_at, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.decision_id,
                    record.authority_wait_id,
                    record.workflow_instance_id,
                    record.checkpoint_id,
                    record.linked_gate_id,
                    record.decision_type,
                    record.decision_value,
                    record.responding_actor_id,
                    record.responding_actor_role,
                    1 if record.state_transition_allowed else 0,
                    record.validation_status,
                    record.created_at,
                    _json_dumps(record.payload),
                ),
        )
        return record

    def find_active_authority_wait(
        self,
        workflow_instance_id: str,
        checkpoint_id: str,
        gate_id: str,
    ) -> Optional[AuthorityWaitStateRecord]:
        row = self._conn.execute(
            """
            SELECT authority_wait_id, workflow_instance_id, checkpoint_id, gate_id, requested_actor_role,
                   status, review_task_message_id, evidence_package_id, due_at, responded_at, resolved_at,
                   hitl_decision_id, created_at, payload
            FROM authority_wait_state
            WHERE workflow_instance_id = ?
              AND checkpoint_id = ?
              AND gate_id = ?
              AND status IN ('waiting', 'publication_failed', 'feedback_received')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (workflow_instance_id, checkpoint_id, gate_id),
        ).fetchone()
        if row is None:
            return None
        return AuthorityWaitStateRecord(
            authority_wait_id=row["authority_wait_id"],
            workflow_instance_id=row["workflow_instance_id"],
            checkpoint_id=row["checkpoint_id"],
            gate_id=row["gate_id"],
            requested_actor_role=row["requested_actor_role"],
            status=row["status"],
            review_task_message_id=row["review_task_message_id"],
            evidence_package_id=row["evidence_package_id"],
            due_at=row["due_at"],
            responded_at=row["responded_at"],
            resolved_at=row["resolved_at"],
            hitl_decision_id=row["hitl_decision_id"],
            created_at=row["created_at"],
            payload=_json_loads(row["payload"], {}),
        )

    def create_phase3_runtime_record(
        self,
        record_type: str,
        status: str,
        payload: dict,
        workflow_instance_id: Optional[str] = None,
        authority_wait_id: Optional[str] = None,
        related_message_id: Optional[str] = None,
        dedupe_key: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> Phase3RuntimeRecord:
        record = Phase3RuntimeRecord(
            record_id=f"p3-{uuid.uuid4().hex[:12]}",
            record_type=record_type,
            workflow_instance_id=workflow_instance_id,
            authority_wait_id=authority_wait_id,
            related_message_id=related_message_id,
            dedupe_key=dedupe_key,
            status=status,
            created_at=created_at or now_iso(),
            payload=payload,
        )
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO phase3_runtime_record(
                    record_id, record_type, workflow_instance_id, authority_wait_id,
                    related_message_id, dedupe_key, status, created_at, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.record_id,
                    record.record_type,
                    record.workflow_instance_id,
                    record.authority_wait_id,
                    record.related_message_id,
                    record.dedupe_key,
                    record.status,
                    record.created_at,
                    _json_dumps(record.payload),
                ),
            )
        return record

    def find_phase3_runtime_record(
        self,
        record_type: str,
        dedupe_key: str,
    ) -> Optional[Phase3RuntimeRecord]:
        row = self._conn.execute(
            """
            SELECT record_id, record_type, workflow_instance_id, authority_wait_id,
                   related_message_id, dedupe_key, status, created_at, payload
            FROM phase3_runtime_record
            WHERE record_type = ? AND dedupe_key = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (record_type, dedupe_key),
        ).fetchone()
        if row is None:
            return None
        return Phase3RuntimeRecord(
            record_id=row["record_id"],
            record_type=row["record_type"],
            workflow_instance_id=row["workflow_instance_id"],
            authority_wait_id=row["authority_wait_id"],
            related_message_id=row["related_message_id"],
            dedupe_key=row["dedupe_key"],
            status=row["status"],
            created_at=row["created_at"],
            payload=_json_loads(row["payload"], {}),
        )

    def list_phase3_runtime_records(
        self,
        record_type: Optional[str] = None,
        authority_wait_id: Optional[str] = None,
    ) -> list[Phase3RuntimeRecord]:
        clauses: list[str] = []
        params: list[str] = []
        if record_type:
            clauses.append("record_type = ?")
            params.append(record_type)
        if authority_wait_id:
            clauses.append("authority_wait_id = ?")
            params.append(authority_wait_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            f"""
            SELECT record_id, record_type, workflow_instance_id, authority_wait_id,
                   related_message_id, dedupe_key, status, created_at, payload
            FROM phase3_runtime_record
            {where}
            ORDER BY created_at ASC
            """,
            tuple(params),
        ).fetchall()
        return [
            Phase3RuntimeRecord(
                record_id=row["record_id"],
                record_type=row["record_type"],
                workflow_instance_id=row["workflow_instance_id"],
                authority_wait_id=row["authority_wait_id"],
                related_message_id=row["related_message_id"],
                dedupe_key=row["dedupe_key"],
                status=row["status"],
                created_at=row["created_at"],
                payload=_json_loads(row["payload"], {}),
            )
            for row in rows
        ]

    def create_phase5_durable_record(
        self,
        family: str,
        status: str,
        payload: dict,
        workflow_instance_id: Optional[str] = None,
        target_ref: Optional[str] = None,
        authority_wait_id: Optional[str] = None,
        related_record_id: Optional[str] = None,
        dedupe_key: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> Phase5DurableRecord:
        existing = self.find_phase5_durable_record(family, dedupe_key) if dedupe_key else None
        if existing is not None:
            return existing
        record = Phase5DurableRecord(
            record_id=f"p5-{uuid.uuid4().hex[:12]}",
            family=family,
            workflow_instance_id=workflow_instance_id,
            target_ref=target_ref,
            authority_wait_id=authority_wait_id,
            related_record_id=related_record_id,
            dedupe_key=dedupe_key,
            status=status,
            created_at=created_at or now_iso(),
            payload=payload,
        )
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO phase5_durable_record(
                    record_id, family, workflow_instance_id, target_ref, authority_wait_id,
                    related_record_id, dedupe_key, status, created_at, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.record_id,
                    record.family,
                    record.workflow_instance_id,
                    record.target_ref,
                    record.authority_wait_id,
                    record.related_record_id,
                    record.dedupe_key,
                    record.status,
                    record.created_at,
                    _json_dumps(record.payload),
                ),
            )
        return record

    def find_phase5_durable_record(
        self,
        family: str,
        dedupe_key: str,
    ) -> Optional[Phase5DurableRecord]:
        row = self._conn.execute(
            """
            SELECT record_id, family, workflow_instance_id, target_ref, authority_wait_id,
                   related_record_id, dedupe_key, status, created_at, payload
            FROM phase5_durable_record
            WHERE family = ? AND dedupe_key = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (family, dedupe_key),
        ).fetchone()
        return self._phase5_record_from_row(row) if row is not None else None

    def list_phase5_durable_records(
        self,
        family: Optional[str] = None,
        workflow_instance_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[Phase5DurableRecord]:
        clauses: list[str] = []
        params: list[str] = []
        if family:
            clauses.append("family = ?")
            params.append(family)
        if workflow_instance_id:
            clauses.append("workflow_instance_id = ?")
            params.append(workflow_instance_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            f"""
            SELECT record_id, family, workflow_instance_id, target_ref, authority_wait_id,
                   related_record_id, dedupe_key, status, created_at, payload
            FROM phase5_durable_record
            {where}
            ORDER BY created_at ASC
            """,
            tuple(params),
        ).fetchall()
        return [self._phase5_record_from_row(row) for row in rows]

    def upsert_current_projection(
        self,
        workflow_instance_id: str,
        projection_status: str,
        payload: dict,
        source_record_id: Optional[str] = None,
        source_family: Optional[str] = None,
    ) -> CurrentProjectionRecord:
        existing = self.get_current_projection(workflow_instance_id)
        version = 1 if existing is None else existing.version + 1
        rebuilt_at = now_iso()
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO current_projection(
                    workflow_instance_id, projection_status, source_record_id, source_family,
                    version, rebuilt_at, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workflow_instance_id) DO UPDATE SET
                    projection_status=excluded.projection_status,
                    source_record_id=excluded.source_record_id,
                    source_family=excluded.source_family,
                    version=excluded.version,
                    rebuilt_at=excluded.rebuilt_at,
                    payload=excluded.payload
                """,
                (
                    workflow_instance_id,
                    projection_status,
                    source_record_id,
                    source_family,
                    version,
                    rebuilt_at,
                    _json_dumps(payload),
                ),
            )
        record = self.get_current_projection(workflow_instance_id)
        if record is None:
            raise KeyError(f"current_projection not found after upsert: {workflow_instance_id}")
        return record

    def get_current_projection(self, workflow_instance_id: str) -> Optional[CurrentProjectionRecord]:
        row = self._conn.execute(
            """
            SELECT workflow_instance_id, projection_status, source_record_id, source_family,
                   version, rebuilt_at, payload
            FROM current_projection
            WHERE workflow_instance_id = ?
            """,
            (workflow_instance_id,),
        ).fetchone()
        if row is None:
            return None
        return CurrentProjectionRecord(
            workflow_instance_id=row["workflow_instance_id"],
            projection_status=row["projection_status"],
            source_record_id=row["source_record_id"],
            source_family=row["source_family"],
            version=row["version"],
            rebuilt_at=row["rebuilt_at"],
            payload=_json_loads(row["payload"], {}),
        )

    def _phase5_record_from_row(self, row: sqlite3.Row) -> Phase5DurableRecord:
        return Phase5DurableRecord(
            record_id=row["record_id"],
            family=row["family"],
            workflow_instance_id=row["workflow_instance_id"],
            target_ref=row["target_ref"],
            authority_wait_id=row["authority_wait_id"],
            related_record_id=row["related_record_id"],
            dedupe_key=row["dedupe_key"],
            status=row["status"],
            created_at=row["created_at"],
            payload=_json_loads(row["payload"], {}),
        )

    def get_hitl_decision_record(self, decision_id: str) -> Optional[HitlDecisionStoreRecord]:
        row = self._conn.execute(
            """
            SELECT decision_id, authority_wait_id, workflow_instance_id, checkpoint_id, linked_gate_id,
                   decision_type, decision_value, responding_actor_id, responding_actor_role,
                   state_transition_allowed, validation_status, created_at, payload
            FROM hitl_decision_record
            WHERE decision_id = ?
            """,
            (decision_id,),
        ).fetchone()
        if row is None:
            return None
        return HitlDecisionStoreRecord(
            decision_id=row["decision_id"],
            authority_wait_id=row["authority_wait_id"],
            workflow_instance_id=row["workflow_instance_id"],
            checkpoint_id=row["checkpoint_id"],
            linked_gate_id=row["linked_gate_id"],
            decision_type=row["decision_type"],
            decision_value=row["decision_value"],
            responding_actor_id=row["responding_actor_id"],
            responding_actor_role=row["responding_actor_role"],
            state_transition_allowed=bool(row["state_transition_allowed"]),
            validation_status=row["validation_status"],
            created_at=row["created_at"],
            payload=_json_loads(row["payload"], {}),
        )

    def create_abnormal_state_record(
        self,
        abnormal_state_id: str,
        error_event_id: str,
        workflow_instance_id: Optional[str],
        error_class: str,
        abnormal_class: str,
        resolved: bool,
        notification_sent: bool,
        resolution_record_id: Optional[str],
        escalation_timer_id: Optional[str],
        detected_at: str,
        resolved_at: Optional[str],
        payload: dict,
    ) -> AbnormalStateStoreRecord:
        record = AbnormalStateStoreRecord(
            abnormal_state_id=abnormal_state_id,
            error_event_id=error_event_id,
            workflow_instance_id=workflow_instance_id,
            error_class=error_class,
            abnormal_class=abnormal_class,
            resolved=resolved,
            notification_sent=notification_sent,
            resolution_record_id=resolution_record_id,
            escalation_timer_id=escalation_timer_id,
            detected_at=detected_at,
            resolved_at=resolved_at,
            payload=payload,
        )
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO abnormal_state_record(
                    abnormal_state_id, error_event_id, workflow_instance_id, error_class, abnormal_class,
                    resolved, notification_sent, resolution_record_id, escalation_timer_id,
                    detected_at, resolved_at, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(abnormal_state_id) DO UPDATE SET
                    error_event_id=excluded.error_event_id,
                    workflow_instance_id=excluded.workflow_instance_id,
                    error_class=excluded.error_class,
                    abnormal_class=excluded.abnormal_class,
                    resolved=excluded.resolved,
                    notification_sent=excluded.notification_sent,
                    resolution_record_id=excluded.resolution_record_id,
                    escalation_timer_id=excluded.escalation_timer_id,
                    detected_at=excluded.detected_at,
                    resolved_at=excluded.resolved_at,
                    payload=excluded.payload
                """,
                (
                    record.abnormal_state_id,
                    record.error_event_id,
                    record.workflow_instance_id,
                    record.error_class,
                    record.abnormal_class,
                    1 if record.resolved else 0,
                    1 if record.notification_sent else 0,
                    record.resolution_record_id,
                    record.escalation_timer_id,
                    record.detected_at,
                    record.resolved_at,
                    _json_dumps(record.payload),
                ),
            )
        return record

    def list_unresolved_abnormal_states(self, workflow_instance_id: Optional[str] = None) -> list[AbnormalStateStoreRecord]:
        if workflow_instance_id:
            rows = self._conn.execute(
                """
                SELECT abnormal_state_id, error_event_id, workflow_instance_id, error_class, abnormal_class,
                       resolved, notification_sent, resolution_record_id, escalation_timer_id,
                       detected_at, resolved_at, payload
                FROM abnormal_state_record
                WHERE resolved = 0 AND workflow_instance_id = ?
                ORDER BY detected_at ASC
                """,
                (workflow_instance_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT abnormal_state_id, error_event_id, workflow_instance_id, error_class, abnormal_class,
                       resolved, notification_sent, resolution_record_id, escalation_timer_id,
                       detected_at, resolved_at, payload
                FROM abnormal_state_record
                WHERE resolved = 0
                ORDER BY detected_at ASC
                """
            ).fetchall()
        return [
            AbnormalStateStoreRecord(
                abnormal_state_id=row["abnormal_state_id"],
                error_event_id=row["error_event_id"],
                workflow_instance_id=row["workflow_instance_id"],
                error_class=row["error_class"],
                abnormal_class=row["abnormal_class"],
                resolved=bool(row["resolved"]),
                notification_sent=bool(row["notification_sent"]),
                resolution_record_id=row["resolution_record_id"],
                escalation_timer_id=row["escalation_timer_id"],
                detected_at=row["detected_at"],
                resolved_at=row["resolved_at"],
                payload=_json_loads(row["payload"], {}),
            )
            for row in rows
        ]

    def create_resolution_record(
        self,
        resolution_id: str,
        abnormal_state_id: str,
        error_event_id: str,
        workflow_instance_id: str,
        resolved_by: str,
        resolution_action: str,
        created_at: str,
        payload: dict,
    ) -> ResolutionStoreRecord:
        record = ResolutionStoreRecord(
            resolution_id=resolution_id,
            abnormal_state_id=abnormal_state_id,
            error_event_id=error_event_id,
            workflow_instance_id=workflow_instance_id,
            resolved_by=resolved_by,
            resolution_action=resolution_action,
            created_at=created_at,
            payload=payload,
        )
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO resolution_record(
                    resolution_id, abnormal_state_id, error_event_id, workflow_instance_id,
                    resolved_by, resolution_action, created_at, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.resolution_id,
                    record.abnormal_state_id,
                    record.error_event_id,
                    record.workflow_instance_id,
                    record.resolved_by,
                    record.resolution_action,
                    record.created_at,
                    _json_dumps(record.payload),
                ),
            )
        return record

    def get_resolution_record(self, resolution_id: str) -> Optional[ResolutionStoreRecord]:
        row = self._conn.execute(
            """
            SELECT resolution_id, abnormal_state_id, error_event_id, workflow_instance_id,
                   resolved_by, resolution_action, created_at, payload
            FROM resolution_record
            WHERE resolution_id = ?
            """,
            (resolution_id,),
        ).fetchone()
        if row is None:
            return None
        return ResolutionStoreRecord(
            resolution_id=row["resolution_id"],
            abnormal_state_id=row["abnormal_state_id"],
            error_event_id=row["error_event_id"],
            workflow_instance_id=row["workflow_instance_id"],
            resolved_by=row["resolved_by"],
            resolution_action=row["resolution_action"],
            created_at=row["created_at"],
            payload=_json_loads(row["payload"], {}),
        )

    def get_abnormal_state_record(self, abnormal_state_id: str) -> Optional[AbnormalStateStoreRecord]:
        row = self._conn.execute(
            """
            SELECT abnormal_state_id, error_event_id, workflow_instance_id, error_class, abnormal_class,
                   resolved, notification_sent, resolution_record_id, escalation_timer_id,
                   detected_at, resolved_at, payload
            FROM abnormal_state_record
            WHERE abnormal_state_id = ?
            """,
            (abnormal_state_id,),
        ).fetchone()
        if row is None:
            return None
        return AbnormalStateStoreRecord(
            abnormal_state_id=row["abnormal_state_id"],
            error_event_id=row["error_event_id"],
            workflow_instance_id=row["workflow_instance_id"],
            error_class=row["error_class"],
            abnormal_class=row["abnormal_class"],
            resolved=bool(row["resolved"]),
            notification_sent=bool(row["notification_sent"]),
            resolution_record_id=row["resolution_record_id"],
            escalation_timer_id=row["escalation_timer_id"],
            detected_at=row["detected_at"],
            resolved_at=row["resolved_at"],
            payload=_json_loads(row["payload"], {}),
        )

    def create_escalation_timer(
        self,
        escalation_timer_id: str,
        workflow_instance_id: str,
        trigger_type: str,
        due_at: str,
        status: str,
        created_at: str,
        payload: dict,
    ) -> EscalationTimerStoreRecord:
        record = EscalationTimerStoreRecord(
            escalation_timer_id=escalation_timer_id,
            workflow_instance_id=workflow_instance_id,
            trigger_type=trigger_type,
            due_at=due_at,
            status=status,
            created_at=created_at,
            payload=payload,
        )
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO escalation_timer(
                    escalation_timer_id, workflow_instance_id, trigger_type, due_at, status, created_at, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(escalation_timer_id) DO UPDATE SET
                    workflow_instance_id=excluded.workflow_instance_id,
                    trigger_type=excluded.trigger_type,
                    due_at=excluded.due_at,
                    status=excluded.status,
                    created_at=excluded.created_at,
                    payload=excluded.payload
                """,
                (
                    record.escalation_timer_id,
                    record.workflow_instance_id,
                    record.trigger_type,
                    record.due_at,
                    record.status,
                    record.created_at,
                    _json_dumps(record.payload),
                ),
            )
        return record

    def _initialize_schema(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS pending_task (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL UNIQUE,
                    task_type TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    correlation_id TEXT NOT NULL,
                    workflow_id TEXT NOT NULL,
                    skill_name TEXT,
                    state TEXT NOT NULL,
                    input_payload TEXT NOT NULL,
                    result_payload TEXT,
                    error_payload TEXT,
                    reply_to_subject TEXT,
                    priority INTEGER NOT NULL DEFAULT 0,
                    received_at TEXT NOT NULL,
                    first_response_deadline TEXT,
                    completion_deadline TEXT,
                    last_progress_at TEXT NOT NULL,
                    completed_at TEXT,
                    created_by TEXT NOT NULL,
                    updated_by TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS callback_wait (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    callback_id TEXT NOT NULL UNIQUE,
                    correlation_id TEXT NOT NULL,
                    expected_subject TEXT NOT NULL,
                    expected_source_agent_id TEXT NOT NULL,
                    request_message_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    callback_type TEXT NOT NULL,
                    request_payload TEXT NOT NULL,
                    response_payload TEXT,
                    reply_subject TEXT,
                    deadline TEXT,
                    first_response_deadline TEXT,
                    completion_deadline TEXT,
                    last_progress_at TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    completed_at TEXT,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 3,
                    error_summary TEXT,
                    created_by TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS side_effect_outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    outbox_id TEXT NOT NULL UNIQUE,
                    message_id TEXT,
                    correlation_id TEXT NOT NULL,
                    causation_id TEXT,
                    side_effect_type TEXT NOT NULL,
                    target TEXT NOT NULL,
                    payload_summary TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    state TEXT NOT NULL,
                    planned_at TEXT NOT NULL,
                    published_at TEXT,
                    confirmed_at TEXT,
                    confirmed_by TEXT,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 3,
                    next_retry_at TEXT,
                    error_summary TEXT,
                    checksum TEXT,
                    created_by TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS envelope_inbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id TEXT,
                    envelope_id TEXT NOT NULL UNIQUE,
                    subject TEXT NOT NULL,
                    state TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    raw_inbound_envelope TEXT,
                    normalized_execution_envelope TEXT,
                    validation_errors TEXT,
                    failure_class TEXT,
                    failure_subclass TEXT,
                    broker_action TEXT,
                    terminal_outcome TEXT,
                    anomaly_id TEXT,
                    abnormal_state_id TEXT,
                    handler_exhausted INTEGER NOT NULL DEFAULT 0,
                    governed_state_store_ref TEXT,
                    workflow_instance_id TEXT,
                    message_id TEXT,
                    causation_id TEXT,
                    correlation_id TEXT,
                    source_agent_id TEXT,
                    target_agent_id TEXT,
                    local_retry_count INTEGER NOT NULL DEFAULT 0,
                    max_local_retries INTEGER NOT NULL DEFAULT 3,
                    received_at TEXT NOT NULL,
                    completed_at TEXT,
                    error TEXT
                );

                CREATE TABLE IF NOT EXISTS durable_idempotency (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    message_id TEXT NOT NULL,
                    workflow_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    result_detail TEXT,
                    recorded_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS runtime_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    runtime_id TEXT NOT NULL UNIQUE,
                    agent_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT,
                    quarantined_path TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS authority_wait_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    authority_wait_id TEXT NOT NULL UNIQUE,
                    workflow_instance_id TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL,
                    gate_id TEXT NOT NULL,
                    requested_actor_role TEXT NOT NULL,
                    status TEXT NOT NULL,
                    review_task_message_id TEXT,
                    evidence_package_id TEXT,
                    due_at TEXT,
                    responded_at TEXT,
                    resolved_at TEXT,
                    hitl_decision_id TEXT,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS hitl_decision_record (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    decision_id TEXT NOT NULL UNIQUE,
                    authority_wait_id TEXT NOT NULL,
                    workflow_instance_id TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL,
                    linked_gate_id TEXT NOT NULL,
                    decision_type TEXT NOT NULL,
                    decision_value TEXT NOT NULL,
                    responding_actor_id TEXT NOT NULL,
                    responding_actor_role TEXT NOT NULL,
                    state_transition_allowed INTEGER NOT NULL,
                    validation_status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS phase3_runtime_record (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id TEXT NOT NULL UNIQUE,
                    record_type TEXT NOT NULL,
                    workflow_instance_id TEXT,
                    authority_wait_id TEXT,
                    related_message_id TEXT,
                    dedupe_key TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS phase5_durable_record (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id TEXT NOT NULL UNIQUE,
                    family TEXT NOT NULL,
                    workflow_instance_id TEXT,
                    target_ref TEXT,
                    authority_wait_id TEXT,
                    related_record_id TEXT,
                    dedupe_key TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS current_projection (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_instance_id TEXT NOT NULL UNIQUE,
                    projection_status TEXT NOT NULL,
                    source_record_id TEXT,
                    source_family TEXT,
                    version INTEGER NOT NULL,
                    rebuilt_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS abnormal_state_record (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    abnormal_state_id TEXT NOT NULL UNIQUE,
                    error_event_id TEXT NOT NULL,
                    workflow_instance_id TEXT,
                    error_class TEXT NOT NULL,
                    abnormal_class TEXT NOT NULL,
                    resolved INTEGER NOT NULL DEFAULT 0,
                    notification_sent INTEGER NOT NULL DEFAULT 0,
                    resolution_record_id TEXT,
                    escalation_timer_id TEXT,
                    detected_at TEXT NOT NULL,
                    resolved_at TEXT,
                    payload TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS resolution_record (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    resolution_id TEXT NOT NULL UNIQUE,
                    abnormal_state_id TEXT NOT NULL,
                    error_event_id TEXT NOT NULL,
                    workflow_instance_id TEXT NOT NULL,
                    resolved_by TEXT NOT NULL,
                    resolution_action TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS escalation_timer (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    escalation_timer_id TEXT NOT NULL UNIQUE,
                    workflow_instance_id TEXT NOT NULL,
                    trigger_type TEXT NOT NULL,
                    due_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_pending_task_state ON pending_task(state);
                CREATE INDEX IF NOT EXISTS idx_pending_task_workflow_id ON pending_task(workflow_id);
                CREATE INDEX IF NOT EXISTS idx_pending_task_received_at ON pending_task(received_at);
                CREATE INDEX IF NOT EXISTS idx_callback_wait_state ON callback_wait(state);
                CREATE INDEX IF NOT EXISTS idx_callback_wait_task_id ON callback_wait(task_id);
                CREATE INDEX IF NOT EXISTS idx_callback_wait_deadline ON callback_wait(deadline);
                CREATE INDEX IF NOT EXISTS idx_outbox_state ON side_effect_outbox(state);
                CREATE INDEX IF NOT EXISTS idx_outbox_message_id ON side_effect_outbox(message_id);
                CREATE INDEX IF NOT EXISTS idx_outbox_correlation_id ON side_effect_outbox(correlation_id);
                CREATE INDEX IF NOT EXISTS idx_envelope_inbox_state ON envelope_inbox(state);
                CREATE INDEX IF NOT EXISTS idx_envelope_inbox_record_id ON envelope_inbox(record_id);
                CREATE INDEX IF NOT EXISTS idx_idempotency_workflow_id ON durable_idempotency(workflow_id);
                CREATE INDEX IF NOT EXISTS idx_authority_wait_state_status ON authority_wait_state(status);
                CREATE INDEX IF NOT EXISTS idx_authority_wait_due_at ON authority_wait_state(due_at);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_authority_wait_active_unique
                ON authority_wait_state(workflow_instance_id, checkpoint_id, gate_id)
                WHERE status IN ('waiting', 'publication_failed', 'feedback_received');
                CREATE INDEX IF NOT EXISTS idx_hitl_decision_wait ON hitl_decision_record(authority_wait_id);
                CREATE INDEX IF NOT EXISTS idx_phase3_runtime_record_type ON phase3_runtime_record(record_type);
                CREATE INDEX IF NOT EXISTS idx_phase3_runtime_record_wait ON phase3_runtime_record(authority_wait_id);
                CREATE INDEX IF NOT EXISTS idx_phase3_runtime_record_dedupe ON phase3_runtime_record(record_type, dedupe_key);
                CREATE INDEX IF NOT EXISTS idx_phase5_durable_record_family ON phase5_durable_record(family);
                CREATE INDEX IF NOT EXISTS idx_phase5_durable_record_workflow ON phase5_durable_record(workflow_instance_id);
                CREATE INDEX IF NOT EXISTS idx_phase5_durable_record_status ON phase5_durable_record(status);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_phase5_durable_record_dedupe
                ON phase5_durable_record(family, dedupe_key)
                WHERE dedupe_key IS NOT NULL;
                CREATE INDEX IF NOT EXISTS idx_abnormal_state_resolved ON abnormal_state_record(resolved);
                CREATE INDEX IF NOT EXISTS idx_abnormal_state_workflow ON abnormal_state_record(workflow_instance_id);
                CREATE INDEX IF NOT EXISTS idx_escalation_timer_due_at ON escalation_timer(due_at);
                """
            )
        self._migrate_schema()

    def _migrate_schema(self) -> None:
        envelope_inbox_columns = {
            "record_id": "TEXT",
            "raw_inbound_envelope": "TEXT",
            "normalized_execution_envelope": "TEXT",
            "validation_errors": "TEXT",
            "failure_class": "TEXT",
            "failure_subclass": "TEXT",
            "broker_action": "TEXT",
            "terminal_outcome": "TEXT",
            "anomaly_id": "TEXT",
            "abnormal_state_id": "TEXT",
            "handler_exhausted": "INTEGER NOT NULL DEFAULT 0",
            "governed_state_store_ref": "TEXT",
            "workflow_instance_id": "TEXT",
            "message_id": "TEXT",
            "causation_id": "TEXT",
            "correlation_id": "TEXT",
            "source_agent_id": "TEXT",
            "target_agent_id": "TEXT",
            "local_retry_count": "INTEGER NOT NULL DEFAULT 0",
            "max_local_retries": "INTEGER NOT NULL DEFAULT 3",
        }
        existing_columns = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(envelope_inbox)").fetchall()
        }
        with self._conn:
            for column_name, column_def in envelope_inbox_columns.items():
                if column_name not in existing_columns:
                    self._conn.execute(
                        f"ALTER TABLE envelope_inbox ADD COLUMN {column_name} {column_def}"
                    )
