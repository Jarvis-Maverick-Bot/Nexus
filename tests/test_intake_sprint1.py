"""
Sprint 1 Phase 1: Intake Foundation — Quick Verification Test
"""
import sys
sys.path.insert(0, "D:/Projects/gov_langgraph")

from gov_langgraph.platform_model.objects import Project, ProjectStatus

print("=" * 60)
print("Sprint 1 Phase 1 — Intake Foundation Tests")
print("=" * 60)

# Test 1: Partial intake fields → not complete
p1 = Project(
    project_name="Test Project",
    project_goal="Test goal",
    domain_type="internal",
    project_owner="alex",
    intake_summary="Test summary",
    # missing deliverable and business_context
)
print("\nTest 1 — Partial fields (summary only):")
print(f"  validate_intake: {p1.validate_intake()} (expected: False)")
print(f"  intake_complete: {p1.intake_complete} (expected: False)")
assert not p1.validate_intake(), "FAIL: partial fields should not validate"
assert not p1.intake_complete, "FAIL: intake_complete should be False for partial"
print("  PASS")

# Test 2: All required intake fields → validate passes
p2 = Project(
    project_name="Test Project 2",
    project_goal="Test goal",
    domain_type="internal",
    project_owner="alex",
    intake_summary="Test summary",
    intake_deliverable="Test deliverable",
    intake_business_context="Test context",
)
print("\nTest 2 — All required fields present:")
print(f"  validate_intake: {p2.validate_intake()} (expected: True)")
assert p2.validate_intake(), "FAIL: all fields should validate"
print("  PASS")

# Test 3: complete_intake marks intake complete when all fields present
print("\nTest 3 — complete_intake when all fields present:")
print(f"  intake_complete before: {p2.intake_complete} (expected: False)")
p2.complete_intake()
print(f"  intake_complete after: {p2.intake_complete} (expected: True)")
assert p2.intake_complete, "FAIL: intake_complete should be True after complete_intake"
print("  PASS")

# Test 4: complete_intake raises error if missing fields
p3 = Project(
    project_name="Test Project 3",
    project_goal="Test goal",
    domain_type="internal",
    project_owner="alex",
    intake_summary="",
    intake_deliverable="",
    intake_business_context="",
)
print("\nTest 4 — complete_intake raises error for empty fields:")
try:
    p3.complete_intake()
    print("  FAIL: should have raised ValueError")
    assert False
except ValueError as e:
    print(f"  Raised ValueError: {e}")
    print("  PASS")

# Test 5: Serialization — all new fields present on Project
print("\nTest 5 — New fields present on Project dataclass:")
for field_name in ["intake_complete", "intake_summary", "intake_deliverable", "intake_business_context", "output_package"]:
    has_field = field_name in p2.__dataclass_fields__
    status = "OK" if has_field else "MISSING"
    print(f"  {field_name}: {status}")
    assert has_field, f"FAIL: {field_name} not in Project dataclass"
print("  PASS")

# Test 6: V1.5 legacy project (no intake fields) → not complete
p_legacy = Project(
    project_name="Legacy Project",
    project_goal="Legacy goal",
    domain_type="internal",
    project_owner="alex",
)
print("\nTest 6 — V1.5 legacy project (no intake fields):")
print(f"  intake_complete: {p_legacy.intake_complete} (expected: False)")
print(f"  validate_intake: {p_legacy.validate_intake()} (expected: False)")
assert not p_legacy.intake_complete, "FAIL: legacy project should not have intake_complete"
assert not p_legacy.validate_intake(), "FAIL: legacy project should not validate"
print("  PASS")

print("\n" + "=" * 60)
print("ALL TESTS PASSED ✓")
print("=" * 60)
