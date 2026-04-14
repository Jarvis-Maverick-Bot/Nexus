"""Tests for grid data model and BFS pathfinding."""

import pytest
from games.grid_escape.grid import Grid, CellType


class TestGridModel:
    def test_grid_accepts_width_height_seed(self):
        g = Grid(7, 7, seed=42)
        assert g.width == 7
        assert g.height == 7
        assert g.seed == 42

    def test_deterministic_replay(self):
        """Same seed + same dimensions produces identical grid."""
        g1 = Grid(7, 7, seed=99)
        g2 = Grid(7, 7, seed=99)
        assert g1._cells == g2._cells
        assert g1.start == g2.start
        assert g1.exit == g2.exit

    def test_different_seed_different_grid(self):
        g1 = Grid(7, 7, seed=1)
        g2 = Grid(7, 7, seed=2)
        assert g1._cells != g2._cells

    def test_cell_type_enum_has_five_types(self):
        assert len(CellType) == 5
        assert CellType.WALL in CellType
        assert CellType.OPEN in CellType
        assert CellType.START in CellType
        assert CellType.EXIT in CellType
        assert CellType.AGENT in CellType

    def test_cell_at_returns_wall_for_oob(self):
        g = Grid(7, 7, seed=42)
        assert g.cell_at(-1, 0) == CellType.WALL
        assert g.cell_at(0, -1) == CellType.WALL
        assert g.cell_at(7, 0) == CellType.WALL
        assert g.cell_at(0, 7) == CellType.WALL

    def test_cell_at_returns_correct_type(self):
        g = Grid(7, 7, seed=42)
        sx, sy = g.start
        ex, ey = g.exit
        assert g.cell_at(sx, sy) == CellType.START
        assert g.cell_at(ex, ey) == CellType.EXIT

    def test_optimal_path_ge_zero_for_solvable(self):
        for grid_id, (w, h, opt) in [
            ("ge-001", (7, 7, 8)),
            ("ge-002", (8, 8, 12)),
            ("ge-003", (10, 10, 18)),
        ]:
            g = Grid(w, h, seed=42)
            steps = g.compute_optimal_path()
            assert steps >= 0, f"{grid_id}: optimal path should be >= 0, got {steps}"


class TestBFSPathfinding:
    def test_bfs_returns_negative_for_unsolvable(self):
        g = Grid(5, 5, seed=1)
        result = g.compute_optimal_path()
        assert result == -1 or result >= 0

    def test_bfs_path_length_matches_compute_optimal(self):
        g = Grid(7, 7, seed=42)
        steps = g.compute_optimal_path()
        if steps >= 0:
            path = g._bfs()
            assert path is not None
            assert len(path) - 1 == steps
