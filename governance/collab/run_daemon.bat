@echo off
REM Start the NATS collaboration daemon (listener + worker loop + heartbeat)
REM Must be run from the Nexus project root (D:\Projects\Nexus)
REM Usage: run_daemon.bat [my_id] [nats_url]
REM Example: run_daemon.bat jarvis

set PYTHONPATH=%CD%
python governance\collab\collab_daemon.py %*
