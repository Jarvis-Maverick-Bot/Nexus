"""
Grid Chase — REST API Server
GC-BUILD-001

Flask REST API implementing SPEC §6.3 agent interface.
"""

from __future__ import annotations
import uuid
import threading
from flask import Flask, request, jsonify
from engine import GridChaseEngine, Action

app = Flask(__name__)


@app.errorhandler(Exception)
def handle_error(e):
    import traceback
    traceback.print_exc()
    return {"error": str(e)}, 500

# Global state: run_id -> engine instance
_runs: dict[str, GridChaseEngine] = {}
_runs_lock = threading.Lock()

# Global state: session_id -> episode_seed
_sessions: dict[str, int] = {}

# Global state: session_id -> leaderboard list
_leaderboards: dict[str, list] = {}


# ────────────────────────────────────────────────────────────────────────────
# Config (defaults from SPEC §7)
# ────────────────────────────────────────────────────────────────────────────

DEFAULT_WIDTH = 10
DEFAULT_HEIGHT = 10
DEFAULT_TOKEN_RATE = 0.15
DEFAULT_OBSTACLE_RATE = 0.20
DEFAULT_MAX_STEPS = 50


# ────────────────────────────────────────────────────────────────────────────
# Utility
# ────────────────────────────────────────────────────────────────────────────

def _run_or_404(run_id: str):
    with _runs_lock:
        if run_id not in _runs:
            return None, ({"error": f"Run '{run_id}' not found"}, 404)
        return _runs[run_id], None


def _session_or_404(session_id: str):
    if session_id not in _sessions:
        return None, ({"error": f"Session '{session_id}' not found"}, 404)
    return _sessions[session_id], None


# ────────────────────────────────────────────────────────────────────────────
# Agent Registration (SPEC §6.1)
# Not required for local single-agent V1.7 -- registered on session create
# ────────────────────────────────────────────────────────────────────────────

@app.route("/api/v1/register", methods=["POST"])
def register():
    """Register agent (no-op for V1.7 local single-agent)."""
    return jsonify({"ok": True, "message": "Registration not required for V1.7 single-agent local"})


# ────────────────────────────────────────────────────────────────────────────
# Sessions (SPEC §6.3)
# ────────────────────────────────────────────────────────────────────────────

@app.route("/api/v1/sessions", methods=["GET"])
def list_sessions():
    """List available leaderboard sessions."""
    return jsonify({
        "ok": True,
        "sessions": [
            {"session_id": sid, "episode_seed": seed}
            for sid, seed in _sessions.items()
        ]
    })


@app.route("/api/v1/sessions", methods=["POST"])
def create_session():
    """
    Create a new leaderboard session.
    Returns session_id and episode_seed.
    """
    data = request.get_json() or {}

    width = data.get("grid_width", DEFAULT_WIDTH)
    height = data.get("grid_height", DEFAULT_HEIGHT)
    token_rate = data.get("token_rate", DEFAULT_TOKEN_RATE)
    obstacle_rate = data.get("obstacle_rate", DEFAULT_OBSTACLE_RATE)
    max_steps = data.get("max_steps", DEFAULT_MAX_STEPS)
    seed = data.get("episode_seed")

    if seed is None:
        import random
        seed = random.randint(0, 2**31 - 1)

    session_id = str(uuid.uuid4())[:8]
    _sessions[session_id] = seed
    _leaderboards[session_id] = []

    return jsonify({
        "ok": True,
        "session_id": session_id,
        "episode_seed": seed,
        "config": {
            "grid_height": height,
            "grid_width": width,
            "token_rate": token_rate,
            "obstacle_rate": obstacle_rate,
            "max_steps": max_steps,
        }
    })


@app.route("/api/v1/sessions/<session_id>/runs", methods=["POST"])
def start_run(session_id: str):
    """
    Start a new run within an existing session.
    Returns run_id and initial state.
    """
    seed, err = _session_or_404(session_id)
    if err:
        return jsonify(err[0]), err[1]

    # Create fresh engine for this run (new episode with same seed)
    with _runs_lock:
        engine = GridChaseEngine(episode_seed=seed)
        initial_state = engine.reset(seed=seed)
        run_id = f"{session_id}-{str(uuid.uuid4())[:8]}"
        _runs[run_id] = engine

    return jsonify({
        "ok": True,
        "run_id": run_id,
        "session_id": session_id,
        "initial_state": initial_state,
    })


@app.route("/api/v1/run/<run_id>/step", methods=["POST"])
def step(run_id: str):
    """
    Submit an action. Returns reward signal + next state.
    """
    engine, err = _run_or_404(run_id)
    if err:
        return jsonify(err[0]), err[1]

    data = request.get_json() or {}
    action: Action = data.get("action", "NORTH")
    if action not in ("NORTH", "SOUTH", "EAST", "WEST"):
        return jsonify({"error": f"Invalid action: {action}"}), 400

    reward_result = engine.step_action(action)
    state = engine._state()

    return jsonify({
        **reward_result,
        "state": state,
    })


@app.route("/api/v1/run/<run_id>/result", methods=["GET"])
def result(run_id: str):
    """Get final score and episode result."""
    engine, err = _run_or_404(run_id)
    if err:
        return jsonify(err[0]), err[1]

    entry = engine.leaderboard_entry(agent_name="agent")
    return jsonify({
        "ok": True,
        "run_id": run_id,
        "episode_done": engine.episode_done,
        "termination_reason": engine.termination_reason,
        **entry,
    })


@app.route("/api/v1/leaderboard/<session_id>", methods=["GET"])
def leaderboard(session_id: str):
    """Get leaderboard for session."""
    if session_id not in _sessions:
        return jsonify({"error": f"Session '{session_id}' not found"}), 404

    board = _leaderboards.get(session_id, [])
    # Sort by run_score desc, then moves_taken asc
    board_sorted = sorted(board, key=lambda e: (-e["run_score"], e["moves_taken"]))
    return jsonify({
        "ok": True,
        "session_id": session_id,
        "leaderboard": board_sorted,
    })


@app.route("/api/v1/health", methods=["GET"])
def health():
    """Health check."""
    return jsonify({"ok": True, "status": "running"})


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8001))
    app.run(host="0.0.0.0", port=port, debug=False)
