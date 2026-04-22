#!/usr/bin/env python3
"""PMO Dashboard Server - fixed version"""
import http.server
import json
import shutil
from pathlib import Path
from datetime import datetime

PORT = 8765
UI_DIR = Path(__file__).parent / "governance" / "ui"
DATA_DIR = Path(__file__).parent / "governance" / "data"
STATE_FILE = DATA_DIR / "collab_state.json"
MESSAGE_LOG = DATA_DIR / "collab_messages.jsonl"
ARCHIVE_DIR = DATA_DIR / "archive"

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}")

    def do_GET(self):
        try:
            if self.path == "/" or self.path == "/ui":
                self.path = "/ui/pmo_dashboard.html"

            if self.path == "/ui/pmo_dashboard.html":
                file_path = UI_DIR / "pmo_dashboard.html"
                if not file_path.exists():
                    self.send_error(404, "Not Found")
                    return
                with open(file_path, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", len(data))
                self.end_headers()
                self.wfile.write(data)
                return

            if self.path.startswith("/ui/"):
                file_path = UI_DIR / self.path[4:]
                if file_path.exists() and file_path.is_file():
                    ctype = "text/html" if file_path.suffix == ".html" else "text/plain"
                    with open(file_path, "rb") as f:
                        data = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", len(data))
                    self.end_headers()
                    self.wfile.write(data)
                    return

            if self.path in ("/api/collabs", "/data/collab_state.json"):
                raw = STATE_FILE.read_text() if STATE_FILE.exists() else "{}"
                try:
                    state = json.loads(raw) if raw.strip() else {}
                except json.JSONDecodeError:
                    state = {}
                text = json.dumps(state)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", len(text))
                self.end_headers()
                self.wfile.write(text.encode())
                return

            if self.path in ("/api/messages", "/data/collab_messages.jsonl"):
                text = MESSAGE_LOG.read_text() if MESSAGE_LOG.exists() else ""
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", len(text))
                self.end_headers()
                self.wfile.write(text.encode())
                return

            if self.path == "/pmo_dashboard.html":
                with open(UI_DIR / "pmo_dashboard.html", "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", len(data))
                self.end_headers()
                self.wfile.write(data)
                return

            self.send_error(404, "Not Found")
        except Exception as e:
            print(f"Error handling {self.path}: {e}")
            self.send_error(500, str(e))

    def do_POST(self):
        if self.path == "/api/clear-history":
            ARCHIVE_DIR.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.copy(STATE_FILE, ARCHIVE_DIR / f"collab_state_{ts}.json")
            if MESSAGE_LOG.exists():
                shutil.copy(MESSAGE_LOG, ARCHIVE_DIR / f"collab_messages_{ts}.jsonl")
            STATE_FILE.write_text("{}")
            MESSAGE_LOG.write_text("")
            text = json.dumps({"ok": True, "archived_to": str(ARCHIVE_DIR)})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(text))
            self.end_headers()
            self.wfile.write(text.encode())
            return
        self.send_error(404)

if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"PMO Dashboard running: http://localhost:{PORT}/ui/pmo_dashboard.html")
    server.serve_forever()