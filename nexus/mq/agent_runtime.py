"""Minimal WBS 15.6 controlled-UAT agent runtime bootstrap."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import uuid

import yaml

from nexus.mq.adapter_nats import MqAdapterNats
from nexus.mq.listener_runtime import ListenerRuntime, ListenerRuntimeConfig
from nexus.mq.listener_supervisor import ListenerSupervisor, SupervisorConfig
from nexus.mq.message_contracts import build_execution_envelope, validate_execution_message


APPROVED_AGENT_IDS = {"nova", "jarvis"}
APPROVED_ENVIRONMENT = "controlled_uat"
APPROVED_PREFIX = "nexus.3_5.uat."
APPROVED_ACK_POLICY = "consumer_intake_only_after_durable_intake"
APPROVED_RETURN_PATH_POLICY = "prefer_reply_to_then_callback"
APPROVED_HANDLER_MAPPING = {
    "Command_Message": "controlled_uat_handoff_receive",
    "Business_Message": "controlled_uat_return_receive",
}
CONTROLLED_WORKFLOW_TYPE = "controlled_3_5_uat"


@dataclass
class AgentRuntimeValidationResult:
    valid: bool
    errors: list[str]
    config_hash: str = ""


@dataclass
class AgentRuntimeBootstrapResult:
    config: dict[str, Any]
    validation: AgentRuntimeValidationResult
    adapter: Any
    listener: ListenerRuntime
    supervisor: ListenerSupervisor
    evidence_root: Path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_agent_runtime_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"CONFIG_FILE_NOT_FOUND: {config_path}")
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"CONFIG_PARSE_ERROR: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("CONFIG_SCHEMA_INVALID: root must be a mapping")
    data["_config_path"] = str(config_path)
    return data


def validate_agent_runtime_config(config: dict[str, Any]) -> AgentRuntimeValidationResult:
    errors: list[str] = []
    required = [
        "agent_id",
        "role",
        "runtime_instance_id",
        "environment",
        "authority_scopes",
        "broker",
        "consumer",
        "subjects",
        "trusted_subject_prefixes",
        "supported_message_types",
        "capabilities",
        "handler_mapping",
        "evidence_root",
        "ack_policy",
        "return_path_policy",
    ]
    for key in required:
        if key not in config:
            errors.append(f"MISSING_REQUIRED_CONFIG_FIELD: {key}")

    agent_id = config.get("agent_id")
    if agent_id not in APPROVED_AGENT_IDS:
        errors.append(f"UNAPPROVED_AGENT_ID: {agent_id}")
    if config.get("environment") != APPROVED_ENVIRONMENT:
        errors.append(f"UNAPPROVED_ENVIRONMENT: {config.get('environment')}")
    if config.get("ack_policy") != APPROVED_ACK_POLICY:
        errors.append(f"UNSAFE_ACK_POLICY: {config.get('ack_policy')}")
    if config.get("return_path_policy") != APPROVED_RETURN_PATH_POLICY:
        errors.append(f"UNSAFE_RETURN_PATH_POLICY: {config.get('return_path_policy')}")
    if not config.get("evidence_root"):
        errors.append("MISSING_REQUIRED_CONFIG_FIELD: evidence_root")

    broker = _section(config, "broker", errors)
    consumer = _section(config, "consumer", errors)
    subjects = _section(config, "subjects", errors)

    _require_broker(broker, errors)
    _require_consumer(config, consumer, errors)
    _require_subjects(config, subjects, errors)
    _require_list(config, "authority_scopes", errors)
    _require_list(config, "trusted_subject_prefixes", errors)
    _require_list(config, "supported_message_types", errors)
    _require_list(config, "capabilities", errors)
    _require_handler_mapping(config, errors)
    if set(config.get("supported_message_types", [])) != set(APPROVED_HANDLER_MAPPING.keys()):
        errors.append(f"UNAPPROVED_MESSAGE_TYPES: {config.get('supported_message_types')}")
    if set(config.get("capabilities", [])) != set(APPROVED_HANDLER_MAPPING.values()):
        errors.append(f"UNAPPROVED_CAPABILITIES: {config.get('capabilities')}")

    for prefix in config.get("trusted_subject_prefixes", []):
        if prefix != APPROVED_PREFIX:
            errors.append(f"UNAPPROVED_TRUSTED_SUBJECT_PREFIX: {prefix}")
    for field, values in (
        ("broker.stream_subjects", broker.get("stream_subjects", [])),
        ("consumer.filter_subjects", consumer.get("filter_subjects", [])),
        ("subjects", list(subjects.values())),
    ):
        for subject in values:
            if not _is_approved_subject(subject):
                errors.append(f"UNAPPROVED_SUBJECT: {field}={subject}")
            if "*" in str(subject) or ">" in str(subject):
                errors.append(f"WILDCARD_PUBLISH_OR_BINDING_NOT_ALLOWED: {field}={subject}")

    config_hash = hashlib.sha256(
        json.dumps(_without_runtime_fields(config), sort_keys=True).encode("utf-8")
    ).hexdigest()
    return AgentRuntimeValidationResult(valid=not errors, errors=errors, config_hash=config_hash)


def bootstrap_from_config(
    path: str | Path,
    *,
    adapter: Any | None = None,
    identity_yaml_path: str | Path | None = None,
) -> AgentRuntimeBootstrapResult:
    config = load_agent_runtime_config(path)
    validation = validate_agent_runtime_config(config)
    evidence_root = Path(config.get("evidence_root", ""))
    if not validation.valid:
        if evidence_root:
            _write_evidence_record(evidence_root, "errors", "08_rejection_or_error_record.json", config, {
                "error_code": "CONFIG_SCHEMA_INVALID",
                "errors": validation.errors,
                "blocking_reason": "fail_closed_before_actionable_subscription",
                "scope_boundary_preserved": True,
            })
        raise ValueError("; ".join(validation.errors))

    evidence_root.mkdir(parents=True, exist_ok=True)
    adapter = adapter or build_nats_adapter(config)
    listener = build_listener_runtime(config, adapter, identity_yaml_path=identity_yaml_path)
    supervisor = ListenerSupervisor(listener, SupervisorConfig())

    _write_evidence_record(evidence_root, "startup", "00_runtime_identity.json", config, {
        "config_path": str(path),
        "config_hash": validation.config_hash,
        "role": config["role"],
    })
    _write_evidence_record(evidence_root, "startup", "01_config_validation.json", config, {
        "validation_status": "accepted",
        "errors": [],
        "trusted_subject_prefixes": config["trusted_subject_prefixes"],
        "supported_message_types": config["supported_message_types"],
        "ack_is_not_business_completion": True,
    })
    _write_evidence_record(evidence_root, "startup", "02_subscription_binding.json", config, {
        "consumer_durable_name": config["consumer"]["durable_name"],
        "filter_subjects": list(config["consumer"]["filter_subjects"]),
        "adapter_filter_subject": _adapter_filter_subject(config),
        "stream_name": config["broker"]["stream_name"],
        "inbox_bound": config["subjects"]["inbox"] in config["consumer"]["filter_subjects"],
        "callback_bound": config["subjects"]["callback"] in config["consumer"]["filter_subjects"],
    })
    return AgentRuntimeBootstrapResult(
        config=config,
        validation=validation,
        adapter=adapter,
        listener=listener,
        supervisor=supervisor,
        evidence_root=evidence_root,
    )


def build_nats_adapter(config: dict[str, Any]) -> MqAdapterNats:
    broker = config["broker"]
    return MqAdapterNats(
        nats_url=broker["nats_url"],
        stream_name=broker["stream_name"],
        dlq_stream_name=broker["dlq_stream_name"],
        stream_subjects=broker["stream_subjects"],
        consumer_name=config["consumer"]["durable_name"],
        consumer_filter_subject=_adapter_filter_subject(config),
    )


def build_listener_runtime(
    config: dict[str, Any],
    adapter: Any,
    *,
    identity_yaml_path: str | Path | None = None,
) -> ListenerRuntime:
    root = Path(__file__).resolve().parents[2]
    identity_path = identity_yaml_path or root / "config" / "agents_uat.yaml"
    db_path = Path(config["evidence_root"]) / f"{config['agent_id']}-runtime.sqlite3"
    return ListenerRuntime.from_paths(
        adapter=adapter,
        runtime_id=config["runtime_instance_id"],
        agent_id=config["agent_id"],
        role=config["role"],
        db_path=db_path,
        identity_yaml_path=identity_path,
        config=ListenerRuntimeConfig(),
    )


def process_controlled_uat_once(bootstrap: AgentRuntimeBootstrapResult) -> dict[str, Any]:
    message = bootstrap.adapter.consume()
    if message is None:
        return {"status": "idle"}
    envelope = message.get("envelope") if isinstance(message, dict) else None
    subject = message.get("subject", "") if isinstance(message, dict) else ""
    config = bootstrap.config
    errors = _validate_inbound_message(config, subject, envelope)
    if errors:
        _write_evidence_record(bootstrap.evidence_root, "errors", "08_rejection_or_error_record.json", config, {
            "error_code": errors[0],
            "errors": errors,
            "subject": subject,
            "message_id": envelope.get("message_id") if isinstance(envelope, dict) else None,
            "blocking_reason": "fail_closed_controlled_uat_dispatch",
            "scope_boundary_preserved": True,
        }, envelope)
        return {"status": "rejected", "errors": errors}

    message_type = envelope["message_type"]
    handler_name = config["handler_mapping"][message_type]
    runtime = bootstrap.listener.runtime
    runtime.state_store.record_envelope_inbox(
        envelope_id=envelope["message_id"],
        subject=subject,
        payload=envelope,
        normalized_execution_envelope=envelope,
        message_id=envelope["message_id"],
        workflow_instance_id=envelope["workflow_instance_id"],
        causation_id=envelope.get("causation_id"),
        correlation_id=envelope.get("correlation_id"),
        source_agent_id=envelope.get("source_agent_id"),
        target_agent_id=envelope.get("target_agent_id"),
    )
    if message_type == "Command_Message":
        runtime.state_store.create_pending_task(
            task_id=f"task-{envelope['message_id']}",
            task_type="controlled_uat_handoff",
            subject=subject,
            correlation_id=envelope["correlation_id"],
            workflow_id=envelope["workflow_instance_id"],
            payload=envelope,
            reply_to_subject=envelope.get("reply_to_subject"),
            created_by=config["runtime_instance_id"],
        )
    ack = bootstrap.adapter.ack(envelope["message_id"])
    _write_evidence_record(bootstrap.evidence_root, "intake", "03_durable_intake_record.json", config, {
        "subject": subject,
        "durable_record_ref": f"envelope_inbox:{envelope['message_id']}",
    }, envelope)
    _write_evidence_record(bootstrap.evidence_root, "intake", "04_ack_evidence.json", config, {
        "ack_level": ack.get("ack_level"),
        "consumer_name": config["consumer"]["durable_name"],
        "ack": ack,
        "not_business_completion": True,
    }, envelope)
    _write_evidence_record(bootstrap.evidence_root, "dispatch", "05_handler_dispatch_record.json", config, {
        "handler_name": handler_name,
        "capability": handler_name,
        "authorization_result": "accepted",
        "message_type": message_type,
        "handler_success_is_not_business_completion": True,
    }, envelope)

    if message_type == "Command_Message":
        return_envelope = controlled_uat_handoff_receive(envelope, config)
        selected_subject = select_return_subject(envelope, config)
        _write_evidence_record(bootstrap.evidence_root, "returns", "06_return_path_decision.json", config, {
            "reply_to_subject": envelope.get("reply_to_subject"),
            "configured_callback_subject": config["subjects"]["callback"],
            "selected_return_subject": selected_subject,
            "decision_recorded_before_success": True,
        }, envelope)
        return_envelope["reply_to_subject"] = selected_subject
        publish_ack = bootstrap.adapter.publish(return_envelope)
        _write_evidence_record(bootstrap.evidence_root, "returns", "07_return_publish_record.json", config, {
            "return_message_id": return_envelope["message_id"],
            "publish_ack": publish_ack,
            "publish_ack_is_not_business_completion": True,
        }, return_envelope)
        return {"status": "command_dispatched", "return_message": return_envelope}

    controlled_uat_return_receive(envelope, config)
    return {"status": "business_return_received", "message_id": envelope["message_id"]}


def controlled_uat_handoff_receive(envelope: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    return build_execution_envelope(
        message_type="Business_Message",
        workflow_instance_id=envelope["workflow_instance_id"],
        workflow_type=CONTROLLED_WORKFLOW_TYPE,
        workflow_version=envelope["workflow_version"],
        producer=config["agent_id"],
        payload={
            "business_event_type": "controlled_uat_return",
            "transition_id": f"return-{envelope['message_id']}",
            "previous_state": "handoff_received",
            "new_state": "return_prepared",
            "validation_result": "accepted",
            "evidence_refs": [f"dispatch/05_handler_dispatch_record.json"],
        },
        correlation_id=envelope["correlation_id"],
        causation_id=envelope["message_id"],
        idempotency_key=f"controlled-return:{envelope['message_id']}",
        source_agent_id=config["agent_id"],
        source_runtime_instance_id=config["runtime_instance_id"],
        source_role=config["role"],
        authority_scope="workflow.result",
        target_agent_id=envelope.get("source_agent_id"),
        reply_to_subject=select_return_subject(envelope, config),
    ).to_dict()


def controlled_uat_return_receive(envelope: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    return {
        "handler_name": "controlled_uat_return_receive",
        "message_id": envelope["message_id"],
        "agent_id": config["agent_id"],
        "not_business_completion": True,
    }


def select_return_subject(envelope: dict[str, Any], config: dict[str, Any]) -> str:
    reply_to = envelope.get("reply_to_subject")
    if reply_to and _is_approved_subject(reply_to):
        return reply_to
    return config["subjects"]["callback"]


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="WBS 15.6 minimal controlled-UAT agent runtime bootstrap")
    parser.add_argument("--config", required=True)
    parser.add_argument("--startup-only", action="store_true")
    args = parser.parse_args(argv)
    bootstrap = bootstrap_from_config(args.config)
    startup = bootstrap.supervisor.startup()
    return 0 if startup.config_valid and not startup.quarantined else 2


def _validate_inbound_message(config: dict[str, Any], subject: str, envelope: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(envelope, dict):
        return ["MALFORMED_ENVELOPE"]
    if subject not in config["consumer"]["filter_subjects"]:
        errors.append(f"UNAPPROVED_SUBJECT: {subject}")
    contract = validate_execution_message(envelope, require_runtime_overlay=True)
    errors.extend(contract.errors)
    if envelope.get("message_type") not in config["supported_message_types"]:
        errors.append(f"UNSUPPORTED_MESSAGE_TYPE: {envelope.get('message_type')}")
    if envelope.get("message_type") not in config["handler_mapping"]:
        errors.append(f"HANDLER_MAPPING_MISSING: {envelope.get('message_type')}")
    elif config["handler_mapping"][envelope.get("message_type")] not in config["capabilities"]:
        errors.append(f"UNAUTHORIZED_CAPABILITY: {config['handler_mapping'][envelope.get('message_type')]}")
    if envelope.get("authority_scope") not in config["authority_scopes"]:
        errors.append(f"UNAUTHORIZED_AUTHORITY_SCOPE: {envelope.get('authority_scope')}")
    target = envelope.get("target_agent_id")
    if target and target != config["agent_id"]:
        errors.append(f"TARGET_AGENT_MISMATCH: {target}")
    return errors


def _write_evidence_record(
    evidence_root: Path,
    category: str,
    filename: str,
    config: dict[str, Any],
    payload: dict[str, Any],
    envelope: Optional[dict[str, Any]] = None,
) -> Path:
    path = evidence_root / category / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "uat_id": "uat-3.5-full-link-2026-05-16-001",
        "agent_id": config.get("agent_id"),
        "runtime_instance_id": config.get("runtime_instance_id"),
        "message_id": envelope.get("message_id") if envelope else payload.get("message_id"),
        "correlation_id": envelope.get("correlation_id") if envelope else payload.get("correlation_id"),
        "causation_id": envelope.get("causation_id") if envelope else payload.get("causation_id"),
        "captured_at": now_iso(),
        "captured_by": config.get("agent_id", "system"),
        "environment": config.get("environment"),
        "evidence_schema_version": "1.0",
        "not_business_completion": True,
        **payload,
    }
    path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _adapter_filter_subject(config: dict[str, Any]) -> str:
    return f"{APPROVED_PREFIX}{config['agent_id']}.>"


def _section(config: dict[str, Any], key: str, errors: list[str]) -> dict[str, Any]:
    value = config.get(key)
    if not isinstance(value, dict):
        errors.append(f"CONFIG_SCHEMA_INVALID: {key} must be a mapping")
        return {}
    return value


def _require_broker(broker: dict[str, Any], errors: list[str]) -> None:
    for key in ("nats_url", "stream_name", "dlq_stream_name", "stream_subjects"):
        if not broker.get(key):
            errors.append(f"MISSING_REQUIRED_CONFIG_FIELD: broker.{key}")
    if not isinstance(broker.get("stream_subjects", []), list):
        errors.append("CONFIG_SCHEMA_INVALID: broker.stream_subjects must be a list")


def _require_consumer(config: dict[str, Any], consumer: dict[str, Any], errors: list[str]) -> None:
    agent_id = config.get("agent_id")
    expected = f"nexus-3_5-uat-{agent_id}"
    if consumer.get("durable_name") != expected:
        errors.append(f"UNAPPROVED_DURABLE_CONSUMER: {consumer.get('durable_name')}")
    _require_list_in_section(consumer, "filter_subjects", "consumer", errors)


def _require_subjects(config: dict[str, Any], subjects: dict[str, Any], errors: list[str]) -> None:
    agent_id = config.get("agent_id")
    expected = {
        "inbox": f"{APPROVED_PREFIX}{agent_id}.inbox",
        "callback": f"{APPROVED_PREFIX}{agent_id}.callback",
    }
    for key, value in expected.items():
        if subjects.get(key) != value:
            errors.append(f"UNAPPROVED_SUBJECT: subjects.{key}={subjects.get(key)}")


def _require_handler_mapping(config: dict[str, Any], errors: list[str]) -> None:
    mapping = config.get("handler_mapping")
    if not isinstance(mapping, dict):
        errors.append("CONFIG_SCHEMA_INVALID: handler_mapping must be a mapping")
        return
    if mapping != APPROVED_HANDLER_MAPPING:
        errors.append(f"UNAPPROVED_HANDLER_MAPPING: {mapping}")
    capabilities = set(config.get("capabilities", []))
    for handler_name in mapping.values():
        if handler_name not in capabilities:
            errors.append(f"UNAUTHORIZED_CAPABILITY: {handler_name}")


def _require_list(config: dict[str, Any], key: str, errors: list[str]) -> None:
    if not isinstance(config.get(key), list) or not config.get(key):
        errors.append(f"CONFIG_SCHEMA_INVALID: {key} must be a non-empty list")


def _require_list_in_section(section: dict[str, Any], key: str, section_name: str, errors: list[str]) -> None:
    if not isinstance(section.get(key), list) or not section.get(key):
        errors.append(f"CONFIG_SCHEMA_INVALID: {section_name}.{key} must be a non-empty list")


def _is_approved_subject(subject: Any) -> bool:
    return isinstance(subject, str) and subject.startswith(APPROVED_PREFIX)


def _without_runtime_fields(config: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in config.items() if not key.startswith("_")}


if __name__ == "__main__":
    raise SystemExit(main())
