"""Always-on listener runtime primitives for Phase 3 coordination."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from nexus.mq.coordination_runtime import CoordinationRuntime
from nexus.mq.phase3_uat_command_bridge import Phase3UatCommandBridge
from nexus.mq.protocol import ProtocolEnvelope
from nexus.mq.protocol_boundary import ProtocolMessageBoundary
from nexus.mq.protocol_routing import build_ops_anomaly_subject


@dataclass
class ListenerRuntimeConfig:
    max_pending_tasks: int = 100
    emit_anomaly_on_invalid: bool = True
    reconcile_outbox_on_startup: bool = True
    phase5_restart_scan_on_startup: bool = True


@dataclass
class ListenerStartupResult:
    runtime_status: str
    recovered_pending_tasks: int
    recovered_callback_waits: int
    reconciled_outbox_records: int
    phase5_recovery_scan_records: int = 0
    phase5_recovery_action_records: int = 0
    quarantined: bool = False
    errors: list[str] | None = None


@dataclass
class ListenerPollResult:
    status: str
    consumed_message_id: Optional[str] = None
    acked: bool = False
    anomaly_published: bool = False
    artifact_path: Optional[str] = None
    runtime_record_id: Optional[str] = None
    errors: list[str] | None = None


@dataclass
class TimeoutEmitResult:
    published_count: int
    task_timeouts: int
    callback_timeouts: int


class ListenerRuntime:
    """Thin runtime layer that turns coordination primitives into a polling loop."""

    def __init__(
        self,
        adapter,
        coordination_runtime: CoordinationRuntime,
        config: Optional[ListenerRuntimeConfig] = None,
    ):
        self.adapter = adapter
        self.runtime = coordination_runtime
        self.config = config or ListenerRuntimeConfig()
        self.boundary = ProtocolMessageBoundary(self.runtime.identity_store)
        self.phase3_uat_bridge = Phase3UatCommandBridge(self.runtime)

    @classmethod
    def from_paths(
        cls,
        adapter,
        runtime_id: str,
        agent_id: str,
        role: str,
        db_path: str | Path,
        identity_yaml_path: str | Path,
        config: Optional[ListenerRuntimeConfig] = None,
    ) -> "ListenerRuntime":
        runtime = CoordinationRuntime.from_paths(
            runtime_id=runtime_id,
            agent_id=agent_id,
            role=role,
            db_path=db_path,
            identity_yaml_path=identity_yaml_path,
        )
        return cls(adapter=adapter, coordination_runtime=runtime, config=config)

    def startup(self) -> ListenerStartupResult:
        runtime_status = self.runtime.startup()
        recovered_pending = len(self.runtime.state_store.list_pending_tasks(states=["PENDING", "PROCESSING"]))
        recovered_callbacks = len(self.runtime.state_store.list_waiting_callbacks())
        reconciled = 0
        phase5_scans_before = len(self.runtime.state_store.list_phase5_durable_records("recovery_scan_record"))
        phase5_actions_before = len(self.runtime.state_store.list_phase5_durable_records("recovery_action_record"))
        if runtime_status.status == "QUARANTINED":
            return ListenerStartupResult(
                runtime_status=runtime_status.status,
                recovered_pending_tasks=recovered_pending,
                recovered_callback_waits=recovered_callbacks,
                reconciled_outbox_records=0,
                phase5_recovery_scan_records=0,
                phase5_recovery_action_records=0,
                quarantined=True,
                errors=[runtime_status.reason] if runtime_status.reason else [],
            )
        if self.config.phase5_restart_scan_on_startup:
            self.runtime.run_phase5_restart_scan()
        if self.config.reconcile_outbox_on_startup:
            reconciled = self.reconcile_outbox_once()
        phase5_scans_after = len(self.runtime.state_store.list_phase5_durable_records("recovery_scan_record"))
        phase5_actions_after = len(self.runtime.state_store.list_phase5_durable_records("recovery_action_record"))
        return ListenerStartupResult(
            runtime_status=runtime_status.status,
            recovered_pending_tasks=recovered_pending,
            recovered_callback_waits=recovered_callbacks,
            reconciled_outbox_records=reconciled,
            phase5_recovery_scan_records=phase5_scans_after - phase5_scans_before,
            phase5_recovery_action_records=phase5_actions_after - phase5_actions_before,
        )

    def poll_once(self) -> ListenerPollResult:
        message = self.adapter.consume()
        if message is None:
            return ListenerPollResult(status="idle")

        raw_envelope = message.get("envelope")
        envelope_dict = raw_envelope if isinstance(raw_envelope, dict) else {}
        subject = message.get("subject") or envelope_dict.get("subject") or ""
        message_id = envelope_dict.get("message_id")
        execution_type = envelope_dict.get("message_type") if envelope_dict and not envelope_dict.get("protocol_version") else None

        if self._backlog_exceeded() and self._is_business_subject(subject):
            return ListenerPollResult(
                status="backlog_paused",
                consumed_message_id=message_id,
                acked=False,
            )

        if execution_type == "Feedback_Message":
            result = self.runtime.receive_feedback(subject, raw_envelope)
            if result.valid and result.envelope is not None and result.ack_allowed:
                self.adapter.ack(result.envelope.message_id)
                return ListenerPollResult(
                    status="feedback_received",
                    consumed_message_id=result.envelope.message_id,
                    acked=True,
                )
            broker_handled = self._apply_broker_action(result.broker_action, result.intake_record, message_id)
            anomaly = self._emit_anomaly_if_possible(envelope_dict, result.errors or []) if self._should_publish_anomaly(result.broker_action, result.intake_record) else False
            return ListenerPollResult(
                status="feedback_rejected",
                consumed_message_id=self._result_message_id(message_id, result.intake_record),
                acked=broker_handled == "ack",
                anomaly_published=anomaly,
                errors=result.errors,
            )

        if execution_type in {"Evidence_Write_Message", "State_Transition_Message"}:
            errors = [f"DEFERRED_TRANSPORT_INACTIVE: {execution_type}"]
            result = self.runtime.intake_inbound_message(subject, raw_envelope)
            broker_handled = self._apply_broker_action(result.broker_action, result.intake_record, message_id)
            anomaly = self._emit_anomaly_if_possible(envelope_dict, errors) if self._should_publish_anomaly(result.broker_action, result.intake_record) else False
            return ListenerPollResult(
                status="deferred_rejected",
                consumed_message_id=self._result_message_id(message_id, result.intake_record),
                acked=broker_handled == "ack",
                anomaly_published=anomaly,
                errors=errors,
            )

        if execution_type == "Business_Message" or (execution_type is None and self._is_callback_subject(subject)):
            result = self.runtime.receive_callback(subject, raw_envelope)
            if result.valid and result.envelope is not None and result.ack_allowed:
                self.adapter.ack(result.envelope.message_id)
                return ListenerPollResult(
                    status="callback_received" if execution_type is None else "business_callback_received",
                    consumed_message_id=result.envelope.message_id,
                    acked=True,
                )
            broker_handled = self._apply_broker_action(result.broker_action, result.intake_record, message_id)
            anomaly = self._emit_anomaly_if_possible(envelope_dict, result.errors or []) if self._should_publish_anomaly(result.broker_action, result.intake_record) else False
            return ListenerPollResult(
                status="callback_rejected" if execution_type is None else "business_callback_rejected",
                consumed_message_id=self._result_message_id(message_id, result.intake_record),
                acked=broker_handled == "ack",
                anomaly_published=anomaly,
                errors=result.errors,
            )

        result = self.runtime.intake_inbound_message(subject, raw_envelope)
        if result.valid and result.envelope is not None and result.ack_allowed:
            self.adapter.ack(result.envelope.message_id)
            bridge_result = self.phase3_uat_bridge.execute_if_supported(
                pending_task=result.pending_task,
                envelope=result.envelope,
            ) if result.pending_task is not None else None
            if bridge_result is not None and bridge_result.executed:
                return ListenerPollResult(
                    status="command_executed" if bridge_result.status == "artifact_generated" else "command_execution_failed",
                    consumed_message_id=result.envelope.message_id,
                    acked=True,
                    artifact_path=bridge_result.artifact_path,
                    runtime_record_id=bridge_result.runtime_record_id,
                    errors=[bridge_result.error] if bridge_result.error else None,
                )
            return ListenerPollResult(
                status=self._intake_status_for_execution_type(execution_type),
                consumed_message_id=result.envelope.message_id,
                acked=True,
            )

        broker_handled = self._apply_broker_action(result.broker_action, result.intake_record, message_id)
        anomaly = self._emit_anomaly_if_possible(envelope_dict, result.errors or []) if self._should_publish_anomaly(result.broker_action, result.intake_record) else False
        return ListenerPollResult(
            status="message_rejected",
            consumed_message_id=self._result_message_id(message_id, result.intake_record),
            acked=broker_handled == "ack",
            anomaly_published=anomaly,
            errors=result.errors,
        )

    def emit_timeouts_once(self, now_at: Optional[str] = None) -> TimeoutEmitResult:
        scan = self.runtime.scan_timeouts(now_at=now_at)
        published = 0

        for timeout_envelope in scan.task_timeout_envelopes:
            outbox = self.runtime.record_outbox_publish(timeout_envelope)
            self.adapter.publish(timeout_envelope.to_dict())
            self.runtime.confirm_outbox_publish(outbox.outbox_id)
            self.runtime.state_store.update_pending_task(
                task_id=timeout_envelope.causation_id,
                state="TIMED_OUT",
                updated_by=self.runtime.runtime_id,
                error_payload=timeout_envelope.payload,
            )
            published += 1

        for timeout_envelope in scan.callback_timeout_envelopes:
            outbox = self.runtime.record_outbox_publish(timeout_envelope)
            self.adapter.publish(timeout_envelope.to_dict())
            self.runtime.confirm_outbox_publish(outbox.outbox_id)
            self.runtime.state_store.expire_callback_wait(
                callback_id=str(timeout_envelope.payload["record_id"]),
                error_summary=timeout_envelope.payload["reason"],
            )
            published += 1

        for timeout_envelope in scan.authority_wait_timeout_envelopes:
            outbox = self.runtime.record_outbox_publish(timeout_envelope)
            self.adapter.publish(timeout_envelope.to_dict())
            self.runtime.confirm_outbox_publish(outbox.outbox_id)
            published += 1

        return TimeoutEmitResult(
            published_count=published,
            task_timeouts=len(scan.task_timeout_envelopes),
            callback_timeouts=len(scan.callback_timeout_envelopes) + len(scan.authority_wait_timeout_envelopes),
        )

    def reconcile_outbox_once(self) -> int:
        records = self.runtime.state_store.list_outbox_requiring_reconciliation()
        reconciled = 0
        for record in records:
            plan = self.runtime.plan_side_effect_reconciliation(record)
            if not plan["publish_allowed"]:
                continue
            self.adapter.publish(record.payload)
            self.runtime.confirm_outbox_publish(record.outbox_id)
            reconciled += 1
        return reconciled

    def close(self) -> None:
        self.runtime.close()

    def _emit_anomaly_if_possible(self, envelope_dict: dict, errors: list[str]) -> bool:
        if not self.config.emit_anomaly_on_invalid:
            return False
        try:
            anomaly = self.boundary.build_anomaly_envelope(
                original_envelope_dict=envelope_dict,
                reporting_agent_id=self.runtime.agent_id,
                reporting_runtime_instance_id=self.runtime.identity_store.get_agent(self.runtime.agent_id).runtime_instance_id,
                reporting_role=self.runtime.role,
                error_code=errors[0] if errors else "INVALID_MESSAGE",
                details={"errors": errors},
            )
        except Exception:
            try:
                anomaly = ProtocolEnvelope(
                    message_type="anomaly",
                    source_agent_id=self.runtime.agent_id,
                    source_runtime_instance_id=self.runtime.identity_store.get_agent(self.runtime.agent_id).runtime_instance_id,
                    source_role=self.runtime.role,
                    authority_scope="workflow.anomaly",
                    payload={
                        "error_code": errors[0] if errors else "INVALID_MESSAGE",
                        "details": {"errors": errors},
                        "reported_subject": build_ops_anomaly_subject(),
                    },
                    correlation_id=envelope_dict.get("correlation_id", f"corr-anomaly-{self.runtime.agent_id}"),
                    causation_id=envelope_dict.get("message_id"),
                    idempotency_key=f"anomaly:{self.runtime.agent_id}:{envelope_dict.get('message_id', 'unknown')}",
                    target_agent_id=envelope_dict.get("source_agent_id"),
                    reply_to_subject=envelope_dict.get("reply_to_subject"),
                )
            except Exception:
                return False
        self.adapter.publish(anomaly.to_dict())
        return True

    def _apply_broker_action(self, broker_action: Optional[str], intake_record, fallback_message_id: Optional[str]) -> str:
        message_id = self._result_message_id(fallback_message_id, intake_record)
        if not message_id:
            return "none"
        if broker_action in {"REJECT", "TERM"}:
            self.adapter.ack(message_id)
            return "ack"
        if broker_action == "NAK" and hasattr(self.adapter, "nak"):
            self.adapter.nak(message_id, reason="phase2_retryable_expiry")
            return "nak"
        return "none"

    @staticmethod
    def _result_message_id(fallback_message_id: Optional[str], intake_record) -> Optional[str]:
        if intake_record is not None:
            return intake_record.message_id or intake_record.envelope_id
        return fallback_message_id

    @staticmethod
    def _should_publish_anomaly(broker_action: Optional[str], intake_record) -> bool:
        return bool(intake_record is not None and intake_record.anomaly_id and broker_action != "NAK")

    def _backlog_exceeded(self) -> bool:
        active = self.runtime.state_store.list_pending_tasks(states=["PENDING", "PROCESSING"])
        return len(active) >= self.config.max_pending_tasks

    @staticmethod
    def _is_callback_subject(subject: str) -> bool:
        return subject.endswith(".callbacks")

    @staticmethod
    def _is_business_subject(subject: str) -> bool:
        return (
            subject.endswith(".inbox")
            or subject.startswith("workflow.")
            or subject.startswith("review.")
        )

    @staticmethod
    def _intake_status_for_execution_type(execution_type: Optional[str]) -> str:
        mapping = {
            None: "message_intake",
            "Command_Message": "command_intake",
            "Review_Task": "review_task_intake",
            "Timeout_Message": "timeout_recorded",
            "Retry_Message": "retry_recorded",
            "Dead_Letter_Message": "dead_letter_recorded",
        }
        return mapping.get(execution_type, "message_intake")
