"""
PMO Dashboard Server
Serves the dashboard UI and handles API calls (clear history).
"""

import http.server
import json
import shutil
from pathlib import Path
from datetime import datetime
import os

PORT = 8765
UI_DIR = Path(__file__).parent
DATA_DIR = Path(__file__).parent.parent / "data"
STATE_FILE = DATA_DIR / "collab_state.json"
MESSAGE_LOG = DATA_DIR / "collab_messages.jsonl"
ARCHIVE_DIR = DATA_DIR / "archive"


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/ui/pmo_dashboard.html":
            self.path = "/ui/pmo_dashboard.html"

        if self.path.startswith("/ui/"):
            # Serve from UI directory
            file_path = UI_DIR / self.path[1:]
            if file_path.exists() and file_path.is_file():
                self.send_file(file_path)
                return

        if self.path == "/api/collabs" or self.path == "/data/collab_state.json":
            raw = STATE_FILE.read_text() if STATE_FILE.exists() else "{}"
            try:
                state = json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError:
                state = {}
            self.send_json(state)
            return

        if self.path == "/api/messages" or self.path == "/data/collab_messages.jsonl":
            text = MESSAGE_LOG.read_text() if MESSAGE_LOG.exists() else ""
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(text))
            self.end_headers()
            self.wfile.write(text.encode())
            return

        # Fallback: serve from ui dir
        if self.path == "/pmo_dashboard.html":
            self.send_file(UI_DIR / "pmo_dashboard.html")
            return

        self.send_error(404)

    def do_POST(self):
        if self.path == "/api/clear-history":
            ARCHIVE_DIR.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")

            shutil.copy(STATE_FILE, ARCHIVE_DIR / f"collab_state_{ts}.json")
            if MESSAGE_LOG.exists():
                shutil.copy(MESSAGE_LOG, ARCHIVE_DIR / f"collab_messages_{ts}.jsonl")

            STATE_FILE.write_text("{}")
            MESSAGE_LOG.write_text("")

            self.send_json({"ok": True, "archived_to": str(ARCHIVE_DIR)})
            return

        self.send_error(404)

    def send_file(self, file_path):
        ctype = "text/html" if file_path.suffix == ".html" else "text/plain"
        with open(file_path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, data):
        text = json.dumps(data)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(text))
        self.end_headers()
        self.wfile.write(text.encode())

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"PMO Dashboard: http://localhost:{PORT}/ui/pmo_dashboard.html")
    server.serve_forever()