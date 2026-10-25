"""Live checks against the real archives. Skipped by default; run: uv run pytest -m integration"""

from __future__ import annotations

import os

import pytest

from astromcp.whats_here import whats_here

pytestmark = pytest.mark.integration


@pytest.mark.skipif(not os.environ.get("TNS_API_KEY"), reason="needs TNS bot credentials")
def test_live_at2026agtq() -> None:
    r = whats_here(40.228980, 12.601026, 5)
    assert r["verdict"] == "known transient"
    assert any("2026agtq" in e for e in r["evidence"])


def test_live_toi2330() -> None:
    r = whats_here(172.85872, -41.68953, 5)
    assert "known TESS object of interest" in r["labels"]


def test_live_empty_sky() -> None:
    r = whats_here(200.5, -20.3, 3)
    assert r["verdict"] in ("nothing known", "star", "known object")
