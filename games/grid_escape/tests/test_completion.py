"""Tests for completion detection (Task 1.5)."""

import pytest
from games.grid_escape.engine import Game, State
from datetime import datetime


_PATHS = {
    "ge-001": ["east", "south", "east", "south", "south", "east", "south", "east"],
    "ge-002": ["east", "north", "east", "east", "east", "east", "south",
               "south", "south", "west", "south", "south"],
    "ge-003": ["south", "south", "south", "east", "east", "north", "east",
               "north", "east", "north", "east", "east", "south", "south",
               "south", "south", "south", "south"],
}


class TestCompletionDetection:
    def test_escaped_output_format(self):
        g = Game.new("ge-001")
        g.restart()
        for move in _PATHS["ge-001"]:
            result = g.move(move)
        assert result.startswith("ESCAPED|"), f"Got: {result}"
        parts = result.split("|")
        assert len(parts) == 4
        assert parts[0] == "ESCAPED"
        assert int(parts[1]) == 8
        datetime.fromisoformat(parts[3])

    def test_after_escaped_no_further_moves(self):
        g = Game.new("ge-001")
        g.restart()
        for move in _PATHS["ge-001"]:
            g.move(move)
        assert g.state == State.ESCAPED
        result = g.move("north")
        assert result == "GAME OVER"
        assert g.step_count == 8

    def test_escaped_fires_once(self):
        g = Game.new("ge-001")
        g.restart()
        for move in _PATHS["ge-001"]:
            g.move(move)
        escaped_count = 0
        for _ in range(5):
            result = g.move("north")
            if result.startswith("ESCAPED"):
                escaped_count += 1
        assert escaped_count == 0

    def test_ge002_completion(self):
        g = Game.new("ge-002")
        g.restart()
        for move in _PATHS["ge-002"]:
            result = g.move(move)
        assert result.startswith("ESCAPED|")
        parts = result.split("|")
        assert int(parts[1]) == 12

    def test_ge003_completion(self):
        g = Game.new("ge-003")
        g.restart()
        for move in _PATHS["ge-003"]:
            result = g.move(move)
        assert result.startswith("ESCAPED|")
        parts = result.split("|")
        assert int(parts[1]) == 18
        datetime.fromisoformat(parts[3])
