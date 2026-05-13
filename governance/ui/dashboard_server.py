"""
PMO Dashboard Server
Serves the dashboard UI and handles API calls (clear history).
"""

import http.server
import asyncio
import json
import shutil
import urllib.parse
from pathlib import Path
from datetime import datetime
import os

PORT = 8765
UI_DIR = Path(__file__).parent
DATA_DIR = Path(__file__).parent.parent / "data"
STATE_FILE = DATA_DIR / "collab_state.json"
MESSAGE_LOG = DATA_DIR / "collab_messages.jsonl"
ARCHIVE_DIR = DATA_DIR / "archive"

DEFAULT_NATS_URL = os.getenv("NATS_URL", "nats://192.168.31.64:4222")
DEFAULT_PHASE3_STREAM = os.getenv("PHASE3_MQ_STREAM", "phase3-jarvis-inbox")
DEFAULT_PHASE3_CONSUMER = os.getenv("PHASE3_MQ_CONSUMER", "phase3-jarvis-receiver")


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/" or path == "/ui/pmo_dashboard.html":
            self.path = "/ui/pmo_dashboard.html"

        if path.startswith("/ui/"):
            # Serve from UI directory
            file_path = UI_DIR / path.removeprefix("/ui/")
            if file_path.exists() and file_path.is_file():
                self.send_file(file_path)
                return

        if path == "/api/collabs" or path == "/data/collab_state.json":
            raw = STATE_FILE.read_text() if STATE_FILE.exists() else "{}"
            try:
                state = json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError:
                state = {}
            self.send_json(state)
            return

        if path == "/api/messages" or path == "/data/collab_messages.jsonl":
            text = MESSAGE_LOG.read_text() if MESSAGE_LOG.exists() else ""
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(text))
            self.end_headers()
            self.wfile.write(text.encode())
            return

        if path == "/api/mq/phase3-status":
            nats_url = query.get("nats_url", [DEFAULT_NATS_URL])[0]
            stream = query.get("stream", [DEFAULT_PHASE3_STREAM])[0]
            consumer = query.get("consumer", [DEFAULT_PHASE3_CONSUMER])[0]
            self.send_json(get_phase3_mq_status(nats_url, stream, consumer))
            return

        # Fallback: serve from ui dir
        if path == "/pmo_dashboard.html":
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


def _safe_get(obj, name, default=None):
    return getattr(obj, name, default)


def _stream_state_dict(info):
    state = _safe_get(info, "state")
    if not state:
        return {}
    return {
        "messages": _safe_get(state, "messages"),
        "bytes": _safe_get(state, "bytes"),
        "first_seq": _safe_get(state, "first_seq"),
        "last_seq": _safe_get(state, "last_seq"),
        "consumer_count": _safe_get(state, "consumer_count"),
        "deleted": _safe_get(state, "deleted"),
        "num_deleted": _safe_get(state, "num_deleted"),
        "num_subjects": _safe_get(state, "num_subjects"),
    }


def _consumer_state_dict(info):
    delivered = _safe_get(info, "delivered")
    ack_floor = _safe_get(info, "ack_floor")
    return {
        "name": _safe_get(_safe_get(info, "config"), "durable_name") or _safe_get(_safe_get(info, "config"), "name"),
        "filter_subject": _safe_get(_safe_get(info, "config"), "filter_subject"),
        "num_ack_pending": _safe_get(info, "num_ack_pending"),
        "num_pending": _safe_get(info, "num_pending"),
        "num_waiting": _safe_get(info, "num_waiting"),
        "num_redelivered": _safe_get(info, "num_redelivered"),
        "delivered_consumer_seq": _safe_get(delivered, "consumer_seq") if delivered else None,
        "delivered_stream_seq": _safe_get(delivered, "stream_seq") if delivered else None,
        "ack_floor_consumer_seq": _safe_get(ack_floor, "consumer_seq") if ack_floor else None,
        "ack_floor_stream_seq": _safe_get(ack_floor, "stream_seq") if ack_floor else None,
    }


async def _get_phase3_mq_status_async(nats_url, stream, consumer):
    import nats

    nc = await nats.connect(nats_url, connect_timeout=2, max_reconnect_attempts=0)
    try:
        js = nc.jetstream()
        stream_info = await js.stream_info(stream)
        consumer_info = await js.consumer_info(stream, consumer)
        return {
            "ok": True,
            "nats_url": nats_url,
            "stream": stream,
            "consumer": consumer,
            "stream_state": _stream_state_dict(stream_info),
            "consumer_state": _consumer_state_dict(consumer_info),
            "checked_at": datetime.now().isoformat(timespec="seconds"),
        }
    finally:
        await nc.close()


def get_phase3_mq_status(nats_url, stream, consumer):
    try:
        return asyncio.run(_get_phase3_mq_status_async(nats_url, stream, consumer))
    except Exception as exc:
        return {
            "ok": False,
            "nats_url": nats_url,
            "stream": stream,
            "consumer": consumer,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "checked_at": datetime.now().isoformat(timespec="seconds"),
        }


if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"PMO Dashboard: http://localhost:{PORT}/ui/pmo_dashboard.html")
    server.serve_forever()
