@echo off
REM Grid Chase — Run GC-BUILD-001
REM Usage: run.bat [port]
set PORT=%1
if "%PORT%"=="" set PORT=8001
echo Installing dependencies...
pip install -r requirements.txt > nul 2>&1
echo Starting Grid Chase API on port %PORT%...
python api.py %PORT%
