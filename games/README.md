# Games

`games` contains public, agent-playable example workflows.

These examples are useful for testing bounded task interaction, command parsing, completion evidence, and agent-facing loops without requiring production runtime infrastructure.

## Modules

- `grid_escape.py` and `grid_escape/` - Grid Escape game engine, CLI entry points, scoring, grid definitions, and tests.

## Boundaries

- Game examples are not the governance runtime.
- Completion lines and scores are local task evidence only.
- Game success does not imply runtime promotion, deployment approval, or final PASS for unrelated WBS work.
