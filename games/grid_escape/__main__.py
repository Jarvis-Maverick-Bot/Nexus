"""Grid Escape CLI interface.

Usage:
    interactive:   python grid_escape.py
    batch:         echo -e "look\nmove north\n..." | python grid_escape.py --grid <id>
"""

import sys
import argparse
from games.grid_escape.engine import Game, State


def main() -> None:
    parser = argparse.ArgumentParser(description="Grid Escape — AI-native maze game")
    parser.add_argument("--grid", default="ge-001", help="Grid ID: ge-001, ge-002, ge-003")
    parser.add_argument("--seed", type=int, default=None, help="Seed override (optional)")
    args = parser.parse_args()

    # Load and start game
    game = Game.new(args.grid)
    game.restart()

    # Interactive or batch mode
    if sys.stdin.isatty():
        _run_interactive(game)
    else:
        _run_batch(game)


def _run_interactive(game: Game) -> None:
    print("Grid Escape \u2014 type 'help' for commands")
    print(game.look())
    print()

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not line:
            continue
        output = _execute(game, line)
        if output.startswith("ESCAPED|"):
            print(_display_escaped(output))
        else:
            print(output)
        if output == "quit":
            break


def _display_escaped(raw: str) -> str:
    """Parse ESCAPED|<steps>|<grid>|<ts>|<tier> and show a friendly message."""
    parts = raw.split("|")
    if len(parts) == 5 and parts[0] == "ESCAPED":
        tier = parts[4]
        steps = parts[1]
        return f"ESCAPED! {steps} steps — You achieved: {tier}"
    return raw


def _run_batch(game: Game) -> None:
    """Read commands from stdin, write output to stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        output = _execute(game, line)
        if output.startswith("ESCAPED|"):
            print(_display_escaped(output))
        else:
            print(output)
        if output.startswith("ESCAPED") or game.state == State.QUIT:
            break


def _execute(game: Game, line: str) -> str:
    """Parse and execute a command line."""
    parts = line.split()
    if not parts:
        return ""
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else None

    match cmd:
        case "look":
            return game.look()
        case "move":
            if not arg:
                return "ERROR: move requires a direction (n/s/e/w)"
            return game.move(arg)
        case "status":
            return game.status()
        case "restart":
            game.restart()
            return "RESTARTED\n" + game.look()
        case "quit":
            return game.quit()
        case "help":
            return "Commands: look, move <dir>, status, restart, quit"
        case _:
            return f"UNKNOWN COMMAND: {cmd}"


if __name__ == "__main__":
    main()
