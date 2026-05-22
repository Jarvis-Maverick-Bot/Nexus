from nexus.mq.candidate_runtime_controller import CandidateControllerPolicy, evaluate_candidate_controller_preflight
from nexus.mq.candidate_runtime_identity import CandidateAgentProfile, validate_candidate_agent_profile


def test_candidate_runtime_no_go_blocks_business_dispatch_by_default():
    profile = CandidateAgentProfile(
        agent_id="jarvis",
        candidate_profile_ref="candidate-profile://implementation",
        role="implementation",
        capabilities=["implementation"],
        authority_scopes=["workflow.command"],
        privacy_scopes=["project"],
        allowed_task_boundaries=["implementation"],
        no_go_scope=["no business execution"],
        business_dispatch_allowed=True,
    )

    result = validate_candidate_agent_profile(profile)

    assert result.valid is False
    assert "BUSINESS_DISPATCH_NOT_AUTHORIZED" in result.errors


def test_candidate_runtime_controller_disabled_is_fail_closed():
    decision = evaluate_candidate_controller_preflight(
        record=None,
        policy=CandidateControllerPolicy(controller_enabled=False),
        now_at="2026-05-22T00:00:00+00:00",
    )

    assert decision.accepted is False
    assert decision.errors == ["CANDIDATE_CONTROLLER_DISABLED"]
    assert decision.not_business_completion is True
