"""Verify starter grids load correctly with expected optimal steps."""

import pytest
from games.grid_escape.grids import load_grid, get_optimal_steps


class TestStarterGrids:
    @pytest.mark.parametrize("grid_id,expected_opt", [
        ("ge-001", 8),
        ("ge-002", 12),
        ("ge-003", 18),
    ])
    def test_grid_loads_and_solvable(self, grid_id, expected_opt):
        g = load_grid(grid_id)
        assert g.compute_optimal_path() >= 0

    @pytest.mark.parametrize("grid_id,expected_opt", [
        ("ge-001", 8),
        ("ge-002", 12),
        ("ge-003", 18),
    ])
    def test_optimal_steps_match(self, grid_id, expected_opt):
        g = load_grid(grid_id)
        assert g.compute_optimal_path() == expected_opt, (
            f"{grid_id}: BFS={g.compute_optimal_path()}, expected={expected_opt}"
        )

    def test_grid_id_unknown_raises(self):
        with pytest.raises(ValueError):
            load_grid("ge-999")
