"""HTTP layer: timeouts, retries with backoff, HTTP 429 handling, short-lived disk cache,
per-host circuit breakers and secret redaction."""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from . import __version__

USER_AGENT = f"AstroMCP/{__version__} (+https://github.com/louisperner/AstroMCP)"
DEFAULT_TTL = 15 * 60  # seconds


class SourceError(RuntimeError):
    """A remote archive failed or answered something unusable. The message is safe to show."""


def cache_dir() -> Path:
    d = Path(os.environ.get("ASTROMCP_CACHE_DIR") or Path.home() / ".cache" / "astromcp")
    d.mkdir(parents=True, exist_ok=True)
    return d


_SECRET_RE = re.compile(r"(api_key=)[^&\s\"']+", re.IGNORECASE)


def redact(text: str) -> str:
    """Remove API keys (and the TNS key from the environment) from any text."""
    text = _SECRET_RE.sub(r"\1***", text)
    key = os.environ.get("TNS_API_KEY")
    if key:
        text = text.replace(key, "***")
    return text


class CircuitBreaker:
    """After `limit` consecutive failures, fail fast for `cooldown` seconds.
    Without it, a VizieR outage costs ~90 s per query."""

    def __init__(self, limit: int = 3, cooldown: float = 120.0) -> None:
        self.limit = limit
        self.cooldown = cooldown
        self.failures = 0
        self.opened_at = 0.0
        self._lock = threading.Lock()

    @property
    def open(self) -> bool:
        with self._lock:
            if self.failures < self.limit:
                return False
            if time.time() - self.opened_at > self.cooldown:
                self.failures = self.limit - 1  # half-open: allow one try
                return False
            return True

    def record(self, ok: bool) -> None:
        with self._lock:
            if ok:
                self.failures = 0
            else:
                self.failures += 1
                if self.failures >= self.limit:
                    self.opened_at = time.time()


_breakers: dict[str, CircuitBreaker] = {}
_breakers_lock = threading.Lock()


def breaker(host: str) -> CircuitBreaker:
    with _breakers_lock:
        return _breakers.setdefault(host, CircuitBreaker())


def _retry_after(err: urllib.error.HTTPError, attempt: int) -> float:
    for h in ("Retry-After", "x-rate-limit-reset", "x-cone-rate-limit-reset"):
        try:
            return min(float(str(err.headers.get(h, ""))) + 1, 60.0)
        except (TypeError, ValueError):
            continue
    backoff: float = 5.0 * (2**attempt)
    return min(backoff, 60.0)


def _transport(req: urllib.request.Request, timeout: float) -> bytes:
    """The only function that touches the network (tests replace it)."""
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data: bytes = r.read()
        return data


def fetch(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    ttl: float = DEFAULT_TTL,
    timeout: float = 30.0,
    retries: int = 3,
    max_429: int = 2,
) -> bytes:
    """GET (or POST when `data` is given) with cache, retries and a per-host circuit breaker."""
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    key = hashlib.sha256(url.encode() + b"\0" + (body or b"")).hexdigest()
    path = cache_dir() / "http" / key[:2] / key
    if ttl > 0 and path.exists() and time.time() - path.stat().st_mtime < ttl:
        return path.read_bytes()

    host = urllib.parse.urlsplit(url).netloc
    br = breaker(host)
    if br.open:
        raise SourceError(f"{host} is failing repeatedly; skipped for a couple of minutes")
    hdrs = {"User-Agent": USER_AGENT, **(headers or {})}
    attempt = n429 = 0
    while True:
        try:
            content = _transport(urllib.request.Request(url, data=body, headers=hdrs), timeout)
            br.record(True)
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and n429 < max_429:
                time.sleep(_retry_after(e, n429))
                n429 += 1
                continue
            if e.code == 429:
                raise SourceError(f"{host} rate limit (HTTP 429); try again later") from None
            if 400 <= e.code < 500:
                raise SourceError(f"{host} answered HTTP {e.code}") from None
            attempt += 1
            if attempt >= retries:
                br.record(False)
                raise SourceError(f"{host} answered HTTP {e.code}") from None
        except Exception as e:  # network errors, timeouts
            attempt += 1
            if attempt >= retries:
                br.record(False)
                raise SourceError(redact(f"{host} unreachable: {e.__class__.__name__}: {e}")) from None
        time.sleep(2 ** (attempt - 1))

    if ttl > 0:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(content)
        os.replace(tmp, path)
    return content


def fetch_json(url: str, **kw: Any) -> Any:
    raw = fetch(url, **kw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        host = urllib.parse.urlsplit(url).netloc
        raise SourceError(f"{host} returned non-JSON content") from None


def fetch_text(url: str, **kw: Any) -> str:
    return fetch(url, **kw).decode("utf-8", "replace")
