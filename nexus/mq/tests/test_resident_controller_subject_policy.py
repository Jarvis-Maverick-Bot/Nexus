from nexus.mq.resident_controller.dispatcher import (
    ResidentControllerSubjectPolicy,
    validate_publish_subject,
)


def _policy():
    return ResidentControllerSubjectPolicy(
        namespace="nexus.4_19.wbs7_19_14",
        run_id="run-001",
        allowed_agents=["jarvis"],
        publish_allowlist=[
            "nexus.4_19.wbs7_19_14.*.controller.init",
            "nexus.4_19.wbs7_19_14.*.assignment",
            "nexus.4_19.wbs7_19_14.*.assignment.duplicate_replay",
            "nexus.4_19.wbs7_19_14.*.drain",
        ],
    )


def test_resident_controller_subject_policy_rejects_publish_wildcard():
    result = validate_publish_subject("nexus.4_19.wbs7_19_14.run-001.*.assignment", _policy())

    assert result.accepted is False
    assert "PUBLISH_SUBJECT_CANNOT_CONTAIN_WILDCARD" in result.errors


def test_resident_controller_subject_policy_requires_run_id():
    result = validate_publish_subject("nexus.4_19.wbs7_19_14.other-run.jarvis.assignment", _policy())

    assert result.accepted is False
    assert "PUBLISH_SUBJECT_RUN_ID_MISMATCH" in result.errors


def test_resident_controller_subject_policy_accepts_canonical_assignment_subject_without_runtime_id():
    result = validate_publish_subject("nexus.4_19.wbs7_19_14.run-001.jarvis.assignment", _policy())

    assert result.accepted is True
    assert result.errors == []


def test_resident_controller_subject_policy_accepts_candidate_pinned_assignment_allowlist():
    policy = ResidentControllerSubjectPolicy(
        namespace="nexus.4_19.wbs7_19_15",
        run_id="run-7152",
        allowed_agents=["jarvis"],
        publish_allowlist=["nexus.4_19.wbs7_19_15.*.jarvis.assignment"],
    )

    result = validate_publish_subject("nexus.4_19.wbs7_19_15.run-7152.jarvis.assignment", policy)

    assert result.accepted is True
    assert result.errors == []


def test_resident_controller_subject_policy_rejects_runtime_scoped_assignment_alias():
    result = validate_publish_subject("nexus.4_19.wbs7_19_14.run-001.jarvis.jarvis-runtime-001.assignment", _policy())

    assert result.accepted is False
    assert "PUBLISH_SUBJECT_NOT_ALLOWLISTED" in result.errors


def test_resident_controller_subject_policy_rejects_extra_segments():
    result = validate_publish_subject("nexus.4_19.wbs7_19_14.run-001.jarvis.extra.assignment", _policy())

    assert result.accepted is False
    assert "PUBLISH_SUBJECT_NOT_ALLOWLISTED" in result.errors
