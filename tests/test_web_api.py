from __future__ import annotations

from astromcp import web_api


def test_answer_rejects_bad_query() -> None:
    assert web_api.answer({"ra": ["999"], "dec": ["0"]})[0] == 400
    assert web_api.answer({"dec": ["0"]})[0] == 400
    assert web_api.answer({"ra": ["10"], "dec": ["0"], "radius": ["500"]})[0] == 400


def test_answer_drops_details(monkeypatch: object) -> None:
    monkeypatch.setattr(  # type: ignore[attr-defined]
        web_api, "whats_here", lambda ra, dec, r, e: {"verdict": "nothing known", "details": {"x": 1}}
    )
    code, body = web_api.answer({"ra": ["10"], "dec": ["-5"]})
    assert code == 200 and body == {"verdict": "nothing known"}


def test_rate_limit_per_ip() -> None:
    web_api._hits.clear()
    assert all(web_api._allowed("1.2.3.4") for _ in range(web_api.MAX_PER_MINUTE))
    assert not web_api._allowed("1.2.3.4")
    assert web_api._allowed("5.6.7.8")


def test_tonight_rejects_bad_query() -> None:
    assert web_api.answer_tonight({"lat": ["99"], "lon": ["0"]})[0] == 400
    assert web_api.answer_tonight({"lon": ["0"]})[0] == 400
    assert web_api.answer_tonight({"lat": ["-25"], "lon": ["-49"], "mag_limit": ["30"]})[0] == 400


def test_tonight_passes_through(monkeypatch: object) -> None:
    monkeypatch.setattr(  # type: ignore[attr-defined]
        web_api, "observe_tonight", lambda lat, lon, date, mag_limit, limit: {"targets": [], "lat": lat, "limit": limit}
    )
    code, body = web_api.answer_tonight({"lat": ["-25.4"], "lon": ["-49.3"]})
    assert code == 200 and body["lat"] == -25.4 and body["limit"] == 40
