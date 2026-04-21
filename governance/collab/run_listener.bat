@echo off
REM Start the NATS collaboration listener
REM Must be run from the Nexus project root (D:\Projects\Nexus)
REM Usage: run_listener.bat <my_id> [nats_url]
REM Example: run_listener.bat jarvis

set PYTHONPATH=%CD%
python governance\collab\listener.py %*
