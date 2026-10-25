"""SIMBAD via TAP (ADQL)."""

from __future__ import annotations

import csv
import io
from typing import Any

from .. import net
from ..util import rnd

TAP = "https://simbad.cds.unistra.fr/simbad/sim-tap/sync"

# otype codes that mean "variable star" (SIMBAD 2020+ condensed codes)
VARIABLE_OTYPES = {
    "V*", "V*?", "Ir*", "Er*", "Ro*", "Pu*", "RR*", "Ce*", "cC*", "C*", "dS*", "Mi*", "LP*", "LP?", "EB*", "EB?",
    "No*", "No?", "CV*", "CV?", "DN*", "XB*", "Fl*", "Or*", "BY*", "RS*", "sr*", "gD*", "SX*", "WV*", "ZZ*", "El*",
    "RV*", "Be*", "s*b", "BS*", "Y*O", "TT*", "Ae*", "bC*", "BL*", "LXB", "HXB", "Sy*",
}  # fmt: skip
TRANSIENT_OTYPES = {"SN*", "SN?", "No*", "No?", "GRB", "TDE"}
STAR_HINTS = ("*",)


def query(adql: str) -> list[dict[str, str]]:
    text = net.fetch_text(
        TAP, params={"request": "doQuery", "lang": "adql", "format": "csv", "query": adql}, timeout=30, ttl=3600
    )
    return list(csv.DictReader(io.StringIO(text)))


def cone(ra: float, dec: float, radius_arcsec: float = 10.0, limit: int = 15) -> dict[str, Any]:
    q = (
        f"SELECT TOP {int(limit)} main_id, otype, ra, dec, sp_type, rvz_redshift, "
        f"DISTANCE(POINT('ICRS', ra, dec), POINT('ICRS', {ra}, {dec})) * 3600 AS sep "
        f"FROM basic WHERE CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {ra}, {dec}, {radius_arcsec / 3600})) = 1 "
        "ORDER BY sep"
    )
    objs = [
        {
            "main_id": r.get("main_id"),
            "otype": r.get("otype"),
            "sep_arcsec": rnd(r.get("sep"), 2),
            "ra": rnd(r.get("ra"), 6),
            "dec": rnd(r.get("dec"), 6),
            "sp_type": r.get("sp_type") or None,
            "redshift": rnd(r.get("rvz_redshift"), 5),
            "url": "https://simbad.cds.unistra.fr/simbad/sim-id?Ident=" + (r.get("main_id") or "").replace(" ", "+"),
        }
        for r in query(q)
    ]
    return {"source": "SIMBAD TAP", "count": len(objs), "objects": objs}
