from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from astromcp import observe
from astromcp.sources import tns


def _jd(y: int, m: int, d: int, h: float = 0.0) -> float:
    return observe.julian_date(dt.datetime(y, m, d, tzinfo=dt.UTC) + dt.timedelta(hours=h))


def test_julian_date_j2000() -> None:
    assert _jd(2000, 1, 1, 12) == pytest.approx(2451545.0, abs=1e-6)


def test_sun_near_equinox_and_solstice() -> None:
    _, dec_eq = observe.sun_radec(_jd(2026, 3, 20, 14))
    _, dec_sol = observe.sun_radec(_jd(2026, 6, 21, 8))
    assert abs(dec_eq) < 0.5
    assert dec_sol == pytest.approx(23.44, abs=0.1)


def test_polaris_altitude_equals_latitude() -> None:
    # Polaris (RA 37.95, Dec +89.26) sits ~at the observer's latitude at any time.
    for h in (0, 6, 12, 18):
        alt = observe.altitude_deg(37.95, 89.26, 45.0, 10.0, _jd(2026, 10, 25, h))
        assert alt == pytest.approx(45.0, abs=1.0)


def test_moon_full_on_2026_10_26() -> None:
    # Full Moon of October 2026: 26 Oct ~04:12 UTC.
    assert observe.moon_illumination(_jd(2026, 10, 26, 4.2)) > 0.98
    assert observe.moon_illumination(_jd(2026, 11, 9, 0)) < 0.05  # new Moon ~9 Nov


def test_no_night_at_polar_summer() -> None:
    assert observe.night_grid(78.2, 15.6, dt.date(2026, 6, 21)) == []


class _FakeIndex:
    def __init__(self, objs: list[dict[str, Any]]) -> None:
        self.by_name = {o["name"]: o for o in objs}


def test_observe_tonight_filters_and_ranks(monkeypatch: pytest.MonkeyPatch) -> None:
    base = {"type": None, "reporting_group": "ATLAS", "internal_names": None, "url": "u"}
    objs = [
        {**base, "name": "AT 2026aaa", "ra": 30.0, "dec": -30.0, "discovery_mag": 16.0, "discovery_date": "2026-10-23 03:00:00"},
        {**base, "name": "AT 2026bbb", "ra": 30.0, "dec": -30.0, "discovery_mag": 18.0, "discovery_date": "2026-10-23 03:00:00"},
        {
            **base,
            "name": "AT 2026faint",
            "ra": 30.0,
            "dec": -30.0,
            "discovery_mag": 19.5,
            "discovery_date": "2026-10-23 03:00:00",
        },
        {
            **base,
            "name": "SN 2026cls",
            "type": "SN Ia",
            "ra": 30.0,
            "dec": -30.0,
            "discovery_mag": 16.0,
            "discovery_date": "2026-10-23 03:00:00",
        },
        {**base, "name": "AT 2026old", "ra": 30.0, "dec": -30.0, "discovery_mag": 16.0, "discovery_date": "2026-08-01 03:00:00"},
        {**base, "name": "AT 2026north", "ra": 30.0, "dec": 80.0, "discovery_mag": 15.0, "discovery_date": "2026-10-23 03:00:00"},
    ]
    monkeypatch.setattr(tns, "archive_index", lambda: _FakeIndex(objs))
    # night starting 2026-11-08 (new Moon), site at 30 S: RA 30 / Dec -30 culminates near zenith
    r = observe.observe_tonight(-30.0, -70.0, "2026-11-08", min_moon_sep=0)
    names = [t["name"] for t in r["targets"]]
    assert names == ["AT 2026aaa", "AT 2026bbb"]  # brighter first; faint, classified, old, never-up excluded
    assert r["targets"][0]["max_altitude_deg"] > 80
    assert r["moon"]["illumination"] < 0.1
