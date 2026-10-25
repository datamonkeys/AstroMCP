from __future__ import annotations

import json
import urllib.error
from email.message import Message

import pytest
from conftest import FIXTURES, FakeNet

from astromcp import net
from astromcp.sources import alerce, cutouts, exofop, fink, simbad, skybot, tess, tns, vizier

WASP = (172.85872, -41.68953)
AGTQ = (40.228980, 12.601026)


def test_simbad_cone(offline: FakeNet) -> None:
    offline.add("sim-tap", "simbad_wasp128.csv")
    r = simbad.cone(*WASP, 5)
    assert r["count"] == 2
    assert r["objects"][0]["main_id"] == "WASP-128"
    assert r["objects"][0]["otype"] == "*"


def test_vsx(offline: FakeNet) -> None:
    offline.add("B%2Fvsx", "vsx_wasp128.tsv")
    r = vizier.vsx(*WASP, 5)
    assert r["count"] == 1
    assert r["objects"][0]["name"] == "WASP-128"
    assert r["objects"][0]["type"].startswith("EA")


def test_vsx_empty(offline: FakeNet) -> None:
    offline.add("B%2Fvsx", "vsx_empty.tsv")
    assert vizier.vsx(*AGTQ, 5)["count"] == 0


def test_gaia(offline: FakeNet) -> None:
    offline.add("gaiadr3", "gaia_wasp128.tsv")
    r = vizier.gaia(*WASP, 5)
    n = r["nearest"]
    assert n["source_id"] == "5382697351745548416"
    assert n["likely_star"] is True
    assert n["parallax_snr"] > 100


def test_tess_eb(offline: FakeNet) -> None:
    offline.add("tess-ebs", "vizier_tess_eb.tsv")
    ebs = vizier.tess_eb(175.108299, -6.10253, 30)
    assert ebs[0]["tic"] == "0185259483"
    assert ebs[0]["period_days"] == pytest.approx(0.310564)


def test_exofop_by_tic_and_position(offline: FakeNet) -> None:
    offline.add("download_toi", "exofop_toi.csv")
    offline.add("download_ctoi", "exofop_ctoi.csv")
    by_tic = exofop.find(tic=180991313)
    assert {o["id"] for o in by_tic["objects"]} >= {"TOI-2330.01"}
    by_pos = exofop.find(ra=WASP[0], dec=WASP[1], radius_arcsec=5)
    assert any(o["id"] == "TOI-2330.01" and o["sep_arcsec"] < 1 for o in by_pos["objects"])
    assert exofop.find(ra=10.0, dec=10.0, radius_arcsec=5)["count"] == 0


def test_tess_known_from_tic(offline: FakeNet) -> None:
    offline.add("IV%2F39%2Ftic82", "vizier_tic.tsv")
    offline.add("download_toi", "exofop_toi.csv")
    offline.add("download_ctoi", "exofop_ctoi.csv")
    offline.add("tess-ebs", "vsx_empty.tsv")
    r = tess.known(tic=180991313)
    assert r["ra"] == pytest.approx(172.8587, abs=1e-3)
    assert "TOI-2330.01" in r["summary"]
    assert r["tess_eb"] == []


def test_alerce_cone(offline: FakeNet) -> None:
    offline.add("objects/?", "alerce_cone_agtq.json")
    r = alerce.objects_near(*AGTQ, 5)
    assert r["objects"][0]["oid"] == "ZTF26acatcla"


def test_alerce_lightcurve(offline: FakeNet) -> None:
    offline.add("/lightcurve", "alerce_lightcurve.json")
    r = alerce.lightcurve("ZTF26acatcla")
    assert r["n_detections"] >= 10
    assert set(r["per_band"]) <= {"g", "r", "i"}
    assert r["detections"][0]["magpsf_corr"] is not None
    assert r["non_detections"]["count"] > 0
    assert r["non_detections"]["last_before_first_detection"]["limit_mag"] > 15


def test_alerce_bad_oid() -> None:
    with pytest.raises(ValueError):
        alerce.lightcurve("not-an-oid")


def test_fink_object(offline: FakeNet) -> None:
    offline.add("/sources", "fink_sources.json")
    r = fink.obj(170028485643862094)
    assert r["n_sources"] > 10
    assert r["peak_mag_ab"] is not None
    assert "Difference" in r["cutouts"]["difference"]


def test_fink_recent_uses_iso_startdate(offline: FakeNet) -> None:
    offline.add("/tags", "fink_tags.json")
    r = fink.recent("most_likely_sn", 3)
    assert r["count"] > 0
    url = offline.calls[0][0]
    assert "startdate=20" in url and "%3A" in url  # ISO with time, not MJD


def test_fink_recent_empty_reports_latest_night(offline: FakeNet) -> None:
    offline.add("/tags", b"[]")
    offline.add("/statistics", "fink_statistics.json")
    r = fink.recent("hostless_candidate", 1)
    assert r["count"] == 0 and "2026" in r["note"]


def test_fink_bad_tag() -> None:
    with pytest.raises(ValueError):
        fink.recent("nope", 1)


