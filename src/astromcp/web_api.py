"""Tiny HTTP API exposing `whats_here` for the "Is it already known?" web page.

Standard library only (no MCP, no AI): GET /whats_here?ra=..&dec=..[&radius=..][&epoch=..]
returns the same JSON as the MCP tool, minus the bulky per-source `details`.
Meant to run on localhost behind nginx (auth + rate limiting are done there; a small
per-IP limit here is a second line of defence).

    python -m astromcp.web_api --port 8097
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .observe import observe_tonight
from .util import validate_position
from .whats_here import whats_here

MAX_PER_MINUTE = 6
_hits: dict[str, list[float]] = {}
_lock = threading.Lock()


def _allowed(ip: str) -> bool:
    now = time.time()
    with _lock:
        recent = [t for t in _hits.get(ip, []) if now - t < 60]
        if len(recent) >= MAX_PER_MINUTE:
            _hits[ip] = recent
            return False
        recent.append(now)
        _hits[ip] = recent
        return True


def answer(query: dict[str, list[str]]) -> tuple[int, dict[str, Any]]:
    try:
        ra = float(query["ra"][0])
        dec = float(query["dec"][0])
        radius = float(query.get("radius", ["5"])[0])
        epoch = query.get("epoch", [None])[0] or None
        validate_position(ra, dec, radius, 60)
    except (KeyError, ValueError, IndexError) as e:
        return 400, {"error": f"invalid query: {e}"}
    r = whats_here(ra, dec, radius, epoch)
    r.pop("details", None)
    return 200, r


def answer_tonight(query: dict[str, list[str]]) -> tuple[int, dict[str, Any]]:
    try:
        lat = float(query["lat"][0])
        lon = float(query["lon"][0])
        date = query.get("date", [None])[0] or None
        mag = float(query.get("mag_limit", ["18.5"])[0])
        if not (-90 <= lat <= 90 and -180 <= lon <= 360) or not (10 <= mag <= 21):
            raise ValueError("lat/lon/mag_limit out of range")
    except (KeyError, ValueError, IndexError) as e:
        return 400, {"error": f"invalid query: {e}"}
    try:
        return 200, observe_tonight(lat, lon, date, mag_limit=mag, limit=40)
    except ValueError as e:
        return 503, {"error": str(e)}


class Handler(BaseHTTPRequestHandler):
    server_version = "astromcp-web"

    def do_GET(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        rota = url.path.rstrip("/").rsplit("/", 1)[-1]
        if rota not in ("whats_here", "observe_tonight"):
            return self._send(404, {"error": "not found"})
        ip = self.headers.get("X-Real-IP") or self.client_address[0]
        if not _allowed(ip):
            return self._send(429, {"error": "too many requests, wait a minute"})
        q = parse_qs(url.query)
        code, body = answer(q) if rota == "whats_here" else answer_tonight(q)
        self._send(code, body)

    def _send(self, code: int, body: dict[str, Any]) -> None:
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args: Any) -> None:  # keep journald quiet: no query strings
        pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8097)
    a = ap.parse_args()
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
