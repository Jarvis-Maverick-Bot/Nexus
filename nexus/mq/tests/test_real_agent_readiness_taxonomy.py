from nexus.mq.readiness_taxonomy import RealAgentEvidenceStatus, classify_real_agent_readiness


def test_phase3_minitest_evidence_is_diagnostic_only():
    result = classify_real_agent_readiness(
        RealAgentEvidenceStatus(
            integrated_package_complete=False,
            phase3_minitest_only=True,
            diagnostic_only=True,
            source_evidence_refs=["evidence://phase3/minitest"],
        )
    )

    assert result.ready_label_allowed is False
    assert result.diagnostic_only is True
    assert result.status == "DIAGNOSTIC_ONLY"
    assert "PHASE3_MINITEST_DIAGNOSTIC_ONLY" in result.errors
    assert result.final_readiness_claimed is False


def test_partial_package_cannot_mark_real_operating_ready():
    result = classify_real_agent_readiness(
        RealAgentEvidenceStatus(
            integrated_package_complete=False,
            phase3_minitest_only=False,
            diagnostic_only=False,
            source_evidence_refs=["evidence://adapter-only"],
        )
    )

    assert result.ready_label_allowed is False
    assert result.status == "BLOCKED_INCOMPLETE_PACKAGE"
    assert "INTEGRATED_EVIDENCE_PACKAGE_INCOMPLETE" in result.errors


def test_integrated_package_can_only_be_review_ready_candidate():
    result = classify_real_agent_readiness(
        RealAgentEvidenceStatus(
            integrated_package_complete=True,
            phase3_minitest_only=False,
            diagnostic_only=False,
            source_evidence_refs=["evidence://integrated/package"],
        )
    )

    assert result.ready_label_allowed is True
    assert result.status == "READY_FOR_NOVA_REVIEW"
    assert result.final_readiness_claimed is False
    assert result.forbidden_final_label == "THUNDER_REAL_AGENT_OPERATING_ENVIRONMENT_READY"
