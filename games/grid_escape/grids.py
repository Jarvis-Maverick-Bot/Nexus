"""Starter grids for Grid Escape (ge-001, ge-002, ge-003)."""

from games.grid_escape.grid import Grid


_STARTER_GRIDS = {
    "ge-001": (7, 7, 3, 8),
    "ge-002": (8, 8, 549, 12),
    "ge-003": (10, 10, 548, 18),
}


def load_grid(grid_id: str) -> Grid:
    if grid_id not in _STARTER_GRIDS:
        raise ValueError(
            f"Unknown grid_id: {grid_id}. Valid: {', '.join(_STARTER_GRIDS)}"
        )
    w, h, seed, _ = _STARTER_GRIDS[grid_id]
    return Grid(w, h, seed=seed)


def get_optimal_steps(grid_id: str) -> int:
    if grid_id not in _STARTER_GRIDS:
        raise ValueError(f"Unknown grid_id: {grid_id}")
    return _STARTER_GRIDS[grid_id][3]
