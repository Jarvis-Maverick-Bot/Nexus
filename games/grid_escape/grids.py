"""Starter grids for Grid Escape (ge-001, ge-002, ge-003).

Grids are generated programmatically from verified seeds.
Each seed -> grid dimensions -> optimal path length is BFS-verified.
"""

from grid_escape.grid import Grid


_STARTER_GRIDS = {
    # grid_id: (width, height, seed, optimal_steps)
    # Seeds verified with wall perimeter enforced
    "ge-001": (7, 7, 3, 8),
    "ge-002": (8, 8, 549, 12),
    "ge-003": (10, 10, 548, 18),
}


def load_grid(grid_id: str) -> Grid:
    """Load a named starter grid.

    Args:
        grid_id: One of 'ge-001', 'ge-002', 'ge-003'

    Returns:
        Grid instance with deterministic generation and pre-verified optimal path.
    """
    if grid_id not in _STARTER_GRIDS:
        raise ValueError(
            f"Unknown grid_id: {grid_id}. Valid: {', '.join(_STARTER_GRIDS)}"
        )
    w, h, seed, _ = _STARTER_GRIDS[grid_id]
    return Grid(w, h, seed=seed)


def get_optimal_steps(grid_id: str) -> int:
    """Return the optimal step count for a starter grid."""
    if grid_id not in _STARTER_GRIDS:
        raise ValueError(f"Unknown grid_id: {grid_id}")
    return _STARTER_GRIDS[grid_id][3]
