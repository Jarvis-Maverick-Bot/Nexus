import sys
import os

# Ensure proper working directory
os.chdir(r"D:\Projects\Nexus")
sys.path.insert(0, r"D:\Projects\Nexus")

# Run the server directly
exec(open(r"D:\Projects\Nexus\governance\ui\dashboard_server.py").read())