# Grid Chase - Build Candidate (GC-BUILD-001)

**Artifact ID:** GC-BUILD-001
**Author:** Viper (engineering) - embodied internally for V1.7
**Date:** 2026-04-12
**Status:** VERIFIED - local runnable
**Stage:** 4 - Production Build

This is a historical build-candidate artifact. Keep it as evidence of a local runnable candidate at the time it was produced; do not treat it as the current Nexus runtime architecture or a production deployment approval.

## What This Is

Minimal agent-playable Grid Chase build candidate for V1.7.

Delivers:
- Python game engine (state/action/scoring per SPEC sections 2-4)
- Flask REST API (agent interface per SPEC section 6.3)
- Basic web dashboard (human observation only)
- Single-process local operation

This artifact is separate from the current 4.19 runtime module vocabulary. Active documentation should use Runtime Lifecycle Controller, Dispatch Controller, Candidate Agent Adapter, External Agent Runtime, and Resident Controller Service Package where those concepts apply.

## Files

| File | Description |
|------|-------------|
| `engine.py` | Core game logic |
| `api.py` | Flask REST API server |
| `dashboard.html` | Web dashboard for human observation |
| `requirements.txt` | Flask dependency |
| `run.bat` | Launch script (Windows) |
| `README.md` | This file |

## Running

```bash
pip install flask
python api.py
# Server starts on http://localhost:8001
# Open dashboard.html in browser
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/sessions` | GET | List sessions |
| `/api/v1/sessions` | POST | Create session |
| `/api/v1/sessions/{id}/runs` | POST | Start run |
| `/api/v1/run/{run_id}/step` | POST | Submit action |
| `/api/v1/run/{run_id}/result` | GET | Get final result |
| `/api/v1/leaderboard/{session_id}` | GET | Session leaderboard |

## Verified

- Engine: 8/8 unit tests pass (grid init, movement, token collection, wall bump, obstacle, termination, scoring formula)
- API: All 7 endpoints respond correctly
- Scoring formula matches SPEC section 4 exactly
