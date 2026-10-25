"""Known solar-system objects at a position and time (IMCCE SkyBoT cone search)."""

from __future__ import annotations

from typing import Any

from .. import net
from ..util import iso_to_jd, rnd

URL = "https://ssp.imcce.fr/webservices/skybot/api/conesearch.php"


def parse(text: str) -> list[dict[str, Any]]:
    """SkyBoT text output: '# flag: n', a '# Num | Name | ...' header and pipe-separated rows."""
    header: list[str] | None = None
    rows = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            continue
        if s.startswith("#"):
            body = s.lstrip("#").strip()
            if "|" in body:
                header = [h.strip() for h in body.split("|")]
            elif body.lower().startswith("flag") and body.split(":")[-1].strip() in ("0", "-1"):
                return []
            continue
        if header and "|" in s:
            rows.append(dict(zip(header, (p.strip() for p in s.split("|")))))
    out = []
    for r in rows:
        ra_h = r.get("RA(h)", "")
        out.append(
            {
                "number": r.get("Num") if r.get("Num") not in ("-", "") else None,
                "name": r.get("Name"),
                "class": r.get("Class"),
                "ra": ra_h,
                "dec": r.get("DE(deg)"),
                "v_mag": rnd(r.get("Mv"), 2),
                "position_error_arcsec": rnd(r.get("Err(arcsec)"), 3),
                "sep_arcsec": rnd(r.get("d(arcsec)"), 2),
                "motion_ra_arcsec_h": rnd(r.get("dRA(arcsec/h)"), 3),
                "motion_dec_arcsec_h": rnd(r.get("dDEC(arcsec/h)"), 3),
            }
        )
    return sorted(out, key=lambda o: o["sep_arcsec"] if o["sep_arcsec"] is not None else 1e9)


def cone(ra: float, dec: float, epoch_iso: str, radius_arcsec: float = 30.0, observer: str = "500") -> dict[str, Any]:
    try:
        jd = iso_to_jd(epoch_iso)
    except ValueError:
        raise ValueError("epoch must be ISO 8601, e.g. '2026-10-20T03:15:00'") from None
    text = net.fetch_text(
        URL,
        params={
            "-ep": f"{jd:.6f}",
            "-ra": f"{ra:.6f}",
            "-dec": f"{dec:.6f}",
            "-rd": f"{radius_arcsec / 3600:.6f}",
            "-mime": "text",
            "-output": "basic",
            "-loc": observer,
            "-from": "AstroMCP",
        },
        timeout=45,
        retries=2,
        ttl=24 * 3600,
    )
    if "<html" in text[:200].lower():
        raise net.SourceError("SkyBoT returned an HTML error page")
    objs = parse(text)
    return {"source": "IMCCE SkyBoT", "epoch_jd": round(jd, 6), "observer": observer, "count": len(objs), "objects": objs}
