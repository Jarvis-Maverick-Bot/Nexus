from nexus.mq.agent_access_read_model import build_agent_access_read_model, export_agent_access_evidence
from nexus.mq.operational_observability import build_agent_access_evidence_ref


def test_agent_access_evidence_export_is_qa_readable_and_read_only():
    evidence_ref = build_agent_access_evidence_ref(
        source_doc="4.19-refreshed-implementation-design",
        source_record="agent_registry:jarvis",
        evidence_ref="evidence://agent-access/jarvis-readiness",
        checksum_ref="sha256:test",
    )
    model = build_agent_access_read_model(
        agents=[],
        assignments=[],
        outbox_items=[],
        adapter_health=[],
        exceptions=[],
        evidence=[evidence_ref],
    )

    exported = export_agent_access_evidence(model)

    assert exported["read_only"] is True
    assert exported["not_business_completion"] is True
    assert exported["evidence"][0]["source_doc"] == "4.19-refreshed-implementation-design"
    assert exported["evidence"][0]["checksum_ref"] == "sha256:test"
