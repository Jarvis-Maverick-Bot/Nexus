from nexus.mq.candidate_runtime_controller import (
    CandidateControllerPolicy,
    evaluate_candidate_assignment,
    evaluate_candidate_controller_preflight,
)
from nexus.mq.candidate_runtime_identity import build_candidate_registry_record
from nexus.mq.dispatch_request import DispatchRequest
from nexus.mq.tests.test_candidate_runtime_capacity import _capacity
from nexus.mq.tests.test_candidate_runtime_identity import NOW, _identity, _profile


EVAL_NOW = "2026-05-22T00:00:30+00:00"


def _record():
    return build_candidate_registry_record(profile=_profile(), identity=_identity(), now_at=NOW)


def _request():
    return DispatchRequest(
        request_id="candidate-request-001",
        correlation_id="candidate-correlation-001",
        work_ref="work://candidate/001",
        required_capability="implementation",
        required_authority_scope="workflow.command",
        required_privacy_scope="project",
        allowed_task_boundary="implementation",
        no_go_scope=["no business execution"],
    )


def test_candidate_controller_preflight_fails_closed_on_emergency_stop():
    decision = evaluate_candidate_controller_preflight(
        record=_record(),
        policy=CandidateControllerPolicy(emergency_stop=True),
        now_at=EVAL_NOW,
    )

    assert decision.accepted is False
    assert decision.errors == ["CANDIDATE_CONTROLLER_EMERGENCY_STOP"]


def test_candidate_controller_builds_inert_scheduler_claim():
    decision = evaluate_candidate_assignment(
        request=_request(),
        record=_record(),
        registry_revision_seen=1,
        capacity_snapshot=_capacity(),
        policy=CandidateControllerPolicy(),
        now_at=EVAL_NOW,
    )

    assert decision.accepted is True
    assert decision.scheduler_decision.claim.business_execution_allowed is False
    assert decision.not_business_completion is True
