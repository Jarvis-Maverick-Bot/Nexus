# Grid Escape

First AI-native game product for the Jarvis/Viper governance platform.

## Quick Start

**Recommended (if `python -m` works in your environment):**
```bash
python -m games.grid_escape --grid ge-001
```

**Fallback (works in any environment):**
```bash
python games/grid_escape.py --grid ge-001
```

**Batch mode (for agents):**
```bash
echo -e "look\nmove east\n..." | python games/grid_escape.py --grid ge-001
```

## Grid IDs

| Grid | Size | Optimal |
|------|------|---------|
| `ge-001` | 7 x 7 | 8 steps |
| `ge-002` | 8 x 8 | 12 steps |
| `ge-003` | 10 x 10 | 18 steps |

## Commands

| Command | Description |
|---------|-------------|
| `look` | Render current grid state (ASCII) |
| `move <dir>` | Move agent (n/s/e/w or north/south/east/west) |
| `status` | Show step count, position, state |
| `restart` | Reset to initial state |
| `quit` | End session, show final score |

## Completion Line

When the agent reaches EXIT, the game outputs:

```
ESCAPED|<steps>|<grid_id>|<timestamp>
```

Example:
```
ESCAPED|8|Grid(7x7, seed=3)|2026-04-14T13:35:14
```

## Scoring Tiers

After ESCAPED, the tier is computed from steps vs optimal:

| Tier | Condition |
|------|-----------|
| PERFECT | diff <= 0 (at or below optimal) |
| EXCELLENT | diff <= 2 |
| GOOD | diff <= 5 |
| COMPLETED | diff <= 10 |
| OVERMOVED | diff > 10 |

## Architecture

```
games/
  grid_escape.py        # Fallback runner (works without -m)
  __init__.py           # Package marker
  grid_escape/
    __init__.py
    __main__.py         # CLI entry point
    grid.py             # Grid data model, BFS pathfinding, wall perimeter
    engine.py           # Game state machine
    scoring.py          # Tier computation
    grids.py            # Starter grid definitions (ge-001/002/003)
    tests/
      test_pathfinding.py
      test_grids.py
      test_movement.py
      test_commands.py
      test_completion.py
      test_scoring.py
```

## Running Tests

```bash
pip install -e .
python -m pytest games/grid_escape/tests/ -v
```

Or without installing:
```bash
PYTHONPATH=games python -m pytest games/grid_escape/tests/ -v
```
