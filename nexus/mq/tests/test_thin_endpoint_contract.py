from nexus.mq.thin_endpoint_contract import validate_thin_endpoint_contract


def _contract(**overrides):
    data = {
        "endpoint_id": "jarvis-thin-endpoint",
        "runtime_instance_id": "jarvis-runtime-001",
        "allowed_operations": ["receive", "local_ack", "return_result_candidate"],
        "correlation_id": "corr-001",
        "idempotency_key": "idem-001",
        "evidence_refs": ["evidence://endpoint/result"],
        "result_candidate": {"status": "candidate"},
        "not_business_completion": True,
    }
    data.update(overrides)
    return data


def test_thin_endpoint_contract_accepts_candidate_boundary():
    result = validate_thin_endpoint_contract(_contract())

    assert result.valid is True
    assert result.not_business_completion is True


def test_thin_endpoint_rejects_retry_dlq_and_replay_ownership():
    result = validate_thin_endpoint_contract(
        _contract(
            retry_policy={"max_attempts": 3},
            dlq_subject="nexus.3_5.mq.dlq",
            replay_decision="replay_all",
        )
    )

    assert result.valid is False
    assert "ENDPOINT_MUST_NOT_OWN_RETRY_POLICY" in result.errors
    assert "ENDPOINT_MUST_NOT_OWN_DLQ_POLICY" in result.errors
    assert "ENDPOINT_MUST_NOT_OWN_REPLAY_DECISION" in result.errors


def test_thin_endpoint_rejects_correlation_rewrite_and_business_completion():
    result = validate_thin_endpoint_contract(
        _contract(
            original_correlation_id="corr-001",
            returned_correlation_id="corr-rewritten",
            business_completion=True,
            not_business_completion=False,
        )
    )

    assert result.valid is False
    assert "ENDPOINT_MUST_PRESERVE_CORRELATION_ID" in result.errors
    assert "ENDPOINT_CANNOT_CLAIM_BUSINESS_COMPLETION" in result.errors
    assert "NOT_BUSINESS_COMPLETION_REQUIRED" in result.errors


def test_thin_endpoint_rejects_secret_material():
    result = validate_thin_endpoint_contract(_contract(metadata={"token": "abc"}))

    assert result.valid is False
    assert any(error.startswith("SECRET_MATERIAL_FIELD: endpoint.metadata.token") for error in result.errors)
