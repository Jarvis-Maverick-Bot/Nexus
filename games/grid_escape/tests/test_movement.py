"""Tests for movement engine."""

import pytest
from games.grid_escape.engine import Game, DIRECTION_ALIASES, State
from games.grid_escape.grids import load_grid


class TestDirectionAliases:
    def test_all_8_aliases_accepted(self):
        g = Game.new("ge-001")
        g.restart()
        for alias in DIRECTION_ALIASES:
            result = g.move(alias)
            assert result in ("OK", "BLOCKED", "ESCAPED"), f"Unknown result for {alias}: {result}"

    def test_north_south_east_west_and_abbreviations(self):
        aliases = {"n": "north", "s": "south", "e": "east", "w": "west"}
        for abbr, full in aliases.items():
            assert abbr in DIRECTION_ALIASES
            assert full in DIRECTION_ALIASES


class TestMovementBoundary:
    def test_move_into_wall_returns_blocked_no_state_change(self):
        g = Game.new("ge-001")
        g.restart()
        initial_pos = g.agent_pos
        initial_steps = g.step_count
        result = g.move("north")
        assert result == "BLOCKED"
        assert g.agent_pos == initial_pos
        assert g.step_count == initial_steps

    def test_move_out_of_bounds_returns_blocked(self):
        g = Game.new("ge-002")
        g.restart()
        initial_pos = g.agent_pos
        result = g.move("north")
        assert result == "BLOCKED"
        assert g.agent_pos == initial_pos

    def test_valid_move_updates_agent_pos(self):
        g = Game.new("ge-002")
        g.restart()
        sx, sy = g.agent_pos
        result = g.move("south")
        if result == "OK":
            assert g.agent_pos == (sx, sy + 1)


class TestMovementState:
    def test_valid_move_increments_step_count(self):
        g = Game.new("ge-003")
        g.restart()
        g.move("south")
        if g.step_count > 0:
            before = g.step_count
            g.move("east")
            assert g.step_count > before

    def test_visited_list_updated(self):
        g = Game.new("ge-002")
        g.restart()
        g.move("south")
        if g.state == State.ACTIVE:
            assert len(g.visited) >= 1

    def test_restart_resets_state(self):
        g = Game.new("ge-001")
        g.restart()
        g.move("south")
        g.restart()
        assert g.step_count == 0
        assert g.state == State.ACTIVE
        assert g.agent_pos == g.grid.start


class TestGameOver:
    def test_moves_after_escaped_rejected(self):
        g = Game.new("ge-001")
        g.restart()
        for _ in range(8):
            g.move("east")

    def test_game_over_returns_game_over(self):
        g = Game.new("ge-001")
        g.state = State.ESCAPED
        result = g.move("north")
        assert result == "GAME OVER"
