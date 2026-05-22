from nexus.mq.agent_access_read_model import build_agent_access_read_model
from nexus.mq.candidate_runtime_identity import build_candidate_registry_record
from nexus.mq.candidate_runtime_projection import build_candidate_runtime_projection
from nexus.mq.tests.test_candidate_runtime_capacity import _capacity
from nexus.mq.tests.test_candidate_runtime_identity import NOW, _identity, _profile


def _record(**identity_overrides):
    return build_candidate_registry_record(
        profile=_profile(),
        identity=_identity(**identity_overrides),
        now_at=NOW,
    )


def test_candidate_runtime_projection_is_read_only_and_redacted():
    projection = build_candidate_runtime_projection(
        record=_record(),
        capacity=_capacity(),
        evidence_refs=["token=should-redact"],
    )

    assert projection["projection_type"] == "candidate_runtime"
    assert projection["runtime_provider"] == "openclaw"
    assert projection["capacity_revision"] == 1
    assert projection["read_only"] is True
    assert projection["not_business_completion"] is True
    assert projection["evidence_refs"] == ["[REDACTED]"]
    assert "credential_ref" not in projection


def test_agent_access_read_model_includes_candidate_runtime_projection():
    record = _record()
    projection = build_candidate_runtime_projection(record=record, capacity=_capacity())

    model = build_agent_access_read_model(
        agents=[record],
        assignments=[],
        outbox_items=[],
        adapter_health=[],
        exceptions=[],
        evidence=[],
        candidate_runtime_projection=[projection],
    )

    assert model.read_only is True
    assert model.candidate_runtimes[0]["runtime_instance_id"] == "jarvis-runtime-001"
    assert model.candidate_runtimes[0]["not_business_completion"] is True
