"""Grid data model, pathfinding, and grid generation."""

from enum import Enum
from typing import Optional
from collections import deque
import random


class CellType(Enum):
    WALL = "#"
    OPEN = "."
    START = "S"
    EXIT = "E"
    AGENT = "A"


GRID_SYMBOLS = {
    "#": CellType.WALL,
    ".": CellType.OPEN,
    "S": CellType.START,
    "E": CellType.EXIT,
    "A": CellType.AGENT,
}


class Grid:
    """N x M grid with deterministic generation.

    Args:
        width:  Number of columns (must be >= 5)
        height: Number of rows (must be >= 5)
        seed:   Integer seed for reproducible grid generation.
                Same seed + same width/height always produces identical grid.
    """

    def __init__(self, width: int, height: int, seed: Optional[int] = None):
        if width < 5 or height < 5:
            raise ValueError("Grid must be at least 5x5")
        self.width = width
        self.height = height
        self.seed = seed
        self._cells = None
        self._start = None
        self._exit = None
        self._optimal = None
        self._generate()

    def _generate(self) -> None:
        """Generate grid deterministically from seed."""
        rng = random.Random(self.seed)

        # Initialize all cells as OPEN
        self._cells = [[CellType.OPEN for _ in range(self.width)] for _ in range(self.height)]

        # Place START in top-left region
        sx = rng.randrange(1, min(3, self.width - 2))
        sy = rng.randrange(1, min(3, self.height - 2))
        self._cells[sy][sx] = CellType.START
        self._start = (sx, sy)

        # Place EXIT in bottom-right region
        ex = rng.randrange(self.width - 3, self.width - 1)
        ey = rng.randrange(self.height - 3, self.height - 1)
        self._cells[ey][ex] = CellType.EXIT
        self._exit = (ex, ey)

        # Add random walls (25-35% of interior cells)
        interior = []
        for y in range(1, self.height - 1):
            for x in range(1, self.width - 1):
                if (x, y) not in (self._start, self._exit):
                    interior.append((x, y))
        rng.shuffle(interior)
        wall_count = int(len(interior) * rng.uniform(0.25, 0.35))
        for x, y in interior[:wall_count]:
            self._cells[y][x] = CellType.WALL

        # Ensure path exists — if BFS fails, regenerate walls
        for attempt in range(100):
            path = self._bfs()
            if path is not None:
                self._optimal = len(path) - 1  # steps, not nodes
                return
            # Clear walls and try fewer
            interior_cur = [(x, y) for y in range(1, self.height - 1)
                                     for x in range(1, self.width - 1)
                                     if self._cells[y][x] == CellType.WALL
                                     and (x, y) not in (self._start, self._exit)]
            rng.shuffle(interior_cur)
            remove_count = len(interior_cur) // 2
            for x, y in interior_cur[:remove_count]:
                self._cells[y][x] = CellType.OPEN

        raise RuntimeError(f"Could not generate solvable grid after 100 attempts (w={self.width}, h={self.height}, seed={self.seed})")

    def cell_at(self, x: int, y: int) -> CellType:
        """Return cell type at (x, y). Returns WALL for out-of-bounds."""
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return CellType.WALL
        return self._cells[y][x]

    def set_cell(self, x: int, y: int, cell_type: CellType) -> None:
        """Set cell type at (x, y). No-op if out of bounds."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self._cells[y][x] = cell_type

    @property
    def start(self) -> tuple[int, int]:
        return self._start

    @property
    def exit(self) -> tuple[int, int]:
        return self._exit

    def compute_optimal_path(self) -> int:
        """Return BFS optimal path length in steps from START to EXIT.

        Returns:
            Number of steps (edges) in shortest path.
            Returns -1 if no path exists.
        """
        if self._optimal is not None:
            return self._optimal
        path = self._bfs()
        if path is None:
            return -1
        return len(path) - 1

    def _bfs(self) -> Optional[list[tuple[int, int]]]:
        """Breadth-first search from START to EXIT.

        Returns:
            List of (x, y) positions from START to EXIT (inclusive).
            None if no path exists.
        """
        sx, sy = self._start
        ex, ey = self._exit
        queue = deque([(sx, sy, [(sx, sy)])])
        visited = {(sx, sy)}

        while queue:
            x, y, path = queue.popleft()
            if (x, y) == (ex, ey):
                return path
            for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                nx, ny = x + dx, y + dy
                if (nx, ny) not in visited and self.cell_at(nx, ny) != CellType.WALL:
                    visited.add((nx, ny))
                    queue.append((nx, ny, path + [(nx, ny)]))
        return None

    def render(self, agent_pos: Optional[tuple[int, int]] = None) -> str:
        """Render grid as ASCII string.

        Args:
            agent_pos: (x, y) of agent. If None, shows START instead of AGENT.
        """
        lines = []
        for y in range(self.height):
            row = ""
            for x in range(self.width):
                if agent_pos == (x, y):
                    row += CellType.AGENT.value
                elif (x, y) == self._start:
                    row += CellType.START.value
                elif (x, y) == self._exit:
                    row += CellType.EXIT.value
                else:
                    row += self._cells[y][x].value
            lines.append(row)
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"Grid({self.width}x{self.height}, seed={self.seed})"

    @classmethod
    def from_ascii(cls, ascii_map: str, seed: Optional[int] = None) -> "Grid":
        """Create a Grid from an ASCII-art string.


        Args:
            ascii_map: Multi-line string with '#'=WALL, '.'=OPEN, 'S'=START, 'E'=EXIT
            seed: Optional seed (not used for generation, stored for repr)

        """
        lines = ascii_map.strip().split("\n")
        height = len(lines)
        width = max(len(l) for l in lines)

        grid = cls.__new__(cls)
        grid.width = width
        grid.height = height
        grid.seed = seed
        grid._cells = []
        grid._start = None
        grid._exit = None
        grid._optimal = None

        for y, line in enumerate(lines):
            row = []
            for x, char in enumerate(line.ljust(width)):
                cell_map = {"#": CellType.WALL, ".": CellType.OPEN,
                        "S": CellType.START, "E": CellType.EXIT}
                row.append(cell_map.get(char, CellType.WALL))
                if char == "S":
                    grid._start = (x, y)
                elif char == "E":
                    grid._exit = (x, y)
            grid._cells.append(row)


        path = grid._bfs()
        if path is None:
            raise ValueError(f"Grid has no valid path from S to E")
        grid._optimal = len(path) - 1
        return grid
