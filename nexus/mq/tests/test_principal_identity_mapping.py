from nexus.mq.identity import PrincipalIdentityMappingRecord, validate_principal_identity_mapping


def test_principal_identity_mapping_accepts_verified_scope():
    result = validate_principal_identity_mapping(
        PrincipalIdentityMappingRecord(
            mapping_id="map-001",
            channel_type="telegram",
            actor_channel_identity_ref="telegram:user:alex",
            resolved_principal_id="principal:alex",
            permission_scope_ref="project:nexus",
            mapping_state="resolved",
            source_authority_ref="authority://local/identity",
            last_verified_at="2026-05-18T00:00:00+00:00",
            evidence_refs=["evidence://identity/map-001"],
        ),
        required_permission_scope_ref="project:nexus",
    )

    assert result.valid is True
    assert result.resolved_principal_id == "principal:alex"
    assert result.evidence_refs == ["evidence://identity/map-001"]


def test_principal_identity_blocks_unknown_suspended_and_wrong_scope():
    unknown = validate_principal_identity_mapping(
        PrincipalIdentityMappingRecord(
            mapping_id="map-unknown",
            channel_type="discord",
            actor_channel_identity_ref="discord:user:anon",
            resolved_principal_id=None,
            permission_scope_ref="project:nexus",
            mapping_state="unknown",
            source_authority_ref=None,
            last_verified_at=None,
        ),
        required_permission_scope_ref="project:nexus",
    )
    suspended = validate_principal_identity_mapping(
        PrincipalIdentityMappingRecord(
            mapping_id="map-suspended",
            channel_type="feishu",
            actor_channel_identity_ref="feishu:user:suspended",
            resolved_principal_id="principal:suspended",
            permission_scope_ref="team:other",
            mapping_state="suspended",
            source_authority_ref="authority://local/identity",
            last_verified_at="2026-05-18T00:00:00+00:00",
        ),
        required_permission_scope_ref="project:nexus",
    )

    assert "UNKNOWN_IDENTITY" in unknown.errors
    assert "MISSING_SOURCE_AUTHORITY" in unknown.errors
    assert "SUSPENDED_PRINCIPAL" in suspended.errors
    assert "WRONG_SCOPE" in suspended.errors
