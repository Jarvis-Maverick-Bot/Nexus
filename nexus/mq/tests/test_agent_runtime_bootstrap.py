"""Focused tests for WBS 15.6 minimal controlled-UAT agent runtime bootstrap."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from nexus.mq.adapter import MqAdapterStub
from nexus.mq.agent_runtime import (
    CONTROLLED_WORKFLOW_TYPE,
    bootstrap_from_config,
    build_nats_adapter,
    load_agent_runtime_config,
    main,
    process_controlled_uat_once,
    select_return_subject,
    validate_agent_runtime_config,
)
from nexus.mq.message_contracts import build_execution_envelope


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _config_path(agent_id: str) -> Path:
    return _repo_root() / "config" / "agents" / f"{agent_id}.yaml"


def _identity_config_path() -> Path:
    return _repo_root() / "config" / "agents_uat.yaml"


def _load_config(agent_id: str, tmp_path: Path) -> dict:
    config = load_agent_runtime_config(_config_path(agent_id))
    config["evidence_root"] = str(tmp_path / "evidence" / agent_id)
    config["_config_path"] = str(_config_path(agent_id))
    return config


def _write_config(tmp_path: Path, config: dict) -> Path:
    config_path = tmp_path / f"{config['agent_id']}.yaml"
    serializable = {key: value for key, value in config.items() if not key.startswith("_")}
    config_path.write_text(yaml.safe_dump(serializable, sort_keys=False), encoding="utf-8")
    return config_path


def _bootstrap(agent_id: str, tmp_path: Path, adapter: MqAdapterStub | None = None):
    config = _load_config(agent_id, tmp_path)
    return bootstrap_from_config(
        _write_config(tmp_path, config),
        adapter=adapter or MqAdapterStub(),
        identity_yaml_path=_identity_config_path(),
    )


def _command_to_jarvis(reply_to_subject: str | None = "nexus.3_5.uat.nova.callback") -> dict:
    return build_execution_envelope(
        message_type="Command_Message",
        workflow_instance_id="wf-uat-001",
        workflow_type=CONTROLLED_WORKFLOW_TYPE,
        workflow_version="1.0",
        producer="nova",
        payload={
            "command_name": "controlled_uat_handoff",
            "target_handler": "controlled_uat_handoff_receive",
            "completion_event_type": "controlled_uat_return",
        },
        idempotency_key="idem-uat-command-001",
        correlation_id="corr-uat-001",
        causation_id=None,
        source_agent_id="nova",
        source_runtime_instance_id="nova-uat-runtime-001",
        source_role="nova",
        authority_scope="workflow.command",
        target_agent_id="jarvis",
        reply_to_subject=reply_to_subject,
    ).to_dict()


def _business_to_nova(command: dict) -> dict:
    return build_execution_envelope(
        message_type="Business_Message",
        workflow_instance_id=command["workflow_instance_id"],
        workflow_type=CONTROLLED_WORKFLOW_TYPE,
        workflow_version=command["workflow_version"],
        producer="jarvis",
        payload={
            "business_event_type": "controlled_uat_return",
            "transition_id": "transition-uat-001",
            "previous_state": "return_prepared",
            "new_state": "nova_received",
            "validation_result": "accepted",
        },
        idempotency_key="idem-uat-business-001",
        correlation_id=command["correlation_id"],
        causation_id=command["message_id"],
        source_agent_id="jarvis",
        source_runtime_instance_id="jarvis-uat-runtime-001",
        source_role="jarvis",
        authority_scope="workflow.result",
        target_agent_id="nova",
        reply_to_subject="nexus.3_5.uat.nova.callback",
    ).to_dict()


def test_agent_runtime_requires_explicit_config_path():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_agent_runtime_rejects_unknown_agent_id(tmp_path):
    config = _load_config("nova", tmp_path)
    config["agent_id"] = "viper"
    result = validate_agent_runtime_config(config)
    assert not result.valid
    assert any(error.startswith("UNAPPROVED_AGENT_ID") for error in result.errors)


def test_agent_runtime_rejects_untrusted_subject_prefix(tmp_path):
    config = _load_config("jarvis", tmp_path)
    config["trusted_subject_prefixes"] = ["agent.jarvis."]
    result = validate_agent_runtime_config(config)
    assert not result.valid
    assert "UNAPPROVED_TRUSTED_SUBJECT_PREFIX: agent.jarvis." in result.errors


def test_agent_runtime_rejects_unauthorized_capability(tmp_path):
    config = _load_config("jarvis", tmp_path)
    config["capabilities"] = ["controlled_uat_return_receive"]
    result = validate_agent_runtime_config(config)
    assert not result.valid
    assert "UNAUTHORIZED_CAPABILITY: controlled_uat_handoff_receive" in result.errors


def test_agent_runtime_rejects_unsafe_return_path_policy(tmp_path):
    config = _load_config("nova", tmp_path)
    config["return_path_policy"] = "publish_anywhere"
    result = validate_agent_runtime_config(config)
    assert not result.valid
    assert "UNSAFE_RETURN_PATH_POLICY: publish_anywhere" in result.errors


def test_agent_runtime_requires_evidence_root(tmp_path):
    config = _load_config("nova", tmp_path)
    config["evidence_root"] = ""
    result = validate_agent_runtime_config(config)
    assert not result.valid
    assert "MISSING_REQUIRED_CONFIG_FIELD: evidence_root" in result.errors


def test_agent_runtime_preserves_ack_intake_only_contract(tmp_path):
    config = _load_config("jarvis", tmp_path)
    assert config["ack_policy"] == "consumer_intake_only_after_durable_intake"
    result = validate_agent_runtime_config(config)
    assert result.valid


def test_nova_listener_startup_smoke_from_config(tmp_path):
    bootstrap = _bootstrap("nova", tmp_path)
    startup = bootstrap.supervisor.startup()
    identity = bootstrap.evidence_root / "startup" / "00_runtime_identity.json"
    binding = bootstrap.evidence_root / "startup" / "02_subscription_binding.json"
    bootstrap.listener.close()

    assert startup.runtime_status == "ACTIVE"
    assert identity.exists()
    assert binding.exists()
    assert "nexus-3_5-uat-nova" in binding.read_text(encoding="utf-8")


def test_jarvis_listener_startup_smoke_from_config(tmp_path):
    bootstrap = _bootstrap("jarvis", tmp_path)
    startup = bootstrap.supervisor.startup()
    binding = bootstrap.evidence_root / "startup" / "02_subscription_binding.json"
    bootstrap.listener.close()

    assert startup.runtime_status == "ACTIVE"
    assert binding.exists()
    assert "nexus.3_5.uat.jarvis.inbox" in binding.read_text(encoding="utf-8")
    assert "nexus.3_5.uat.jarvis.callback" in binding.read_text(encoding="utf-8")
    assert "nexus.3_5.uat.jarvis.>" in binding.read_text(encoding="utf-8")


def test_controlled_uat_nova_to_jarvis_handoff(tmp_path):
    adapter = MqAdapterStub()
    bootstrap = _bootstrap("jarvis", tmp_path, adapter)
    command = _command_to_jarvis()
    publish_ack = adapter.publish(command)

    result = process_controlled_uat_once(bootstrap)
    intake = bootstrap.listener.runtime.state_store.get_envelope_inbox(command["message_id"])
    dispatch = bootstrap.evidence_root / "dispatch" / "05_handler_dispatch_record.json"
    bootstrap.listener.close()

    assert publish_ack["message_id"] == command["message_id"]
    assert adapter.replay()[0]["subject"] == "nexus.3_5.uat.jarvis.inbox"
    assert result["status"] == "command_dispatched"
    assert intake is not None
    assert dispatch.exists()


def test_controlled_uat_jarvis_to_nova_return_via_reply_to(tmp_path):
    adapter = MqAdapterStub()
    bootstrap = _bootstrap("jarvis", tmp_path, adapter)
    command = _command_to_jarvis(reply_to_subject="nexus.3_5.uat.nova.callback")
    adapter.publish(command)

    result = process_controlled_uat_once(bootstrap)
    decision = bootstrap.evidence_root / "returns" / "06_return_path_decision.json"
    bootstrap.listener.close()

    assert result["return_message"]["reply_to_subject"] == "nexus.3_5.uat.nova.callback"
    assert "nexus.3_5.uat.nova.callback" in decision.read_text(encoding="utf-8")
    assert adapter.replay()[-1]["subject"] == "nexus.3_5.uat.nova.callback"


def test_controlled_uat_jarvis_to_nova_return_via_callback_fallback(tmp_path):
    config = _load_config("jarvis", tmp_path)
    envelope = _command_to_jarvis(reply_to_subject="agent.nova.callbacks")
    assert select_return_subject(envelope, config) == "nexus.3_5.uat.jarvis.callback"


def test_controlled_uat_ack_and_durable_intake_evidence(tmp_path):
    adapter = MqAdapterStub()
    bootstrap = _bootstrap("jarvis", tmp_path, adapter)
    command = _command_to_jarvis()
    adapter.publish(command)

    process_controlled_uat_once(bootstrap)
    ack_evidence = bootstrap.evidence_root / "intake" / "04_ack_evidence.json"
    intake_evidence = bootstrap.evidence_root / "intake" / "03_durable_intake_record.json"
    bootstrap.listener.close()

    assert ack_evidence.exists()
    assert intake_evidence.exists()
    assert "consumer_intake" in ack_evidence.read_text(encoding="utf-8")
    assert "not_business_completion" in ack_evidence.read_text(encoding="utf-8")


def test_controlled_uat_unauthorized_capability_rejection(tmp_path):
    adapter = MqAdapterStub()
    bootstrap = _bootstrap("jarvis", tmp_path, adapter)
    command = _command_to_jarvis()
    command["payload"] = deepcopy(command["payload"])
    command["authority_scope"] = "workflow.admin"
    adapter.publish(command)

    result = process_controlled_uat_once(bootstrap)
    error_record = bootstrap.evidence_root / "errors" / "08_rejection_or_error_record.json"
    bootstrap.listener.close()

    assert result["status"] == "rejected"
    assert error_record.exists()
    assert "UNAUTHORIZED_AUTHORITY_SCOPE" in error_record.read_text(encoding="utf-8")


def test_build_nats_adapter_uses_single_wildcard_filter_for_both_fixed_paths(tmp_path):
    config = _load_config("nova", tmp_path)
    adapter = build_nats_adapter(config)
    assert adapter._consumer_name == "nexus-3_5-uat-nova"
    assert adapter._consumer_filter_subject == "nexus.3_5.uat.nova.>"
    assert "nexus.3_5.uat.nova.inbox" in adapter._stream_subjects
    assert "nexus.3_5.uat.nova.callback" in adapter._stream_subjects


def test_controlled_uat_nova_receives_business_return(tmp_path):
    adapter = MqAdapterStub()
    bootstrap = _bootstrap("nova", tmp_path, adapter)
    command = _command_to_jarvis()
    business = _business_to_nova(command)
    adapter.publish(business)

    result = process_controlled_uat_once(bootstrap)
    dispatch = bootstrap.evidence_root / "dispatch" / "05_handler_dispatch_record.json"
    bootstrap.listener.close()

    assert result["status"] == "business_return_received"
    assert adapter.replay()[0]["subject"] == "nexus.3_5.uat.nova.callback"
    assert dispatch.exists()
