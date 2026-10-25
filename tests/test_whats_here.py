from __future__ import annotations

import json

from conftest import FakeNet

from astromcp import server
from astromcp.whats_here import whats_here


def _common(f: FakeNet) -> None:
    f.add("download_toi", "exofop_toi.csv")
    f.add("download_ctoi", "exofop_ctoi.csv")


def test_known_transient(offline: FakeNet, tns_creds: str) -> None:
    _common(offline)
    offline.add("/api/get/search", "tns_search_agtq.json")
    offline.add("/api/get/object", "tns_object_agtq.json")
    offline.add("tns_public_objects", "tns_public_objects.csv.zip")
    offline.add("sim-tap", "simbad_empty.csv")
    offline.add("B%2Fvsx", "vsx_empty.tsv")
    offline.add("gaiadr3", "gaia_empty.tsv")
    offline.add("objects/?", "alerce_cone_agtq.json")
    offline.add("skybot", "skybot_none.txt")
    r = whats_here(40.22898, 12.601026, 5, "2026-10-20T06:00:00")
    assert r["verdict"] == "known transient"
    assert any("AT 2026agtq" in e for e in r["evidence"])
    assert r["sources_failed"] == []
    assert tns_creds not in json.dumps(r)


def test_toi_and_variable(offline: FakeNet) -> None:
    _common(offline)
    offline.add("sim-tap", "simbad_wasp128.csv")
    offline.add("B%2Fvsx", "vsx_wasp128.tsv")
    offline.add("gaiadr3", "gaia_wasp128.tsv")
    offline.add("objects/?", "alerce_cone_empty.json")
    r = whats_here(172.85872, -41.68953, 5)
    assert r["verdict"] == "known TESS object of interest"
    assert {"known variable", "star"} <= set(r["labels"])
    assert r["sources_failed"] == ["tns"]  # no credentials, no archive
    assert "tns" in r["caveat"]


def test_nothing_known_with_failure(offline: FakeNet) -> None:
    _common(offline)
    offline.add("sim-tap", "simbad_empty.csv")
    offline.add("B%2Fvsx", "vsx_empty.tsv")
    offline.add("gaiadr3", OSError("network down"))
    offline.add("objects/?", "alerce_cone_empty.json")
    r = whats_here(10.0, 10.0, 5)
    assert r["verdict"] == "nothing known"
    assert "gaia" in r["sources_failed"]


def test_archive_only_tns_is_not_a_clean_nothing_known(offline: FakeNet, monkeypatch: object) -> None:
    """Without credentials TNS falls back to the daily archive, which misses objects
    reported today (seen live with AT 2025andj): say so, and still report the ZTF source."""
    from astromcp.sources import tns

    _common(offline)
    offline.add("sim-tap", "simbad_empty.csv")
    offline.add("B%2Fvsx", "vsx_empty.tsv")
    offline.add("gaiadr3", "gaia_empty.tsv")
    offline.add("objects/?", "alerce_cone_agtq.json")
    monkeypatch.setattr(  # type: ignore[attr-defined]
        tns, "search", lambda ra, dec, r: {"source": "TNS public archive (daily)", "objects": []}
    )
    r = whats_here(40.22898, 12.601026, 5)
    assert r["verdict"] == "known ZTF alert source"
    assert "daily public archive" in r["caveat"]


def test_server_tools_validate_input() -> None:
    assert "error" in server.whats_here(400.0, 0.0)
    assert "error" in server.gaia(10.0, 95.0)
    assert "error" in server.ztf_lightcurve("bad")
    assert "error" in server.tess_known()


async def test_tools_registered() -> None:
    tools = {t.name for t in await server.mcp.list_tools()}
    assert tools == {
        "whats_here", "tns_object", "tns_search", "ztf_lightcurve", "ztf_objects_near", "rubin_object",
        "rubin_recent", "simbad", "vsx", "gaia", "tess_known", "asteroids_at", "cutout_urls", "observe_tonight",
    }  # fmt: skip
