"""Tests for ESCAPED message tier field (Task 1.7).

TASK-001: ESCAPED format must include tier as the 5th field (6th pipe-delimited slot).
TASK-002: compute_tier must be wired into the escape path.
"""

import pytest
from games.grid_escape.engine import Game, State


# ge-001: optimal=8 steps, path below takes exactly 8 steps → diff=0 → PERFECT
_PATH_GE001_ESCAPE = [
    "east", "south", "east", "south", "south", "east", "south", "east",
]


class TestEscapedTierField:
    """ESCAPED message must include tier as the 5th pipe-delimited field."""

    def test_escaped_message_has_tier_field(self):
        """ESCAPED message should contain a non-empty tier in the 5th field.

        Current format:  ESCAPED|<steps>|<grid>|<ts>
        Expected format: ESCAPED|<steps>|<grid>|<ts>|<tier>

        The tier string must be one of: PERFECT, EXCELLENT, GOOD, COMPLETED, OVERMOVED.
        """
        g = Game.new("ge-001")
        g.restart()

        for move in _PATH_GE001_ESCAPE:
            result = g.move(move)

        assert result.startswith("ESCAPED|"), f"Expected ESCAPED, got: {result}"

        parts = result.split("|")
        # Format: ESCAPED|<steps>|<grid>|<ts>|<tier>  →  5 parts
        assert len(parts) == 5, (
            f"ESCAPED message should have 5 pipe-delimited fields "
            f"(got {len(parts)}): {result}"
        )

        tier = parts[4]
        assert tier in ("PERFECT", "EXCELLENT", "GOOD", "COMPLETED", "OVERMOVED"), (
            f"5th field should be a valid tier string, got: {tier}"
        )
        assert tier != "", "Tier field must not be empty"

    def test_escaped_tier_is_perfect_for_optimal_path(self):
        """ge-001 optimal is 8 steps; taking exactly 8 steps yields PERFECT."""
        g = Game.new("ge-001")
        g.restart()

        for move in _PATH_GE001_ESCAPE:
            g.move(move)

        parts = g.move("north").split("|")  # Should be GAME OVER, not ESCAPED again
        # Actually just re-check the last ESCAPED result
        g2 = Game.new("ge-001")
        g2.restart()
        for move in _PATH_GE001_ESCAPE:
            g2.move(move)

        result = g2.move("east")  # Valid move before ESCAPED check
        # No - we already escaped, let me just re-check the escape result
        g3 = Game.new("ge-001")
        g3.restart()
        for move in _PATH_GE001_ESCAPE:
            g3.move(move)

        # Reconstruct by checking state
        assert g3.state == State.ESCAPED

        # Verify tier is PERFECT (8 steps, optimal=8, diff=0)
        from games.grid_escape.scoring import compute_tier
        expected_tier = compute_tier("ge-001", 8)
        assert expected_tier == "PERFECT"

        # And that the ESCAPED message contains it
        # We need to re-exercise the escape path to get the message
        g4 = Game.new("ge-001")
        g4.restart()
        escaped_msg = None
        for move in _PATH_GE001_ESCAPE:
            r = g4.move(move)
            if r.startswith("ESCAPED|"):
                escaped_msg = r
                break

        assert escaped_msg is not None
        tier_in_msg = escaped_msg.split("|")[4]
        assert tier_in_msg == "PERFECT", (
            f"ge-001 with 8 steps (optimal) should yield PERFECT tier, "
            f"got: {tier_in_msg}"
        )
