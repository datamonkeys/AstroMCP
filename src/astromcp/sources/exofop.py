"""ExoFOP-TESS TOI and CTOI tables (downloaded whole and cached for 12 h)."""

from __future__ import annotations

import csv
import io
from typing import Any

from .. import net
from ..util import rnd, sep_arcsec, sexa_to_deg

TOI_URL = "https://exofop.ipac.caltech.edu/tess/download_toi.php?sort=toi&output=csv"
CTOI_URL = "https://exofop.ipac.caltech.edu/tess/download_ctoi.php?sort=ctoi&output=csv"
TTL = 12 * 3600


def _rows(url: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(net.fetch_text(url, ttl=TTL, timeout=90))))


def _pos(row: dict[str, str]) -> tuple[float, float] | None:
    try:
        return sexa_to_deg(row["RA"], hours=True), sexa_to_deg(row["Dec"], hours=False)
    except (KeyError, ValueError, IndexError):
        return None


def _compact(row: dict[str, str], kind: str, sep: float | None) -> dict[str, Any]:
    ident = row.get("TOI") if kind == "TOI" else row.get("CTOI")
    out: dict[str, Any] = {
        "kind": kind,
        "id": f"{kind}-{ident}",
        "tic": row.get("TIC ID"),
        "period_days": rnd(row.get("Period (days)"), 6),
        "depth_ppm": rnd(row.get("Depth (ppm)") or row.get("Depth ppm"), 1),
        "planet_radius_re": rnd(row.get("Planet Radius (R_Earth)"), 2),
        "tess_mag": rnd(row.get("TESS Mag"), 3),
    }
    if kind == "TOI":
        out["tfopwg_disposition"] = row.get("TFOPWG Disposition") or None
        out["planet_name"] = row.get("Planet Name") or None
    else:
        out["user_disposition"] = row.get("User Disposition") or None
        out["promoted_to_toi"] = row.get("Promoted to TOI") or None
    if sep is not None:
        out["sep_arcsec"] = round(sep, 2)
    out["url"] = f"https://exofop.ipac.caltech.edu/tess/target.php?id={row.get('TIC ID')}"
    return out


def find(
    tic: int | None = None, ra: float | None = None, dec: float | None = None, radius_arcsec: float = 30.0
) -> dict[str, Any]:
    """TOIs and CTOIs matching a TIC id and/or lying within radius of a position."""
    found: list[dict[str, Any]] = []
    for kind, url in (("TOI", TOI_URL), ("CTOI", CTOI_URL)):
        for row in _rows(url):
            sep = None
            if ra is not None and dec is not None:
                p = _pos(row)
                if p is not None:
                    sep = sep_arcsec(ra, dec, p[0], p[1])
            by_tic = tic is not None and row.get("TIC ID", "").strip() == str(tic)
            by_pos = sep is not None and sep <= radius_arcsec
            if by_tic or by_pos:
                found.append(_compact(row, kind, sep))
    return {"source": "ExoFOP-TESS", "count": len(found), "objects": found}
