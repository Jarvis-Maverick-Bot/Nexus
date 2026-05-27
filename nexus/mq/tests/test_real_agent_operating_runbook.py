from pathlib import Path


RUNBOOK = Path("docs/runbooks/4.19_REAL_AGENT_OPERATING_ENVIRONMENT_RUNBOOK.md")


def test_runbook_evidence_completeness_for_roles():
    text = RUNBOOK.read_text(encoding="utf-8")

    for role in [
        "Alex",
        "Nova",
        "Jarvis runtime host",
        "Thunder",
        "Operator",
        "Evidence reviewer",
    ]:
        assert role in text

    for phrase in [
        "CODING_AUTHORIZED_WITH_NOTES",
        "READY_FOR_NOVA_REVIEW",
        "BLOCKED",
        "not authorized",
        "final readiness claim",
    ]:
        assert phrase in text


def test_runbook_contains_distributed_uat_broker_preflight_and_env_contract():
    text = RUNBOOK.read_text(encoding="utf-8")

    for phrase in [
        "nats://192.168.31.124:7422",
        "NATS_URL",
        "NEXUS_RESIDENT_CONTROLLER_NATS_URL",
        "never OpenClaw 4222",
        "never Jarvis-side 127.0.0.1",
        "firewall",
        "auth",
        "preflight",
    ]:
        assert phrase in text


def test_runbook_forbids_chat_only_pass_claims():
    text = RUNBOOK.read_text(encoding="utf-8")

    assert "THUNDER_REAL_AGENT_OPERATING_ENVIRONMENT_READY" in text
    assert "must not be claimed from chat-only evidence" in text
    assert "MiniTest diagnostic only" in text
