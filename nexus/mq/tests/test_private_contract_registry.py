from copy import deepcopy

from nexus.mq.agent_registry_service import AgentRegistryService
from nexus.mq.agent_registry_store import FakeAgentRegistryStore
from nexus.mq.private_contract_registry import FakePrivateContractRegistryStore
from nexus.mq.tests.test_private_agent_contract import NOW, _contract


def test_contract_registry_does_not_create_trusted_runtime_record():
    private_store = FakePrivateContractRegistryStore()
    runtime_store = FakeAgentRegistryStore()
    runtime_service = AgentRegistryService(runtime_store)

    write = private_store.upsert_contract(_contract(), now_at=NOW)
    runtime_read = runtime_service.read_registry_record("private-adapter", now_at=NOW)

    assert write.accepted is True
    assert private_store.get_contract("contract-private-diagnostic", now_at=NOW).accepted is True
    assert runtime_read.accepted is False
    assert runtime_read.errors == ["REGISTRY_RECORD_NOT_FOUND"]


def test_contract_registry_rejects_cache_only_truth():
    authoritative = FakePrivateContractRegistryStore()
    assert authoritative.upsert_contract(_contract(), now_at=NOW).accepted is True
    cache_only = FakePrivateContractRegistryStore(authoritative=False)
    cache_only.seed_raw_row(authoritative.normalized_row("contract-private-diagnostic"))

    read = cache_only.get_contract("contract-private-diagnostic", now_at=NOW)

    assert read.accepted is False
    assert read.errors == ["PRIVATE_CONTRACT_TRUTH_UNVERIFIED"]


def test_contract_registry_malformed_row_quarantines_that_contract():
    store = FakePrivateContractRegistryStore()
    assert store.upsert_contract(_contract(), now_at=NOW).accepted is True
    malformed = deepcopy(store.normalized_row("contract-private-diagnostic"))
    malformed["contract_id"] = "contract-malformed"
    malformed["payload"]["contract"]["contract_id"] = "contract-malformed"
    malformed.pop("payload_schema_version")
    store.seed_raw_row(malformed)

    load = store.load_contracts(now_at=NOW)

    assert load.accepted is True
    assert [item.contract.contract_id for item in load.records] == ["contract-private-diagnostic"]
    assert "MALFORMED_PRIVATE_CONTRACT_ROW: missing payload_schema_version" in load.rejected_contracts[
        "contract-malformed"
    ]


def test_private_anomaly_suspends_contract_eligibility_record():
    store = FakePrivateContractRegistryStore()
    write = store.upsert_contract(_contract(), now_at=NOW)
    assert write.accepted is True

    anomaly = store.record_anomaly(
        "contract-private-diagnostic",
        anomaly_ref="evidence://private-agent/anomaly/privacy",
        severity="severe",
        expected_revision=write.revision,
        now_at=NOW,
    )

    assert anomaly.accepted is True
    assert anomaly.contract.contract_status == "suspended"
    assert anomaly.contract.blocking_anomaly_refs == ["evidence://private-agent/anomaly/privacy"]
