"""VizieR cone searches (VSX, Gaia DR3, TESS EBs) with a breaker so outages fail fast."""

from __future__ import annotations

from typing import Any

from .. import net
from ..util import num, rnd

URL = "https://vizier.cds.unistra.fr/viz-bin/asu-tsv"


def cone(catalog: str, ra: float, dec: float, radius_arcsec: float, cols: list[str], limit: int = 20) -> list[dict[str, str]]:
    """Rows sorted by distance; each row has `_r` (arcsec) plus `cols`."""
    text = net.fetch_text(
        URL,
        params={
            "-source": catalog,
            "-c": f"{ra:.6f} {dec:+.6f}",
            "-c.rs": f"{radius_arcsec}",
            "-out": ",".join(cols),
            "-out.add": "_r",
            "-c.u": "arcsec",
            "-sort": "_r",
            "-out.max": str(limit),
        },
        timeout=25,
        retries=2,
        ttl=3600,
    )
    lines = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
    if not lines:
        return []
    header = [h.strip() for h in lines[0].split("\t")]
    rows = []
    for ln in lines[3:]:  # header, units, dashes
        parts = ln.split("\t")
        if len(parts) == len(header):
            rows.append({h: p.strip() for h, p in zip(header, parts)})
    return rows


VSX_TYPES_URL = "https://www.aavso.org/vsx/index.php?view=about.vartypes"


def vsx(ra: float, dec: float, radius_arcsec: float = 10.0) -> dict[str, Any]:
    """AAVSO VSX variable stars."""
    rows = cone("B/vsx/vsx", ra, dec, radius_arcsec, ["OID", "Name", "Type", "max", "min", "n_max", "Period"])
    objs = [
        {
            "name": r.get("Name"),
            "type": r.get("Type") or None,
            "sep_arcsec": rnd(r.get("_r"), 2),
            "mag_max": rnd(r.get("max"), 2),
            "mag_min": rnd(r.get("min"), 2),
            "band": r.get("n_max") or None,
            "period_days": rnd(r.get("Period"), 6),
            "url": f"https://www.aavso.org/vsx/index.php?view=detail.top&oid={r.get('OID')}" if r.get("OID") else None,
        }
        for r in rows
    ]
    return {"source": "AAVSO VSX (VizieR B/vsx)", "count": len(objs), "objects": objs}


def gaia(ra: float, dec: float, radius_arcsec: float = 5.0) -> dict[str, Any]:
    """Gaia DR3 sources (nearest first), with parallax/proper-motion significance."""
    rows = cone(
        "I/355/gaiadr3",
        ra,
        dec,
        radius_arcsec,
        ["Source", "RA_ICRS", "DE_ICRS", "Gmag", "BP-RP", "Plx", "e_Plx", "pmRA", "pmDE", "RUWE", "VarFlag"],
        limit=10,
    )
    objs = []
    for r in rows:
        plx, eplx, pmra, pmde = num(r.get("Plx")), num(r.get("e_Plx")), num(r.get("pmRA")), num(r.get("pmDE"))
        pm = (pmra**2 + pmde**2) ** 0.5 if pmra is not None and pmde is not None else None
        plx_snr = plx / eplx if plx is not None and eplx else None
        objs.append(
            {
                "source_id": r.get("Source"),
                "sep_arcsec": rnd(r.get("_r"), 3),
                "ra": rnd(r.get("RA_ICRS"), 7),
                "dec": rnd(r.get("DE_ICRS"), 7),
                "g_mag": rnd(r.get("Gmag"), 3),
                "bp_rp": rnd(r.get("BP-RP"), 3),
                "parallax_mas": rnd(plx, 4),
                "parallax_snr": rnd(plx_snr, 1),
                "pm_total_mas_yr": rnd(pm, 3),
                "pm_ra": rnd(pmra, 3),
                "pm_dec": rnd(pmde, 3),
                "ruwe": rnd(r.get("RUWE"), 3),
                "gaia_variable": (r.get("VarFlag") or "").upper() == "VARIABLE",
                "likely_star": bool((plx_snr is not None and plx_snr > 3) or (pm is not None and pm > 5)),
            }
        )
    return {
        "source": "Gaia DR3 (VizieR I/355/gaiadr3)",
        "count": len(objs),
        "nearest": objs[0] if objs else None,
        "objects": objs,
    }


def tess_eb(ra: float, dec: float, radius_arcsec: float = 30.0) -> list[dict[str, Any]]:
    """TESS eclipsing binaries (Prsa et al. 2022, J/ApJS/258/16)."""
    rows = cone("J/ApJS/258/16/tess-ebs", ra, dec, radius_arcsec, ["TIC", "Per", "Morph"], limit=10)
    return [
        {
            "tic": r.get("TIC"),
            "period_days": rnd(r.get("Per"), 6),
            "morphology": rnd(r.get("Morph"), 3),
            "sep_arcsec": rnd(r.get("_r"), 2),
        }
        for r in rows
    ]
