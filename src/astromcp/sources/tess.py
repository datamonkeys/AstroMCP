"""Known TESS objects: TOI/CTOI (ExoFOP) and TESS eclipsing binaries (Prsa+2022)."""

from __future__ import annotations

from typing import Any

from .. import net
from ..util import num
from . import exofop, vizier


def tic_position(tic: int) -> tuple[float, float] | None:
    """TIC v8.2 position via VizieR (IV/39/tic82)."""
    text = net.fetch_text(
        vizier.URL,
        params={"-source": "IV/39/tic82", "TIC": str(tic), "-out": "TIC,RAJ2000,DEJ2000", "-out.max": "1"},
        timeout=25,
        retries=2,
        ttl=7 * 24 * 3600,
    )
    lines = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
    for ln in lines[3:]:
        parts = [p.strip() for p in ln.split("\t")]
        if len(parts) >= 3 and (ra := num(parts[1])) is not None and (dec := num(parts[2])) is not None:
            return ra, dec
    return None


def known(
    tic: int | None = None, ra: float | None = None, dec: float | None = None, radius_arcsec: float = 30.0
) -> dict[str, Any]:
    if tic is None and (ra is None or dec is None):
        raise ValueError("give tic, or ra and dec")
    out: dict[str, Any] = {"tic": tic}
    errors: dict[str, str] = {}
    if tic is not None and (ra is None or dec is None):
        try:
            pos = tic_position(tic)
            if pos:
                ra, dec = pos
        except Exception as e:
            errors["tic_lookup"] = str(e)
    out["ra"], out["dec"] = ra, dec
    try:
        out["toi_ctoi"] = exofop.find(tic, ra, dec, radius_arcsec)["objects"]
    except Exception as e:
        errors["exofop"] = str(e)
    if ra is not None and dec is not None:
        try:
            ebs = vizier.tess_eb(ra, dec, radius_arcsec)
            out["tess_eb"] = ebs
        except Exception as e:
            errors["tess_eb"] = str(e)
    if errors:
        out["errors"] = errors
    toi = out.get("toi_ctoi") or []
    eb = out.get("tess_eb") or []
    out["summary"] = (", ".join(o["id"] for o in toi[:10]) if toi else "no TOI/CTOI") + (
        f"; {len(eb)} TESS EB(s)" if eb else "; no TESS EB"
    )
    out["source"] = "ExoFOP-TESS + VizieR J/ApJS/258/16"
    return out
