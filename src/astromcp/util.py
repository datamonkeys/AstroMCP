"""Small astronomy helpers."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any


def validate_position(ra: float, dec: float, radius_arcsec: float | None = None, max_radius: float = 3600) -> None:
    if not (0 <= ra < 360):
        raise ValueError("ra must be in degrees, 0 <= ra < 360")
    if not (-90 <= dec <= 90):
        raise ValueError("dec must be in degrees, -90 <= dec <= 90")
    if radius_arcsec is not None and not (0 < radius_arcsec <= max_radius):
        raise ValueError(f"radius_arcsec must be in (0, {max_radius}]")


def sep_arcsec(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    """Great-circle separation (haversine) in arcsec."""
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    a = math.sin((d2 - d1) / 2) ** 2 + math.cos(d1) * math.cos(d2) * math.sin((r2 - r1) / 2) ** 2
    return math.degrees(2 * math.asin(min(1.0, math.sqrt(a)))) * 3600


def sexa_to_deg(value: str, hours: bool) -> float:
    """'hh:mm:ss.s' / 'dd:mm:ss.s' (or plain decimal) to degrees."""
    s = value.strip()
    if ":" not in s and " " not in s:
        return float(s)
    parts = s.replace(":", " ").split()
    sign = -1.0 if parts[0].startswith("-") else 1.0
    d, m, sec = (abs(float(parts[0])), float(parts[1]), float(parts[2]) if len(parts) > 2 else 0.0)
    deg = d + m / 60 + sec / 3600
    return sign * deg * (15 if hours else 1)


def num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def rnd(v: Any, n: int = 4) -> float | None:
    f = num(v)
    return None if f is None else round(f, n)


def iso_to_jd(epoch_iso: str) -> float:
    s = epoch_iso.strip().replace("Z", "+00:00")
    t = datetime.fromisoformat(s)
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return t.timestamp() / 86400 + 2440587.5


def mjd_now() -> float:
    return datetime.now(UTC).timestamp() / 86400 + 40587


def ab_mag_from_njy(flux: float | None) -> float | None:
    return None if flux is None or flux <= 0 else round(31.4 - 2.5 * math.log10(flux), 3)
