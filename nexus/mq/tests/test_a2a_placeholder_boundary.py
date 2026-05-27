from nexus.mq.a2a_placeholder_marker import A2A_PLACEHOLDER_STATUS, reject_a2a_route_request


def test_v0_1_rejects_a2a_route_request_without_state_mutation():
    state = {"route_count": 0, "assignments": []}
    original = dict(state)

    result = reject_a2a_route_request(
        {
            "source_agent_id": "jarvis",
            "target_agent_id": "thunder",
            "assignment_id": "assignment-001",
        },
        state=state,
    )

    assert result.accepted is False
    assert result.status == A2A_PLACEHOLDER_STATUS
    assert "A2A_DEFERRED_TO_V0_2" in result.errors
    assert state == original
