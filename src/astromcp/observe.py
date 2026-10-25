"""'What to observe tonight': recent, bright, still-unclassified TNS transients that are
observable from a given site tonight — a follow-up / spectroscopic classification planner.

Positions of the Sun and Moon use the low-precision formulas of the Astronomical Almanac
(errors of a few arcminutes, plenty for planning). No astropy dependency.
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Any

from .sources import tns

RAD = math.pi / 180


def julian_date(t: dt.datetime) -> float:
    return t.replace(tzinfo=dt.UTC).timestamp() / 86400 + 2440587.5 if t.tzinfo is None else t.timestamp() / 86400 + 2440587.5


def gmst_deg(jd: float) -> float:
    d = jd - 2451545.0
    return (280.46061837 + 360.98564736629 * d) % 360


def altitude_deg(ra: float, dec: float, lat: float, lon: float, jd: float) -> float:
    ha = (gmst_deg(jd) + lon - ra) * RAD
    s = math.sin(lat * RAD) * math.sin(dec * RAD) + math.cos(lat * RAD) * math.cos(dec * RAD) * math.cos(ha)
    return math.degrees(math.asin(max(-1.0, min(1.0, s))))


def sun_radec(jd: float) -> tuple[float, float]:
    n = jd - 2451545.0
    L = (280.460 + 0.9856474 * n) % 360
    g = (357.528 + 0.9856003 * n) % 360 * RAD
    lam = (L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)) * RAD
    eps = (23.439 - 0.0000004 * n) * RAD
    ra = math.degrees(math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))) % 360
    dec = math.degrees(math.asin(math.sin(eps) * math.sin(lam)))
    return ra, dec


def moon_radec(jd: float) -> tuple[float, float]:
    t = (jd - 2451545.0) / 36525
    lam = (
        218.32
        + 481267.881 * t
        + 6.29 * math.sin((135.0 + 477198.87 * t) * RAD)
        - 1.27 * math.sin((259.3 - 413335.36 * t) * RAD)
        + 0.66 * math.sin((235.7 + 890534.22 * t) * RAD)
        + 0.21 * math.sin((269.9 + 954397.74 * t) * RAD)
        - 0.19 * math.sin((357.5 + 35999.05 * t) * RAD)
        - 0.11 * math.sin((186.5 + 966404.03 * t) * RAD)
    ) * RAD
    beta = (
        5.13 * math.sin((93.3 + 483202.02 * t) * RAD)
        + 0.28 * math.sin((228.2 + 960400.89 * t) * RAD)
        - 0.28 * math.sin((318.3 + 6003.15 * t) * RAD)
        - 0.17 * math.sin((217.6 - 407332.21 * t) * RAD)
    ) * RAD
    eps = 23.439 * RAD
    x = math.cos(beta) * math.cos(lam)
    y = math.cos(eps) * math.cos(beta) * math.sin(lam) - math.sin(eps) * math.sin(beta)
    z = math.sin(eps) * math.cos(beta) * math.sin(lam) + math.cos(eps) * math.sin(beta)
    return math.degrees(math.atan2(y, x)) % 360, math.degrees(math.asin(z))


def separation_deg(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    c = math.sin(dec1 * RAD) * math.sin(dec2 * RAD) + math.cos(dec1 * RAD) * math.cos(dec2 * RAD) * math.cos((ra1 - ra2) * RAD)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def night_grid(lat: float, lon: float, date: dt.date, sun_limit: float = -12.0, step_min: int = 10) -> list[float]:
    """JDs (every step_min) between the evening and morning when the Sun is below sun_limit
    (nautical twilight by default), for the night starting on the local evening of `date`."""
    local_noon_utc = dt.datetime(date.year, date.month, date.day, 12, tzinfo=dt.UTC) - dt.timedelta(hours=lon / 15)
    jd0 = julian_date(local_noon_utc)
    grid = []
    for i in range(0, 24 * 60 // step_min + 1):
        jd = jd0 + i * step_min / 1440
        ra, dec = sun_radec(jd)
        if altitude_deg(ra, dec, lat, lon, jd) < sun_limit:
            grid.append(jd)
    return grid


def moon_illumination(jd: float) -> float:
    sra, sdec = sun_radec(jd)
    mra, mdec = moon_radec(jd)
    elong = separation_deg(sra, sdec, mra, mdec)
    return (1 - math.cos(elong * RAD)) / 2


def _iso(jd: float) -> str:
    return dt.datetime.fromtimestamp((jd - 2440587.5) * 86400, tz=dt.UTC).strftime("%Y-%m-%dT%H:%MZ")


def observe_tonight(
    lat: float,
    lon: float,
    date: str | None = None,
    mag_limit: float = 18.5,
    max_age_days: float = 21,
    min_altitude: float = 30.0,
    min_moon_sep: float = 20.0,
    include_classified: bool = False,
    limit: int = 30,
) -> dict[str, Any]:
    idx = tns.archive_index()
    if idx is None:
        raise ValueError("TNS public archive unavailable (set TNS bot credentials so it can be downloaded)")
    day = dt.date.fromisoformat(date) if date else dt.datetime.now(dt.UTC).date()
    grid = night_grid(lat, lon, day)
    if not grid:
        return {
            "site": {"lat": lat, "lon": lon},
            "date": day.isoformat(),
            "targets": [],
            "note": "no astronomical night at this site/date (Sun never below -12 deg)",
        }
    mid = grid[len(grid) // 2]
    mra, mdec = moon_radec(mid)
    illum = moon_illumination(mid)
    today = dt.datetime.combine(day, dt.time(12), tzinfo=dt.UTC)
    alvos = []
    for o in idx.by_name.values():
        if (o.get("type") and not include_classified) or o.get("discovery_mag") is None:
            continue
        if o["discovery_mag"] > mag_limit:
            continue
        try:
            disc = dt.datetime.fromisoformat(str(o["discovery_date"]).replace(" ", "T")[:19]).replace(tzinfo=dt.UTC)
        except ValueError:
            continue
        age = (today - disc).total_seconds() / 86400
        if not (0 <= age <= max_age_days):
            continue
        alts = [altitude_deg(o["ra"], o["dec"], lat, lon, jd) for jd in grid]
        acima = [jd for jd, a in zip(grid, alts) if a >= min_altitude]
        if not acima:
            continue
        moon_sep = separation_deg(o["ra"], o["dec"], mra, mdec)
        if moon_sep < min_moon_sep:
            continue
        horas = len(acima) * 10 / 60
        imax = max(range(len(alts)), key=lambda i: alts[i])
        # priority: brighter and younger first, then more time above the altitude limit
        prioridade = (mag_limit - o["discovery_mag"]) * 2 + max(0.0, 10 - age) * 0.5 + min(horas, 6) * 0.3
        alvos.append(
            {
                "name": o["name"],
                "ra": o["ra"],
                "dec": o["dec"],
                "type": o.get("type"),
                "discovery_mag": o["discovery_mag"],
                "age_days": round(age, 1),
                "max_altitude_deg": round(alts[imax], 1),
                "transit_utc": _iso(grid[imax]),
                "window_utc": [_iso(acima[0]), _iso(acima[-1])],
                "hours_above_limit": round(horas, 1),
                "moon_sep_deg": round(moon_sep, 1),
                "reporting_group": o.get("reporting_group"),
                "internal_names": o.get("internal_names"),
                "url": o.get("url"),
                "priority": round(prioridade, 2),
            }
        )
    alvos.sort(key=lambda a: -a["priority"])
    return {
        "site": {"lat": lat, "lon": lon},
        "night_utc": [_iso(grid[0]), _iso(grid[-1])],
        "moon": {"illumination": round(illum, 2), "ra": round(mra, 2), "dec": round(mdec, 2)},
        "criteria": {
            "mag_limit": mag_limit,
            "max_age_days": max_age_days,
            "min_altitude": min_altitude,
            "min_moon_sep": min_moon_sep,
            "unclassified_only": not include_classified,
        },
        "n_matching": len(alvos),
        "targets": alvos[:limit],
        "note": "discovery magnitude from TNS (current brightness may differ); archive refreshed daily at 00:00 UTC",
    }
