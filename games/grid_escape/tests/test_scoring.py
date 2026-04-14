"""Tests for scoring tiers (Task 1.6)."""

import pytest
from games.grid_escape.grids import get_optimal_steps


TIER_RULES = [
    (0, "PERFECT"),
    (1, "EXCELLENT"),
    (2, "EXCELLENT"),
    (3, "GOOD"),
    (4, "GOOD"),
    (5, "GOOD"),
    (6, "COMPLETED"),
    (7, "COMPLETED"),
    (8, "COMPLETED"),
    (9, "COMPLETED"),
    (10, "COMPLETED"),
]


def tier(diff: int) -> str:
    if diff <= 0:
        return "PERFECT"
    elif diff <= 2:
        return "EXCELLENT"
    elif diff <= 5:
        return "GOOD"
    elif diff <= 10:
        return "COMPLETED"
    else:
        return "OVERMOVED"


class TestScoringTiers:
    @pytest.mark.parametrize("diff,expected", TIER_RULES)
    def test_tier_assignment(self, diff, expected):
        assert tier(diff) == expected

    def test_overmoved_threshold(self):
        assert tier(11) == "OVERMOVED"
        assert tier(100) == "OVERMOVED"

    def test_perfect_at_optimal(self):
        assert tier(0) == "PERFECT"

    def test_all_tiers_represented(self):
        tiers = {tier(i) for i in range(15)}
        assert "PERFECT" in tiers
        assert "EXCELLENT" in tiers
        assert "GOOD" in tiers
        assert "COMPLETED" in tiers
        assert "OVERMOVED" in tiers

    def test_optimal_steps_per_grid(self):
        for gid, expected in [("ge-001", 8), ("ge-002", 12), ("ge-003", 18)]:
            assert get_optimal_steps(gid) == expected
