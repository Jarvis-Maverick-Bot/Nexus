# TDD Instantiation Trace — M4-R1 (Real Task Redo)

**Date:** 2026-04-14 16:23 GMT+8
**Status:** REVISION — using real task against actual V1.8 codebase
**Purpose:** Address Nova's blocking issue — prior trace was detached mini-example; this proves real integrated handoff

---

## Task from Planner

- TASK-001: Update ESCAPED format to include tier as sixth field (pipe-delimited)
- TASK-002: Wire compute_tier into escape path so tier appears in ESCAPED message
- TASK-003: Add end-to-end integration test for ESCAPED with tier

**Real codebase context:**
- `games/grid_escape/engine.py` — `Game.move()` returns `ESCAPED|<steps>|<grid>|<ts>` (no tier)
- `games/grid_escape/scoring.py` — `compute_tier(grid_id, steps)` exists but never called in escape path

---

## TDD Output

```json
{
  "failing_test": {
    "code": "import pytest\nfrom games.grid_escape.engine import Game\n\n_PATH_GE001_ESCAPE = ['east', 'south', 'east', 'south', 'south', 'east', 'south', 'east']\n\nclass TestEscapedTierField:\n    def test_escaped_message_has_tier_field(self):\n        g = Game.new('ge-001')\n        g.restart()\n        for move in _PATH_GE001_ESCAPE:\n            result = g.move(move)\n        assert result.startswith('ESCAPED|')\n        parts = result.split('|')\n        assert len(parts) == 5, f'Expected 5 fields, got {len(parts)}: {result}'\n        tier = parts[4]\n        assert tier in ('PERFECT', 'EXCELLENT', 'GOOD', 'COMPLETED', 'OVERMOVED')\n        assert tier != ''\n\n    def test_escaped_tier_is_perfect_for_optimal_path(self):\n        from games.grid_escape.scoring import compute_tier\n        expected = compute_tier('ge-001', 8)\n        assert expected == 'PERFECT'\n        g = Game.new('ge-001')\n        g.restart()\n        escaped_msg = None\n        for move in _PATH_GE001_ESCAPE:\n            r = g.move(move)\n            if r.startswith('ESCAPED|'):\n                escaped_msg = r\n                break\n        assert escaped_msg is not None\n        assert escaped_msg.split('|')[4] == 'PERFECT'",
    "test_name": "test_escaped_message_has_tier_field",
    "expected_failure_message": "AssertionError: ESCAPED message should have 5 pipe-delimited fields (got 4): ESCAPED|8|Grid(7x7, seed=3)|2026-04-14T16:20:20"
  },
  "passing_code": {
    "code": "Changes to 3 files:\n1. grid.py: Grid.__init__ accepts grid_id parameter, stored as self._grid_id, grid_id property added\n2. grids.py: load_grid passes grid_id=grid_id to Grid() constructor\n3. engine.py: move() calls compute_tier(self.grid.grid_id, self.step_count) and appends tier as 5th field\n   Old: f'ESCAPED|{self.step_count}|{self.grid}|{ts}'\n   New: f'ESCAPED|{self.step_count}|{self.grid}|{ts}|{tier}'",
    "language": "python"
  },
  "test_results": {
    "failing_test_passed": false,
    "passing_test_passed": true,
    "failing_test_output": "FAILED — len(parts)==5 assertion failed (got 4): ESCAPED|8|Grid(7x7, seed=3)|2026-04-14T16:20:20",
    "passing_test_output": "55 tests pass — new tier field in ESCAPED, pre-existing test_completion updated to expect 5 fields"
  }
}
```

---

## TDD Cycle Verification

- [x] Task spec in -> failing test out
- [x] Failing test FAILS against actual current codebase (tier not yet in ESCAPED)
- [x] Minimal passing code: compute_tier wired into escape path in engine.py
- [x] TDD cycle proven: failing test before passing code
- [x] Integrated into real V1.8 codebase — not a standalone mini-module

## Changes Applied

| File | Change |
|------|--------|
| `games/grid_escape/grid.py` | Added `grid_id` param + property |
| `games/grid_escape/grids.py` | Passes `grid_id` to Grid constructor |
| `games/grid_escape/engine.py` | `compute_tier` called on escape, tier added as 5th field |
| `games/grid_escape/tests/test_completion.py` | Updated `test_escaped_output_format` to expect 5 fields instead of 4 |

## New ESCAPED Format

```
ESCAPED|8|Grid(7x7, seed=3)|2026-04-14T16:22:14|PERFECT
```

**Status: TDD SEAT RE-VERIFIED (real integrated handoff)**

Seat labeled `instantiated` in: `V1_8_AGENT_ROLES.md`