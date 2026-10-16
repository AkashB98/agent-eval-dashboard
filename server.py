"""Tiny localhost JSON API + dashboard, stdlib http.server only.

Routes:
  GET /                fleet dashboard page (HTML)
  GET /run/<run_id>    run drill-down page (HTML)
  GET /api/status      fleet roll-up JSON
  GET /api/health      same as /api/status (alias)
  GET /api/runs        manifest list JSON
  GET /api/run/<id>    one run summary JSON
"""

from __future__ import annotations

import json
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

from dashboard import render_fleet, render_run
from health import fleet_health
from store import Store, canonical

_RUN_RE = re.compile(r"^/run/([A-Za-z0-9._-]+)$")
_API_RUN_RE = re.compile(r"^/api/run/([A-Za-z0-9._-]+)$")


def make_handler(store_path: str, simulated: bool = False):
    store = Store(store_path)

    class Handler(BaseHTTPRequestHandler):
        server_version = "agent-eval-dashboard/1.0"

        def _json(self, obj, code: int = 200) -> None:
            body = canonical(obj) + "\n"
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _html(self, page: str, code: int = 200) -> None:
            data = page.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            path = urllib.parse.urlparse(self.path).path
            m = _RUN_RE.match(path)
            a = _API_RUN_RE.match(path)
            if path == "/":
                self._html(render_fleet(fleet_health(store), simulated=simulated))
            elif m:
                try:
                    self._html(render_run(store.get(m.group(1)), simulated=simulated))
                except KeyError:
                    self._json({"error": "unknown run_id"}, 404)
            elif path in ("/api/status", "/api/health"):
                self._json(fleet_health(store))
            elif path == "/api/runs":
                self._json(store.manifest())
            elif a:
                try:
                    self._json(store.get(a.group(1)))
                except KeyError:
                    self._json({"error": "unknown run_id"}, 404)
            else:
                self._json({"error": "not found"}, 404)

        def log_message(self, *args):  # quiet by default
            pass

    return Handler


def serve(store_path: str, port: int = 8767, simulated: bool = False) -> None:
    httpd = HTTPServer(("127.0.0.1", port), make_handler(store_path, simulated))
    print(f"agent-eval-dashboard serving on http://127.0.0.1:{httpd.server_port}/")
    httpd.serve_forever()
