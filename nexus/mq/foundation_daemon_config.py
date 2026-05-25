"""Source-only configuration gates for the Layer 3 MQ foundation daemon."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import hashlib
import json

import yaml

from nexus.mq.agent_registry_events import secret_material_errors


FOUNDATION_DAEMON_SCHEMA_VERSION = "3.5.foundation-daemon.v1"


@dataclass
class FoundationDaemonConfigValidation:
    valid: bool
    fail_closed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    config_hash: str = ""
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "fail_closed": self.fail_closed,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "config_hash": self.config_hash,
            "not_business_completion": self.not_business_completion,
        }


def load_foundation_daemon_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    text = config_path.read_text(encoding="utf-8")
    if config_path.suffix.lower() in {".yaml", ".yml"}:
        loaded = yaml.safe_load(text) or {}
    elif config_path.suffix.lower() == ".json":
        loaded = json.loads(text)
    else:
        raise ValueError(f"UNSUPPORTED_CONFIG_FORMAT: {config_path.suffix}")
    if not isinstance(loaded, dict):
        raise ValueError("CONFIG_ROOT_MUST_BE_OBJECT")
    return loaded


def validate_foundation_daemon_config(config: dict[str, Any]) -> FoundationDaemonConfigValidation:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(config, dict):
        errors.append("CONFIG_ROOT_MUST_BE_OBJECT")
        return _validation(errors, warnings, {})

    if config.get("manifest_version") != FOUNDATION_DAEMON_SCHEMA_VERSION:
        errors.append(f"UNSUPPORTED_MANIFEST_VERSION: {config.get('manifest_version')}")
    if config.get("environment") not in {"local", "staging", "source_only"}:
        errors.append(f"INVALID_ENVIRONMENT: {config.get('environment')}")

    daemon = _section(config, "daemon", errors)
    broker = _section(config, "broker", errors)
    subjects = _section(config, "subjects", errors)
    retry = _section(config, "retry", errors)
    timeout = _section(config, "timeout", errors)
    stores = _section(config, "stores", errors)
    feature_flags = _section(config, "feature_flags", errors)

    if daemon:
        _require(daemon, "runtime_instance_id", "daemon", errors)
        _require(daemon, "service_name", "daemon", errors)
        if daemon.get("default_enabled") is not False:
            errors.append("DEFAULT_ENABLED_NOT_ALLOWED_IN_SOURCE_PACKAGE")
        if daemon.get("rollout_phase") not in {"source_only", "dry_run", "disabled"}:
            errors.append(f"INVALID_ROLLOUT_PHASE: {daemon.get('rollout_phase')}")

    if broker:
        _require_list(broker, "urls", "broker", errors)
        _require(broker, "stream", "broker", errors)
        _require(broker, "consumer", "broker", errors)
        _require(broker, "filter_subject", "broker", errors)
        _require(broker, "dlq_subject", "broker", errors)

    allowlist = []
    if subjects:
        allowlist = subjects.get("allowlist") or []
        if not isinstance(allowlist, list) or not allowlist:
            errors.append("MISSING_REQUIRED_FIELD: subjects.allowlist")
        elif broker:
            for field_name in ("filter_subject", "dlq_subject"):
                value = broker.get(field_name)
                if value and not subject_allowed(str(value), allowlist):
                    errors.append(f"SUBJECT_NOT_ALLOWED: broker.{field_name}")

    if retry:
        max_attempts = retry.get("max_attempts")
        if not isinstance(max_attempts, int) or max_attempts <= 0:
            errors.append("INVALID_RETRY_MAX_ATTEMPTS")
    if timeout:
        for field_name in ("endpoint_first_response_seconds", "endpoint_completion_seconds"):
            value = timeout.get(field_name)
            if not isinstance(value, int) or value <= 0:
                errors.append(f"INVALID_TIMEOUT_SECONDS: {field_name}")

    if stores:
        _validate_store(stores, "durable_state", errors)
        _validate_store(stores, "evidence", errors)

    if feature_flags:
        if feature_flags.get("live_publish_enabled") is not False:
            errors.append("LIVE_PUBLISH_NOT_AUTHORIZED_FOR_SOURCE_GATE")
        if feature_flags.get("business_dispatch_enabled") is not False:
            errors.append("BUSINESS_DISPATCH_OUT_OF_SCOPE")
        if feature_flags.get("broker_setup_enabled") is not False:
            errors.append("BROKER_SETUP_MUTATION_OUT_OF_SCOPE")

    errors.extend(secret_material_errors(config, path="config"))
    return _validation(errors, warnings, config)


def redact_config(config: dict[str, Any]) -> dict[str, Any]:
    redacted = json.loads(json.dumps(config, sort_keys=True))
    broker = redacted.get("broker")
    if isinstance(broker, dict):
        broker["urls"] = [_redact_url(str(url)) for url in broker.get("urls", [])]
    stores = redacted.get("stores")
    if isinstance(stores, dict):
        for store in stores.values():
            if isinstance(store, dict) and "dsn" in store:
                store["dsn"] = _redact_url(str(store["dsn"]))
    secret_refs = redacted.get("secret_refs")
    if isinstance(secret_refs, dict):
        redacted["secret_refs"] = {key: "ref-present" if value else "" for key, value in secret_refs.items()}
    return redacted


def config_hash(config: dict[str, Any]) -> str:
    payload = json.dumps(redact_config(config), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def subject_allowed(subject: str, allowlist: list[str]) -> bool:
    return any(_subject_pattern_matches(subject, str(pattern)) for pattern in allowlist)


def _subject_pattern_matches(subject: str, pattern: str) -> bool:
    subject_parts = subject.split(".")
    pattern_parts = pattern.split(".")
    for index, pattern_part in enumerate(pattern_parts):
        if pattern_part == ">":
            return index == len(pattern_parts) - 1 and len(subject_parts) >= index
        if index >= len(subject_parts):
            return False
        if pattern_part != "*" and pattern_part != subject_parts[index]:
            return False
    return len(subject_parts) == len(pattern_parts)


def _validation(
    errors: list[str],
    warnings: list[str],
    config: dict[str, Any],
) -> FoundationDaemonConfigValidation:
    return FoundationDaemonConfigValidation(
        valid=not errors,
        fail_closed=bool(errors),
        errors=list(dict.fromkeys(errors)),
        warnings=warnings,
        config_hash=config_hash(config) if isinstance(config, dict) else "",
    )


def _section(config: dict[str, Any], name: str, errors: list[str]) -> dict[str, Any]:
    value = config.get(name)
    if not isinstance(value, dict):
        errors.append(f"MISSING_REQUIRED_SECTION: {name}")
        return {}
    return value


def _require(section: dict[str, Any], field_name: str, section_name: str, errors: list[str]) -> None:
    if section.get(field_name) in (None, ""):
        errors.append(f"MISSING_REQUIRED_FIELD: {section_name}.{field_name}")


def _require_list(section: dict[str, Any], field_name: str, section_name: str, errors: list[str]) -> None:
    value = section.get(field_name)
    if not isinstance(value, list) or not value:
        errors.append(f"MISSING_REQUIRED_FIELD: {section_name}.{field_name}")


def _validate_store(stores: dict[str, Any], name: str, errors: list[str]) -> None:
    store = stores.get(name)
    if not isinstance(store, dict):
        errors.append(f"MISSING_REQUIRED_SECTION: stores.{name}")
        return
    _require(store, "dsn", f"stores.{name}", errors)
    _require_list(store, "required_families", f"stores.{name}", errors)


def _redact_url(value: str) -> str:
    if "://" not in value or "@" not in value:
        return value
    scheme, rest = value.split("://", 1)
    host = rest.split("@", 1)[1]
    return f"{scheme}://***@{host}"
