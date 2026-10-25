"""Rubin (LSST) alerts via the Fink LSST API."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from .. import net
from ..util import ab_mag_from_njy, num, rnd

API = "https://api.lsst.fink-portal.org/api/v1"
TAGS = (
    "most_likely_sn",
    "sn_near_galaxy_candidate",
    "extragalactic_new_candidate",
    "extragalactic_lt20mag_candidate",
    "hostless_candidate",
)
SOURCE_COLS = "r:diaObjectId,r:diaSourceId,r:ra,r:dec,r:midpointMjdTai,r:band,r:psfFlux,r:psfFluxErr,r:snr,r:reliability"
TAG_COLS = SOURCE_COLS + ",f:clf_snnSnVsOthers_score,f:xm_tns_fullname,f:xm_legacydr8_zphot,r:ssObjectId"


def _point(s: dict[str, Any]) -> dict[str, Any]:
    flux = num(s.get("r:psfFlux"))
    return {
        "mjd": rnd(s.get("r:midpointMjdTai"), 5),
        "band": s.get("r:band"),
        "flux_njy": rnd(flux, 2),
        "mag_ab": ab_mag_from_njy(flux),
        "snr": rnd(s.get("r:snr"), 1),
        "reliability": rnd(s.get("r:reliability"), 3),
    }


def obj(dia_object_id: str | int) -> dict[str, Any]:
    oid = str(dia_object_id).strip()
    if not oid.isdigit():
        raise ValueError("diaObjectId must be an integer")
    sources = net.fetch_json(f"{API}/sources", params={"diaObjectId": oid, "columns": SOURCE_COLS}, timeout=40) or []
    if not sources:
        raise net.SourceError(f"Fink has no Rubin sources for diaObjectId {oid}")
    sources = sorted(sources, key=lambda s: num(s.get("r:midpointMjdTai")) or 0)
    last = sources[-1]
    pts = [_point(s) for s in sources]
    mags = [p for p in pts if p["mag_ab"] is not None]
    return {
        "source": "Fink LSST",
        "diaObjectId": oid,
        "ra": rnd(last.get("r:ra"), 6),
        "dec": rnd(last.get("r:dec"), 6),
        "n_sources": len(pts),
        "first_mjd": pts[0]["mjd"],
        "last_mjd": pts[-1]["mjd"],
        "peak_mag_ab": min((p["mag_ab"] for p in mags), default=None),
        "bands": sorted({str(p["band"]) for p in pts}),
        "lightcurve": pts[-200:],
        "cutouts": {
            k: f"{API}/cutouts?diaSourceId={last.get('r:diaSourceId')}&kind={v}"
            for k, v in (("science", "Science"), ("template", "Template"), ("difference", "Difference"))
        },
        "url": f"https://lsst.fink-portal.org/{oid}",
    }


def recent(tag: str = "most_likely_sn", days: float = 3.0, limit: int = 50) -> dict[str, Any]:
    if tag not in TAGS:
        raise ValueError(f"tag must be one of {', '.join(TAGS)}")
    if not (0 < days <= 30):
        raise ValueError("days must be in (0, 30]")
    # the API documents MJD for startdate but only accepts ISO
    start = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    alerts = (
        net.fetch_json(
            f"{API}/tags", params={"tag": tag, "n": 2000, "startdate": start, "columns": TAG_COLS}, timeout=60, ttl=600
        )
        or []
    )
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for a in alerts:
        groups[str(a.get("r:diaObjectId"))].append(a)
    objs = []
    for oid, als in groups.items():
        als.sort(key=lambda a: num(a.get("r:midpointMjdTai")) or 0)
        fluxes = [f for a in als if (f := num(a.get("r:psfFlux"))) is not None]
        tns = next((a.get("f:xm_tns_fullname") for a in als if a.get("f:xm_tns_fullname") not in (None, "", "nan", "Fail")), None)
        objs.append(
            {
                "diaObjectId": oid,
                "ra": rnd(als[-1].get("r:ra"), 6),
                "dec": rnd(als[-1].get("r:dec"), 6),
                "n_alerts": len(als),
                "first_mjd": rnd(als[0].get("r:midpointMjdTai"), 4),
                "last_mjd": rnd(als[-1].get("r:midpointMjdTai"), 4),
                "peak_mag_ab": ab_mag_from_njy(max(fluxes)) if fluxes else None,
                "snn_sn_score": rnd(max((num(a.get("f:clf_snnSnVsOthers_score")) or 0 for a in als), default=None), 3),
                "tns": tns,
                "known_asteroid": any((num(a.get("r:ssObjectId")) or 0) > 0 for a in als),
                "url": f"https://lsst.fink-portal.org/{oid}",
            }
        )
    objs.sort(key=lambda o: o["peak_mag_ab"] if o["peak_mag_ab"] is not None else 99)
    note = None
    if not objs:
        last = latest_night()
        note = f"no alerts in this window; latest Rubin night in Fink: {last}" if last else "no alerts in this window"
    return {
        "note": note,
        "source": "Fink LSST",
        "tag": tag,
        "days": days,
        "count": len(objs),
        "objects": objs[:limit],
        "truncated": len(objs) > limit,
    }


def latest_night() -> str | None:
    """Latest night (YYYYMMDD) with Rubin alerts in Fink, this year or last; None if unknown."""
    year = datetime.now(UTC).year
    for y in (year, year - 1):
        try:
            nights = net.fetch_json(f"{API}/statistics", params={"date": str(y), "columns": "f:night"}, ttl=3600) or []
        except net.SourceError:
            return None
        if nights:
            return str(max(str(n.get("f:night")) for n in nights))
    return None
