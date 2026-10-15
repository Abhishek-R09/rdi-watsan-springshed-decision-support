"""Local server for the spring tool: the web page in interface/ sends a spring here and gets every agent's result back.

Runs on this computer only (127.0.0.1); no account, key or paid service.

    python scripts/serve_tool.py            then open http://127.0.0.1:8765

The page itself is served from interface/dist (build it once with `npm run build` in interface/). While
developing the page, `npm run dev` in interface/ forwards its /api calls here instead.

Endpoints:
    GET  /api/health   {"ok": true, ...}
    POST /api/assess   body: the request JSON from the page (see interface/src/types.ts)
                       reply: {"run_id", "output_directory", "summary", "agents"}
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from spring_agents.orchestrator import assess  # noqa: E402

DIST = ROOT / "interface" / "dist"
MAX_BODY = 1 << 20
# Fixed types: on some Windows computers the registry maps .js to text/plain, which browsers refuse for scripts.
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon"}

# The record that best describes each agent's step, for the page's progress list.
KEY_OUTPUT = {
    "AG-ORC": "AG-ORC.execution_record", "AG-SPR": "AG-SPR.spring_profile", "AG-VUL": "AG-VUL.vulnerability_assessment",
    "AG-TER": "AG-TER.terrain_package", "AG-CAT": "AG-CAT.catchment_geometry", "AG-LIN": "AG-LIN.run_trace",
    "AG-VER": "AG-VER.verification_report", "AG-COM": "AG-COM.assessment_summary",
}
PAGE_STATUS = {"complete": "complete", "provisional": "needs_review", "unavailable": "unavailable", "failed": "unavailable"}


def agent_progress(store) -> dict:
    agents = {}
    for output_id, record in store.records.items():
        agent_id = record["agent_id"]
        if KEY_OUTPUT.get(agent_id, output_id) == output_id or agent_id not in agents:
            agents[agent_id] = {"status": PAGE_STATUS[record["status"]], "message": record["reason"], "outputId": output_id}
    return agents


class Handler(BaseHTTPRequestHandler):
    server_version = "SpringTool/0.1"

    def _send(self, status, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status, value):
        self._send(status, json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"), "application/json")

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/health":
            self._json(HTTPStatus.OK, {"ok": True, "agents": ["AG-VUL", "catchment"], "page_built": (DIST / "index.html").is_file()})
            return
        if not (DIST / "index.html").is_file():
            self._send(HTTPStatus.OK, b"The page is not built yet. In interface/, run: npm ci, then npm run build. "
                                      b"Or run npm run dev there and open the address it prints.", "text/plain; charset=utf-8")
            return
        file = (DIST / path.lstrip("/")).resolve()
        if path == "/" or DIST.resolve() not in file.parents or not file.is_file():
            file = DIST / "index.html"
        self._send(HTTPStatus.OK, file.read_bytes(), TYPES.get(file.suffix.lower()) or mimetypes.guess_type(file.name)[0] or "application/octet-stream")

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/api/assess":
            self._json(HTTPStatus.NOT_FOUND, {"error": "Unknown address"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 < length <= MAX_BODY:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "Send the request as JSON (up to 1 MB)"})
            return
        try:
            submission = json.loads(self.rfile.read(length))
            store, summary = assess(submission)
        except (ValueError, KeyError, TypeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": f"Assessment could not start: {exc}"})
            return
        except Exception as exc:  # report, keep the server running
            traceback.print_exc()
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Assessment failed: {exc}"})
            return
        self._json(HTTPStatus.OK, {"run_id": store.run_id, "output_directory": str(store.directory),
                                   "summary": summary, "agents": agent_progress(store)})

    def log_message(self, fmt, *args):
        sys.stderr.write(f"{self.log_date_time_string()} {fmt % args}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = HTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Spring tool running at http://127.0.0.1:{args.port}  (Ctrl+C to stop)")
    if not (DIST / "index.html").is_file():
        print("The page is not built yet: run `npm ci` and `npm run build` in interface/, or use `npm run dev` there.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
