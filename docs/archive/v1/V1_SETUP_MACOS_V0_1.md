# PMO Smart Agent V1 — macOS Setup Guide

**Author:** Jarvis
**Date:** 2026-04-09
**Status:** V1 ARCHIVE — UAT setup reference

---

## Overview

This guide explains how to set up and run the PMO Smart Agent V1 on macOS for UAT purposes.

The project has two runtimes:
1. **PMO Web UI** — FastAPI server (the UAT interface)
2. **gov_langgraph** — the governance engine (used by the Web UI)

---

## System Requirements

- macOS (Intel or Apple Silicon)
- Python 3.12 or higher
- Git
- Network access to clone the repo

---

## Step 1 — Clone the Repository

```bash
git clone https://github.com/Jarvis-Maverick-Bot/gov_langgraph.git
cd gov_langgraph
```

---

## Step 2 — Python Environment

**Using uv (recommended — faster):**
```bash
# Install uv if not present
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment with Python 3.12
uv venv --python 3.12 .venv

# Activate it
source .venv/bin/activate

# Install all dependencies
uv pip install -e .
```

**Using standard venv:**
```bash
# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .
```

---

## Step 3 — Install PMO Web UI Dependencies

The PMO Web UI has additional FastAPI dependencies. These are included in the package install above, but if running the UI directly:

```bash
# From the repo root
cd pmo_web_ui
pip install fastapi uvicorn

# Or from repo root, install everything:
pip install fastapi uvicorn pydantic
```

---

## Step 4 — Configure Environment

Create a `.env` file in the repo root (optional — V1 works with defaults):

```bash
# Optional — defaults shown below
PMO_PORT=8000
PMO_HOST=0.0.0.0
HARNESS_DATA_DIR=./data
LOG_LEVEL=INFO
```

---

## Step 5 — Initialise the Harness (Data Directory)

The harness needs a `data/` directory for workitems and taskstates:

```bash
# From repo root
mkdir -p data/workitems data/taskstates data/checkpoints data/evidence

# Initialise with default config
python -c "from gov_langgraph.harness import get_default_config; print(get_default_config())"
```

---

## Step 6 — Start the PMO Web UI

```bash
# From repo root
python -X utf8 pmo_web_ui/main.py
```

Or with uvicorn directly:

```bash
uvicorn pmo_web_ui.main:app --host 0.0.0.0 --port 8000
```

The server will start on `http://0.0.0.0:8000` (accessible from other machines on the same network at `http://<your-lan-ip>:8000`).

**To find your LAN IP on macOS:**
```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```

---

## Step 7 — Verify the Server is Running

```bash
curl http://localhost:8000/health
```

Expected response: `{"status":"ok"}` or similar.

---

## API Endpoints (UAT Test Surface)

Base URL: `http://localhost:8000` (or `http://<lan-ip>:8000` from another machine)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/kickoff` | Kick off a new task |
| `GET` | `/status/{task_id}` | Get task status |
| `POST` | `/gate/approve/{task_id}` | Approve gate |
| `POST` | `/gate/reject/{task_id}` | Reject gate with reason |

Example kickoff:
```bash
curl -X POST http://localhost:8000/kickoff \
  -H "Content-Type: application/json" \
  -d '{"task_name": "test-task", "project_id": "pmo-kickoff"}'
```

Example status:
```bash
curl http://localhost:8000/status/pmo-kickoff
```

---

## Running Tests

From the repo root:

```bash
# Unit tests (harness, platform_model)
python -m pytest gov_langgraph/harness/tests/
python -m pytest gov_langgraph/platform_model/tests/

# E2E test (9 steps — BA→SA→DEV→QA pipeline)
python gov_langgraph/tests/LANGGRAPH_E2E_TEST.py
```

---

## Project Structure Reference

```
gov_langgraph/
├── pmo_web_ui/          # FastAPI web server (UAT interface)
│   ├── main.py          # Entry point
│   └── static/         # Static assets
├── gov_langgraph/       # Core package
│   ├── harness/         # Layer 2: State + events + checkpoints
│   ├── platform_model/  # Layer 3: Governance objects + rules
│   ├── langgraph_engine/ # Layer 4: LangGraph pipeline
│   └── openclaw_integration/ # OpenClaw tool wrappers
├── data/                # Runtime data (created on first run)
├── pyproject.toml       # Package config
└── README.md
```

---

## Troubleshooting

**Port 8000 already in use:**
```bash
# Find what's using it
lsof -i :8000
# Kill it if needed
kill $(lsof -t -i :8000)
```

**Python version error:**
```bash
# Check version
python3 --version
# Must be 3.12+
```

**Module not found errors:**
```bash
# Reinstall dependencies
pip install -e .
```

**Slow startup on Apple Silicon:**
```bash
# Ensure OpenSSL is available
brew install openssl
```
