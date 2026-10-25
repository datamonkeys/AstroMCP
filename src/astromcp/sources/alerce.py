"""ZTF via the ALeRCE broker API."""

from __future__ import annotations

import re
from typing import Any

from .. import net
from ..util import mjd_now, rnd

API = "https://api.alerce.online/ztf/v1"
FILTERS = {1: "g", 2: "r", 3: "i"}
OID_RE = re.compile(r"^ZTF\d{2}[a-z]{7}$")


def _obj(o: dict[str, Any]) -> dict[str, Any]:
    return {
        "oid": o.get("oid"),
        "ra": rnd(o.get("meanra"), 6),
        "dec": rnd(o.get("meandec"), 6),
        "ndet": o.get("ndet"),
        "first_mjd": rnd(o.get("firstmjd"), 4),
        "last_mjd": rnd(o.get("lastmjd"), 4),
        "stellar": o.get("stellar"),
        "class": o.get("class"),
        "classifier": o.get("classifier"),
        "probability": rnd(o.get("probability"), 3),
        "url": f"https://alerce.online/object/{o.get('oid')}",
    }


def objects_near(ra: float, dec: float, radius_arcsec: float = 5.0) -> dict[str, Any]:
    d = net.fetch_json(f"{API}/objects/", params={"ra": ra, "dec": dec, "radius": radius_arcsec, "page_size": 20}, timeout=30)
    objs = [_obj(o) for o in (d.get("items") or [])]
    return {"source": "ALeRCE (ZTF)", "count": len(objs), "objects": objs}


def lightcurve(oid: str, max_points: int = 200) -> dict[str, Any]:
    """Detections (with magpsf_corr when available) and per-filter non-detection summary."""
    oid = oid.strip()
    if not OID_RE.match(oid):
        raise ValueError("ZTF object ids look like 'ZTF26acatcla'")
    d = net.fetch_json(f"{API}/objects/{oid}/lightcurve", timeout=40)
    dets_raw = sorted(d.get("detections") or [], key=lambda x: x.get("mjd") or 0)
    nd_raw = sorted(d.get("non_detections") or [], key=lambda x: x.get("mjd") or 0)
    if not dets_raw and not nd_raw:
        raise net.SourceError(f"ALeRCE has no light curve for {oid}")
    dets: list[dict[str, Any]] = []
    for x in dets_raw:
        pos = x.get("isdiffpos", 1) in (1, "t", True)
        dets.append(
            {
                "mjd": rnd(x.get("mjd"), 5),
                "band": FILTERS.get(x.get("fid"), str(x.get("fid"))),
                "magpsf": rnd(x.get("magpsf"), 3),
                "sigmapsf": rnd(x.get("sigmapsf"), 3),
                "magpsf_corr": rnd(x.get("magpsf_corr"), 3),
                "positive": pos,
            }
        )
    summary: dict[str, Any] = {}
    for band in sorted({p["band"] for p in dets}):
        pts = [p for p in dets if p["band"] == band and p["magpsf"] is not None]
        if pts:
            brightest = min(pts, key=lambda p: p["magpsf"])
            summary[band] = {
                "n": len(pts),
                "first_mag": pts[0]["magpsf"],
                "last_mag": pts[-1]["magpsf"],
                "peak_mag": brightest["magpsf"],
                "peak_mjd": brightest["mjd"],
            }
    first_det = dets[0]["mjd"] if dets else None
    before = [n for n in nd_raw if first_det is None or (n.get("mjd") or 0) < first_det]
    last_nd = before[-1] if before else None
    nd_summary = {
        "count": len(nd_raw),
        "last_before_first_detection": (
            {
                "mjd": rnd(last_nd.get("mjd"), 5),
                "band": FILTERS.get(last_nd.get("fid"), str(last_nd.get("fid"))),
                "limit_mag": rnd(last_nd.get("diffmaglim"), 2),
            }
            if last_nd
            else None
        ),
        "deepest_limit_mag": rnd(max((n.get("diffmaglim") or 0 for n in nd_raw), default=None), 2) if nd_raw else None,
    }
    out = {
        "source": "ALeRCE (ZTF)",
        "oid": oid,
        "n_detections": len(dets),
        "first_detection_mjd": first_det,
        "last_detection_mjd": dets[-1]["mjd"] if dets else None,
        "days_since_last_detection": round(mjd_now() - dets[-1]["mjd"], 2) if dets and dets[-1]["mjd"] else None,
        "per_band": summary,
        "non_detections": nd_summary,
        "detections": dets[-max_points:],
        "truncated": len(dets) > max_points,
        "url": f"https://alerce.online/object/{oid}",
    }
    return out
