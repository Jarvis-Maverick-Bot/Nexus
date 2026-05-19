"""Separate contract-only registry boundary for WBS 7.12.

This registry stores private-agent contract truth only. It deliberately does not
write WBS 7.8 trusted runtime records or adapter presence.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from nexus.mq.private_agent_contract import (
    PRIVATE_AGENT_CONTRACT_SCHEMA_VERSION,
    PrivateAgentContract,
    validate_private_agent_contract,
)


PRIVATE_CONTRACT_STORE_SCHEMA_VERSION = "4.19.private_contract_registry.v1"


@dataclass(frozen=True)
class StoredPrivateContractRecord:
    contract: PrivateAgentContract
    revision: int
    normalized: dict[str, Any]


@dataclass(frozen=True)
class PrivateContractWriteResult:
    accepted: bool
    contract: Optional[PrivateAgentContract] = None
    revision: Optional[int] = None
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PrivateContractReadResult:
    accepted: bool
    contract: Optional[PrivateAgentContract] = None
    revision: Optional[int] = None
    errors: list[str] = field(default_factory=list)
    row_quarantined: bool = False


@dataclass
class PrivateContractLoadResult:
    records: list[StoredPrivateContractRecord] = field(default_factory=list)
    rejected_contracts: dict[str, list[str]] = field(default_factory=dict)
    store_errors: list[str] = field(default_factory=list)
    store_fail_closed: bool = False

    @property
    def accepted(self) -> bool:
        return not self.store_fail_closed


class PrivateContractRegistryStore(Protocol):
    @property
    def authoritative(self) -> bool:
        ...

    def upsert_contract(
        self,
        contract: PrivateAgentContract,
        *,
        expected_revision: Optional[int] = None,
        now_at: Optional[str] = None,
    ) -> PrivateContractWriteResult:
        ...

    def get_contract(self, contract_id: str, *, now_at: Optional[str] = None) -> PrivateContractReadResult:
        ...

    def load_contracts(self, *, now_at: Optional[str] = None) -> PrivateContractLoadResult:
        ...

    def record_anomaly(
        self,
        contract_id: str,
        *,
        anomaly_ref: str,
        severity: str = "severe",
        expected_revision: Optional[int] = None,
        now_at: Optional[str] = None,
    ) -> PrivateContractWriteResult:
        ...


class FakePrivateContractRegistryStore:
    """Deterministic local store for private contract tests."""

    def __init__(self, *, authoritative: bool = True):
        self._authoritative = authoritative
        self._rows: dict[str, dict[str, Any]] = {}
        self._store_corrupted = False

    @property
    def authoritative(self) -> bool:
        return self._authoritative

    def upsert_contract(
        self,
        contract: PrivateAgentContract,
        *,
        expected_revision: Optional[int] = None,
        now_at: Optional[str] = None,
    ) -> PrivateContractWriteResult:
        preflight_errors = self._store_preflight_errors()
        if preflight_errors:
            return PrivateContractWriteResult(accepted=False, errors=preflight_errors)

        validation = validate_private_agent_contract(contract, now_at=now_at)
        if not validation.valid:
            return PrivateContractWriteResult(accepted=False, errors=validation.errors)

        existing = self._rows.get(contract.contract_id)
        if existing is not None:
            read = self._row_to_contract(existing, now_at=now_at)
            if not read.accepted or read.contract is None:
                return PrivateContractWriteResult(
                    accepted=False,
                    revision=read.revision,
                    errors=read.errors,
                )
            current_revision = existing["revision"]
            if expected_revision is not None and expected_revision != current_revision:
                return PrivateContractWriteResult(
                    accepted=False,
                    revision=current_revision,
                    errors=["PRIVATE_CONTRACT_STALE_REVISION"],
                )
            new_revision = current_revision + 1
        else:
            if expected_revision not in (None, 0):
                return PrivateContractWriteResult(
                    accepted=False,
                    errors=["PRIVATE_CONTRACT_STALE_REVISION"],
                )
            new_revision = 1

        self._rows[contract.contract_id] = contract_to_normalized_row(contract, revision=new_revision)
        return PrivateContractWriteResult(
            accepted=True,
            contract=contract,
            revision=new_revision,
        )

    def get_contract(self, contract_id: str, *, now_at: Optional[str] = None) -> PrivateContractReadResult:
        preflight_errors = self._store_preflight_errors()
        if preflight_errors:
            return PrivateContractReadResult(accepted=False, errors=preflight_errors)
        row = self._rows.get(contract_id)
        if row is None:
            return PrivateContractReadResult(accepted=False, errors=["PRIVATE_CONTRACT_MISSING"])
        return self._row_to_contract(row, now_at=now_at)

    def load_contracts(self, *, now_at: Optional[str] = None) -> PrivateContractLoadResult:
        preflight_errors = self._store_preflight_errors()
        if preflight_errors:
            return PrivateContractLoadResult(store_errors=preflight_errors, store_fail_closed=True)

        result = PrivateContractLoadResult()
        for contract_id, row in sorted(self._rows.items()):
            read = self._row_to_contract(row, now_at=now_at)
            if not read.accepted or read.contract is None or read.revision is None:
                result.rejected_contracts[contract_id] = read.errors
                continue
            result.records.append(
                StoredPrivateContractRecord(
                    contract=read.contract,
                    revision=read.revision,
                    normalized=normalized_columns(row),
                )
            )
        return result

    def record_anomaly(
        self,
        contract_id: str,
        *,
        anomaly_ref: str,
        severity: str = "severe",
        expected_revision: Optional[int] = None,
        now_at: Optional[str] = None,
    ) -> PrivateContractWriteResult:
        read = self.get_contract(contract_id, now_at=now_at)
        if not read.accepted or read.contract is None:
            return PrivateContractWriteResult(accepted=False, revision=read.revision, errors=read.errors)
        if expected_revision is not None and expected_revision != read.revision:
            return PrivateContractWriteResult(
                accepted=False,
                revision=read.revision,
                errors=["PRIVATE_CONTRACT_STALE_REVISION"],
            )
        updated = _replace_contract(
            read.contract,
            blocking_anomaly_refs=[*read.contract.blocking_anomaly_refs, anomaly_ref],
            contract_status="suspended" if severity == "severe" else read.contract.contract_status,
        )
        revision = (read.revision or 0) + 1
        self._rows[contract_id] = contract_to_normalized_row(updated, revision=revision, quarantined=severity == "severe")
        return PrivateContractWriteResult(accepted=True, contract=updated, revision=revision)

    def normalized_row(self, contract_id: str) -> Optional[dict[str, Any]]:
        row = self._rows.get(contract_id)
        return deepcopy(row) if row is not None else None

    def seed_raw_row(self, row: dict[str, Any]) -> None:
        contract_id = row.get("contract_id")
        if not contract_id:
            raise ValueError("seed row requires contract_id")
        self._rows[str(contract_id)] = deepcopy(row)

    def corrupt_store_for_test(self) -> None:
        self._store_corrupted = True

    def _store_preflight_errors(self) -> list[str]:
        errors: list[str] = []
        if self._store_corrupted:
            errors.append("PRIVATE_CONTRACT_STORE_CORRUPTED")
        if not self._authoritative:
            errors.append("PRIVATE_CONTRACT_TRUTH_UNVERIFIED")
        return errors

    def _row_to_contract(self, row: dict[str, Any], *, now_at: Optional[str]) -> PrivateContractReadResult:
        row_errors = _validate_row_shape(row)
        if row_errors:
            return PrivateContractReadResult(accepted=False, errors=row_errors, row_quarantined=True)
        try:
            payload = deepcopy(row["payload"]["contract"])
            payload["allowed_invocations"] = [
                _allowed_invocation_from_dict(item) for item in payload.get("allowed_invocations", [])
            ]
            contract = PrivateAgentContract(**payload)
        except (KeyError, TypeError, ValueError) as exc:
            return PrivateContractReadResult(
                accepted=False,
                errors=[f"MALFORMED_PRIVATE_CONTRACT_ROW: {exc.__class__.__name__}"],
                row_quarantined=True,
            )
        validation = validate_private_agent_contract(contract, now_at=now_at)
        normalized_errors = _validate_normalized_matches_contract(row, contract)
        errors = validation.errors + normalized_errors
        if errors:
            return PrivateContractReadResult(
                accepted=False,
                contract=contract,
                revision=row.get("revision"),
                errors=_dedupe(errors),
                row_quarantined=True,
            )
        return PrivateContractReadResult(
            accepted=True,
            contract=contract,
            revision=row["revision"],
            row_quarantined=bool(row.get("quarantined", False)),
        )


def contract_to_normalized_row(
    contract: PrivateAgentContract,
    *,
    revision: int,
    quarantined: bool = False,
) -> dict[str, Any]:
    return {
        "schema_version": PRIVATE_CONTRACT_STORE_SCHEMA_VERSION,
        "store_revision": 1,
        "contract_id": contract.contract_id,
        "contract_revision": contract.contract_revision,
        "contract_status": contract.contract_status,
        "trust_class": contract.trust_class,
        "adapter_agent_id": contract.adapter_agent_id,
        "adapter_runtime_instance_id": contract.adapter_runtime_instance_id,
        "expires_at": contract.expires_at,
        "diagnostic_only_until": contract.diagnostic_only_until,
        "revision": revision,
        "payload_schema_version": PRIVATE_AGENT_CONTRACT_SCHEMA_VERSION,
        "payload": {
            "schema_version": PRIVATE_AGENT_CONTRACT_SCHEMA_VERSION,
            "contract": contract.to_dict(),
            "not_business_completion": True,
        },
        "quarantined": quarantined,
    }


def normalized_columns(row: dict[str, Any]) -> dict[str, Any]:
    keys = {
        "schema_version",
        "store_revision",
        "contract_id",
        "contract_revision",
        "contract_status",
        "trust_class",
        "adapter_agent_id",
        "adapter_runtime_instance_id",
        "expires_at",
        "diagnostic_only_until",
        "revision",
        "payload_schema_version",
        "quarantined",
    }
    return {key: deepcopy(row.get(key)) for key in sorted(keys)}


def _validate_row_shape(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for column in [
        "schema_version",
        "store_revision",
        "contract_id",
        "contract_revision",
        "contract_status",
        "revision",
        "payload_schema_version",
        "payload",
    ]:
        if column not in row:
            errors.append(f"MALFORMED_PRIVATE_CONTRACT_ROW: missing {column}")
    if row.get("schema_version") != PRIVATE_CONTRACT_STORE_SCHEMA_VERSION:
        errors.append(f"UNSUPPORTED_PRIVATE_CONTRACT_STORE_SCHEMA: {row.get('schema_version')}")
    if row.get("payload_schema_version") != PRIVATE_AGENT_CONTRACT_SCHEMA_VERSION:
        errors.append(f"UNSUPPORTED_PRIVATE_CONTRACT_PAYLOAD_SCHEMA: {row.get('payload_schema_version')}")
    if not isinstance(row.get("revision"), int) or row.get("revision", 0) <= 0:
        errors.append("MALFORMED_PRIVATE_CONTRACT_ROW: invalid revision")
    payload = row.get("payload")
    if not isinstance(payload, dict):
        errors.append("MALFORMED_PRIVATE_CONTRACT_ROW: payload not object")
    elif payload.get("schema_version") != PRIVATE_AGENT_CONTRACT_SCHEMA_VERSION:
        errors.append(f"UNSUPPORTED_PRIVATE_CONTRACT_PAYLOAD_SCHEMA: {payload.get('schema_version')}")
    return _dedupe(errors)


def _validate_normalized_matches_contract(row: dict[str, Any], contract: PrivateAgentContract) -> list[str]:
    errors: list[str] = []
    for key in [
        "contract_id",
        "contract_revision",
        "contract_status",
        "trust_class",
        "adapter_agent_id",
        "adapter_runtime_instance_id",
        "expires_at",
        "diagnostic_only_until",
    ]:
        if row.get(key) != getattr(contract, key):
            errors.append(f"PRIVATE_CONTRACT_NORMALIZED_PAYLOAD_MISMATCH: {key}")
    return errors


def _allowed_invocation_from_dict(value: Any):
    from nexus.mq.private_agent_contract import AllowedPrivateInvocation

    if isinstance(value, AllowedPrivateInvocation):
        return value
    if not isinstance(value, dict):
        raise TypeError("allowed invocation must be object")
    return AllowedPrivateInvocation(**value)


def _replace_contract(contract: PrivateAgentContract, **updates: Any) -> PrivateAgentContract:
    payload = contract.to_dict()
    payload.update(updates)
    payload["allowed_invocations"] = [
        _allowed_invocation_from_dict(item) for item in payload.get("allowed_invocations", [])
    ]
    return PrivateAgentContract(**payload)


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error not in deduped:
            deduped.append(error)
    return deduped
