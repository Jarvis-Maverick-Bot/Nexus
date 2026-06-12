FIRST_SLICE_NO_GO_FIXTURES = {
    "direct_ui_approval": {
        "action": "direct_ui_approval",
        "expected_error": "ERR_NO_GO_BOUNDARY",
    },
    "raw_feedback_mutation": {
        "action": "raw_feedback_authority_mutation",
        "expected_error": "ERR_RAW_FEEDBACK_NO_AUTHORITY_MUTATION",
        "required_terms": ["FeedbackMetricExtraction", "FeedbackMetricTrend"],
    },
    "ack_as_acceptance": {
        "action": "ack_as_acceptance",
        "expected_error": "ERR_ACK_NOT_ACCEPTANCE",
        "required_terms": ["DispatchDecision"],
    },
    "missing_evaluation_profile": {
        "action": "accept_without_evaluation_profile",
        "expected_error": "ERR_MISSING_EVALUATION_PROFILE",
    },
    "lower_layer_runtime_control": {
        "action": "lower_layer_runtime_control",
        "expected_error": "ERR_NO_GO_BOUNDARY",
    },
}
