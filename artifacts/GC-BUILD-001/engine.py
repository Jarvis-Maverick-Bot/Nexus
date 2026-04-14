"""
Grid Chase — Game Engine Core
GC-BUILD-001

Implements SPEC §2 (Grid and World Model), §3 (Agent Interface), §4 (Scoring).
"""

from __future__ import annotations
import random
import math
from dataclasses import dataclass, field
from typing import Literal

Action = Literal["NORTH", "SOUTH", "EAST", "WEST"]
Cell = str  # '.' | 'T' | '#' | 'A'


@dataclass
class GridChaseEngine:
    """
    Core game engine for Grid Chase.

    Grid cell types:
      '.' = EMPTY (traversable, no reward)
      'T' = TOKEN (+1 point when collected, becomes EMPTY)
      '#' = OBSTACLE (impassable)
      'A' = AGENT (render marker only — agent position from agent_position)
    """

    grid_height: int = 10
    grid_width: int = 10
    token_rate: float = 0.15
    obstacle_rate: float = 0.20
    max_steps: int = 50
    episode_seed: int | None = None

    # Runtime state
    grid: list[list[Cell]] = field(default_factory=list)
    agent_position: tuple[int, int] = (0, 0)
    tokens_collected: int = 0
    tokens_remaining: int = 0
    moves_taken: int = 0
    step: int = 0
    episode_done: bool = False
    termination_reason: str | None = None
    _num_tokens: int = 0

    def reset(self, seed: int | None = None) -> dict:
        """Initialize a new episode. Returns initial state."""
        if seed is not None:
            self.episode_seed = seed
            random.seed(seed)
        elif self.episode_seed is not None:
            random.seed(self.episode_seed)
        else:
            self.episode_seed = random.randint(0, 2**31 - 1)
            random.seed(self.episode_seed)

        # Create empty grid
        self.grid = [["." for _ in range(self.grid_width)] for _ in range(self.grid_height)]

        # Place obstacles
        num_obstacles = math.floor(self.grid_height * self.grid_width * self.obstacle_rate)
        placed = 0
        while placed < num_obstacles:
            x, y = random.randint(0, self.grid_width - 1), random.randint(0, self.grid_height - 1)
            if self.grid[y][x] == ".":
                self.grid[y][x] = "#"
                placed += 1

        # Place tokens
        self._num_tokens = math.floor(self.grid_height * self.grid_width * self.token_rate)
        placed = 0
        while placed < self._num_tokens:
            x, y = random.randint(0, self.grid_width - 1), random.randint(0, self.grid_height - 1)
            if self.grid[y][x] == ".":
                self.grid[y][x] = "T"
                placed += 1

        # Place agent
        attempts = 0
        while True:
            x, y = random.randint(0, self.grid_width - 1), random.randint(0, self.grid_height - 1)
            if self.grid[y][x] == ".":
                self.agent_position = (x, y)
                break
            attempts += 1
            if attempts > 10000:
                # Fallback: place on any non-obstacle, non-token cell
                for y in range(self.grid_height):
                    for x in range(self.grid_width):
                        if self.grid[y][x] == ".":
                            self.agent_position = (x, y)
                            break
                    else:
                        continue
                    break
                break

        # Reset counters
        self.tokens_collected = 0
        self.tokens_remaining = self._num_tokens
        self.moves_taken = 0
        self.step = 0
        self.episode_done = False
        self.termination_reason = None

        return self._state()

    def step_action(self, action: Action) -> dict:
        """
        Execute one action. Returns reward signal + next state.

        Invalid action handling (SPEC §3.2):
          - Move off-grid or into obstacle: agent stays, no movement, no point, step consumed
        """
        if self.episode_done:
            return self._reward_signal()

        dx, dy = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}.get(action, (0, 0))
        x, y = self.agent_position
        nx, ny = x + dx, y + dy

        # Check bounds
        if nx < 0 or nx >= self.grid_width or ny < 0 or ny >= self.grid_height:
            invalid = True
        elif self.grid[ny][nx] == "#":
            invalid = True
        else:
            invalid = False

        if not invalid:
            self.agent_position = (nx, ny)
            # Check for token collection
            if self.grid[ny][nx] == "T":
                self.grid[ny][nx] = "."
                self.tokens_collected += 1
                self.tokens_remaining -= 1
                reward = 1
            else:
                reward = 0
        else:
            reward = 0

        self.moves_taken += 1
        self.step += 1

        # Check termination
        if self.tokens_remaining == 0:
            self.episode_done = True
            self.termination_reason = "all_tokens_collected"
        elif self.step >= self.max_steps:
            self.episode_done = True
            self.termination_reason = "max_steps"
        else:
            self.termination_reason = None

        result = self._reward_signal()
        result["reward"] = reward
        return result

    def _state(self) -> dict:
        """Build full state object (SPEC §3.1)."""
        # Build agent marker grid for render
        render_grid = [row[:] for row in self.grid]
        ax, ay = self.agent_position
        render_grid[ay][ax] = "A"

        return {
            "grid": render_grid,
            "grid_height": self.grid_height,
            "grid_width": self.grid_width,
            "agent_position": {"x": self.agent_position[0], "y": self.agent_position[1]},
            "tokens_collected": self.tokens_collected,
            "tokens_remaining": self.tokens_remaining,
            "moves_taken": self.moves_taken,
            "step": self.step,
            "max_steps": self.max_steps,
            "episode_seed": self.episode_seed,
        }

    def _reward_signal(self) -> dict:
        """Build reward signal (SPEC §3.3)."""
        return {
            "reward": 0,
            "step": self.step,
            "tokens_collected": self.tokens_collected,
            "tokens_remaining": self.tokens_remaining,
            "episode_done": self.episode_done,
            "termination_reason": self.termination_reason,
        }

    def run_score(self) -> float:
        """Compute run_score per SPEC §4."""
        if self.tokens_collected == 0:
            return 0.0
        efficiency_bonus = max(0.0, 1.0 - self.moves_taken / self.max_steps) * 0.5
        return self.tokens_collected * (1.0 + efficiency_bonus)

    def leaderboard_entry(self, agent_name: str) -> dict:
        """Build leaderboard entry."""
        return {
            "agent_name": agent_name,
            "run_score": round(self.run_score(), 4),
            "tokens_collected": self.tokens_collected,
            "moves_taken": self.moves_taken,
            "episode_seed": self.episode_seed,
        }
