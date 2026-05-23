from nexus.mq.durable_state import DurableStateStore
from nexus.mq.structured_task_persistence import (
    list_structured_task_records,
    write_structured_task_record,
)


def test_replay_same_source_policy_hash_is_idempotent(tmp_path):
    store = DurableStateStore(tmp_path / "state.sqlite")

    first = write_structured_task_record(
        store,
        family="structured_task.audit",
        status="opened",
        payload={"run_id": "run-001"},
        workflow_instance_id="run-001",
        dedupe_key="run-001:sha256:source:sha256:policy",
    )
    second = write_structured_task_record(
        store,
        family="structured_task.audit",
        status="opened",
        payload={"run_id": "run-001"},
        workflow_instance_id="run-001",
        dedupe_key="run-001:sha256:source:sha256:policy",
    )

    assert first.record_id == second.record_id
    assert len(list_structured_task_records(store, family="structured_task.audit")) == 1


def test_superseded_plan_preserves_prior_record(tmp_path):
    store = DurableStateStore(tmp_path / "state.sqlite")

    old = write_structured_task_record(
        store,
        family="structured_task.plan",
        status="validated",
        payload={"plan_id": "plan-001"},
        workflow_instance_id="run-001",
        dedupe_key="plan-001:v1",
    )
    new = write_structured_task_record(
        store,
        family="structured_task.plan",
        status="superseded",
        payload={"plan_id": "plan-002", "supersedes": old.record_id},
        workflow_instance_id="run-001",
        dedupe_key="plan-002:v2",
    )

    records = list_structured_task_records(store, family="structured_task.plan")

    assert len(records) == 2
    assert old.record_id != new.record_id
    assert new.payload["supersedes"] == old.record_id
