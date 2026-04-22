import subprocess
import sys

log_path = r"D:\Projects\Nexus\governance\data\nats_collab_daemon.log"
log_file = open(log_path, "a")

p = subprocess.Popen(
    [sys.executable, r"D:\Projects\Nexus\governance\collab\collab_daemon.py", "jarvis"],
    stdout=log_file,
    stderr=subprocess.STDOUT
)
print(p.pid)