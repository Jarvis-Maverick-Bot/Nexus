"""Grid Escape game engine — state management and command interface."""

import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from games.grid_escape.grid import Grid
from games.grid_escape.grids import load_grid
from games.grid_escape.scoring import compute_tier


class State(Enum):
    ACTIVE = "ACTIVE"
    ESCAPED = "ESCAPED"
    QUIT = "QUIT"


DIRECTION_ALIASES = {
    "n": (0, -1), "north": (0, -1),
    "s": (0, 1), "south": (0, 1),
    "e": (1, 0), "east": (1, 0),
    "w": (-1, 0), "west": (-1, 0),
}


@dataclass
class Game:
    """Grid Escape game engine.

    Maintains grid state, agent position, step count, and game state.
    """

    grid: Grid
    agent_pos: tuple[int, int]
    step_count: int = 0
    visited: list[tuple[int, int]] = field(default_factory=list)
    state: State = State.ACTIVE
    _agent_moved: bool = field(default=False, repr=False)

    @classmethod
    def new(cls, grid_id: str) -> "Game":
        """Start a new game from a named starter grid.

        Agent is placed at START but has NOT yet moved.
        First move reveals the agent on the grid.
        """
        grid = load_grid(grid_id)
        agent_pos = grid.start
        return cls(grid=grid, agent_pos=agent_pos)

    def look(self) -> str:
        """Return ASCII grid with agent visible at current position.

        Agent appears as 'A' only after first move; initial position shows 'S'.
        """
        return self.grid.render(
            agent_pos=self.agent_pos if self._agent_moved else None
        )

    def _signal_escaped(self) -> str:
        """Signal that the agent escaped. Returns the ESCAPED message."""
        from datetime import datetime
        ts = datetime.now().isoformat(timespec="seconds")
        tier = compute_tier(self.grid.grid_id, self.step_count)
        return f"ESCAPED|{self.step_count}|{self.grid}|{ts}|{tier}"

    def move(self, direction: str) -> str:
        """Move agent in direction.

        Returns:
            'OK' on success — agent moved
            'BLOCKED' on wall/out-of-bounds — no state change
            'ESCAPED|...' when agent reaches EXIT (includes tier for display)
            error message on unknown direction
        """
        if self.state != State.ACTIVE:
            return "GAME OVER"

        direction = direction.strip().lower()
        if direction not in DIRECTION_ALIASES:
            return f"UNKNOWN DIRECTION: {direction}"

        dx, dy = DIRECTION_ALIASES[direction]
        nx, ny = self.agent_pos[0] + dx, self.agent_pos[1] + dy
        cell = self.grid.cell_at(nx, ny)

        if cell.name == "WALL":
            return "BLOCKED"

        # Update position
        self.agent_pos = (nx, ny)
        self.step_count += 1
        self._agent_moved = True
        self.visited.append((nx, ny))

        # Check for escape
        if cell.name == "EXIT":
            self.state = State.ESCAPED
            return self._signal_escaped()
        return "OK"

    def status(self) -> str:
        """Return current game status."""
        return (
            f"Steps: {self.step_count} | "
            f"Position: {self.agent_pos} | "
            f"State: {self.state.value}"
        )

    def restart(self) -> None:
        """Reset game to initial state."""
        self.agent_pos = self.grid.start
        self.step_count = 0
        self.visited = [self.grid.start]
        self.state = State.ACTIVE
        self._agent_moved = False

    def quit(self) -> str:
        """End the game session."""
        self.state = State.QUIT
        return f"FINAL SCORE: {self.step_count} steps | Position: {self.agent_pos}"