def test_skybot_parse_and_query(offline: FakeNet) -> None:
    offline.add("skybot", "skybot_sample.txt")
    r = skybot.cone(*AGTQ, "2026-10-20T06:00:00", 30)
    assert r["count"] == 2
    assert r["objects"][0]["name"] == "1993 AB"
    assert r["objects"][1]["number"] is None
    assert "-ep=2461333.75" in offline.calls[0][0]


def test_skybot_none(offline: FakeNet) -> None:
    offline.add("skybot", "skybot_none.txt")
    assert skybot.cone(*AGTQ, "2026-10-20", 30)["count"] == 0


def test_skybot_html_error(offline: FakeNet) -> None:
    offline.add("skybot", b"<html><body>502 Bad Gateway</body></html>")
    with pytest.raises(net.SourceError):
        skybot.cone(*AGTQ, "2026-10-20", 30)


def test_cutouts() -> None:
    u = cutouts.urls(*AGTQ, 60)
    assert "legacysurvey.org" in u["legacy_survey_jpeg"] and "size=229" in u["legacy_survey_jpeg"]
    assert "ps1images" in u["panstarrs_jpeg"]
    assert "dss_search" in u["dss_gif"]


# ------------------------------------------------------------------ TNS


def test_tns_api_search_and_enrichment(offline: FakeNet, tns_creds: str) -> None:
    offline.add("/api/get/search", "tns_search_agtq.json")
    offline.add("/api/get/object", "tns_object_agtq.json")
    offline.add("tns_public_objects", "tns_public_objects.csv.zip")
    r = tns.search(*AGTQ, 5)
    assert r["source"] == "TNS API"
    assert r["objects"][0]["name"] == "AT 2026agtq"
    assert r["objects"][0]["sep_arcsec"] < 1
    assert json.dumps(r).find(tns_creds) == -1


def test_tns_object_api(offline: FakeNet, tns_creds: str) -> None:
    offline.add("/api/get/object", "tns_object_agtq.json")
    r = tns.get_object("AT 2026agtq")
    assert r["name"] == "AT 2026agtq"
    assert r["ra"] == pytest.approx(40.22898, abs=1e-3)
    sent = offline.calls[0][1].decode()
    assert "2026agtq" in sent and "AT+2026" not in sent


def test_tns_archive_fallback_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TNS_PUBLIC_CSV", str(FIXTURES / "tns_public_objects.csv.zip"))
    r = tns.search(41.171781, -5.379759, 3)
    assert r["objects"][0]["name"] == "AT 2026agsv"
    assert "archive" in r["source"]
    assert tns.get_object("2026agsv")["name"] == "AT 2026agsv"


def test_tns_unavailable_without_anything() -> None:
    with pytest.raises(net.SourceError, match="no TNS credentials"):
        tns.search(*AGTQ, 5)


def test_tns_api_error_never_leaks_key(offline: FakeNet, tns_creds: str) -> None:
    offline.add("/api/get/search", OSError(f"boom api_key={tns_creds}"))
    offline.add("tns_public_objects", urllib.error.URLError("down"))
    with pytest.raises(net.SourceError) as e:
        tns.search(*AGTQ, 5)
    assert tns_creds not in str(e.value)


def test_tns_bad_name() -> None:
    with pytest.raises(ValueError):
        tns.get_object("hello")


# ------------------------------------------------------------------ net layer


def _http_error(code: int, headers: dict[str, str] | None = None) -> urllib.error.HTTPError:
    m = Message()
    for k, v in (headers or {}).items():
        m[k] = v
    return urllib.error.HTTPError("https://x.test/", code, "err", m, None)


def test_429_retries_then_succeeds(offline: FakeNet) -> None:
    seq: list[bytes | Exception] = [_http_error(429, {"Retry-After": "1"}), b"ok"]

    def transport(req: object, timeout: float) -> bytes:
        item = seq.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    import astromcp.net as n

    n._transport = transport  # type: ignore[assignment]  # restored by monkeypatch teardown
    assert net.fetch("https://api.alerce.online/x", ttl=0) == b"ok"


def test_429_persistent_gives_clear_error(offline: FakeNet) -> None:
    offline.add("alerce", _http_error(429))
    with pytest.raises(net.SourceError, match="rate limit"):
        net.fetch("https://api.alerce.online/y", ttl=0)


def test_cache_hit_avoids_network(offline: FakeNet) -> None:
    offline.add("vizier", b"data")
    assert net.fetch("https://vizier.cds.unistra.fr/a", ttl=60) == b"data"
    assert net.fetch("https://vizier.cds.unistra.fr/a", ttl=60) == b"data"
    assert len(offline.calls) == 1


def test_circuit_breaker_opens(offline: FakeNet) -> None:
    offline.add("vizier", _http_error(503))
    for _ in range(3):
        with pytest.raises(net.SourceError):
            net.fetch("https://vizier.cds.unistra.fr/b", ttl=0, retries=1)
    n = len(offline.calls)
    with pytest.raises(net.SourceError, match="failing repeatedly"):
        net.fetch("https://vizier.cds.unistra.fr/c", ttl=0)
    assert len(offline.calls) == n


def test_redact(tns_creds: str) -> None:
    assert tns_creds not in net.redact(f"x api_key={tns_creds}&y=1 {tns_creds}")
