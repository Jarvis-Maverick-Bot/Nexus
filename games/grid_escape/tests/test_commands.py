"""Tests for game commands."""

import pytest
from games.grid_escape.engine import Game, State


class TestAll5Commands:
    def test_all_commands_recognized(self):
        g = Game.new("ge-001")
        g.restart()
        result = g.look()
        assert isinstance(result, str)
        assert len(result) > 0
        result = g.move("east")
        assert result in ("OK", "BLOCKED", "ESCAPED")
        result = g.status()
        assert "Steps:" in result
        result = g.restart()
        assert result is None
        result = g.quit()
        assert "FINAL SCORE" in result

    def test_unknown_command_returns_unknown(self):
        g = Game.new("ge-001")
        g.restart()
        result = g.move("fly")
        assert "UNKNOWN" in result

    def test_restart_resets_correctly(self):
        g = Game.new("ge-003")
        g.restart()
        g.move("south")
        g.move("east")
        assert g.step_count == 2
        assert g.state == State.ACTIVE
        g.restart()
        assert g.step_count == 0
        assert g.agent_pos == g.grid.start
        assert g.state == State.ACTIVE
        assert g._agent_moved == False

    def test_quit_sets_quit_state(self):
        g = Game.new("ge-001")
        g.restart()
        result = g.quit()
        assert g.state == State.QUIT
        assert "FINAL SCORE" in result
        assert "steps" in result

    def test_status_format(self):
        g = Game.new("ge-001")
        g.restart()
        status = g.status()
        assert "Steps:" in status
        assert "Position:" in status
        assert "State:" in status

    def test_restart_during_escaped_resets(self):
        g = Game.new("ge-001")
        g.restart()
        g.state = State.ESCAPED
        g.restart()
        assert g.state == State.ACTIVE
        assert g.step_count == 0

    def test_quit_during_escaped_works(self):
        g = Game.new("ge-001")
        g.restart()
        g.state = State.ESCAPED
        result = g.quit()
        assert "FINAL SCORE" in result
        assert g.state == State.QUIT
