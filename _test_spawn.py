import sys
print("Python:", sys.executable)
print("CWD:", sys.path[0] if sys.path else "empty")

try:
    from openclaw import sessions_spawn
    print("IMPORT SUCCESS:", sessions_spawn)
    result = sessions_spawn(
        task="You are a test agent. Reply with 'pong' only.",
        runtime="subagent",
        agentId="viper",
        mode="run",
    )
    print("RESULT:", result)
except ImportError as e:
    print("IMPORT ERROR:", e)
except Exception as e:
    print("ERROR:", type(e).__name__, e)
