"""Offline test harness: every HTTP request is answered from tests/fixtures."""

from __future__ import annotations

import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from astromcp import net
from astromcp.sources import tns

FIXTURES = Path(__file__).parent / "fixtures"


class FakeNet:
    """Routes requests to fixture files by URL substrings; records calls."""

    def __init__(self) -> None:
        self.routes: list[tuple[Callable[[str, bytes], bool], bytes | Exception]] = []
        self.calls: list[tuple[str, bytes]] = []

    def add(self, match: str | Callable[[str, bytes], bool], fixture: str | bytes | Exception) -> None:
        fn = match if callable(match) else (lambda u, b, m=match: m in u)
        body: bytes | Exception = (FIXTURES / fixture).read_bytes() if isinstance(fixture, str) else fixture
        self.routes.insert(0, (fn, body))

    def __call__(self, req: urllib.request.Request, timeout: float) -> bytes:
        url = req.full_url
        data = req.data if isinstance(req.data, bytes) else b""
        self.calls.append((url, data))
        for fn, body in self.routes:
            if fn(url, data):
                if isinstance(body, Exception):
                    raise body
                return body
        raise AssertionError(f"unexpected request in offline test: {url}")


@pytest.fixture(autouse=True)
def offline(request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeNet]:
    fake = FakeNet()
    if request.node.get_closest_marker("integration") is not None:
        yield fake  # live test: real network, real credentials, real cache
        return
    monkeypatch.setenv("ASTROMCP_CACHE_DIR", str(tmp_path / "cache"))
    for k in ("TNS_BOT_ID", "TNS_BOT_NAME", "TNS_API_KEY", "TNS_PUBLIC_CSV"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(tns, "CONE_INTERVAL", 0.0)
    monkeypatch.setattr(net.time, "sleep", lambda s: None)
    net._breakers.clear()
    tns._index.update({"mtime": 0.0, "index": None})
    monkeypatch.setattr(net, "_transport", fake)
    yield fake


@pytest.fixture
def tns_creds(monkeypatch: pytest.MonkeyPatch) -> str:
    key = "SECRETKEY1234567890"
    monkeypatch.setenv("TNS_BOT_ID", "999")
    monkeypatch.setenv("TNS_BOT_NAME", "test_bot")
    monkeypatch.setenv("TNS_API_KEY", key)
    return key
