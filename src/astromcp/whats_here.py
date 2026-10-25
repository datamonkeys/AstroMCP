"""'Is it already known?': query every archive in parallel and reach a verdict."""

from __future__ import annotations

import concurrent.futures as cf
from collections.abc import Callable
from typing import Any

from . import net
from .sources import alerce, cutouts, exofop, simbad, skybot, tns, vizier

PER_SOURCE_TIMEOUT = 60.0
_POOL = cf.ThreadPoolExecutor(max_workers=16, thread_name_prefix="astromcp")


def _run(jobs: dict[str, Callable[[], Any]], timeout: float) -> dict[str, dict[str, Any]]:
    futs = {name: _POOL.submit(fn) for name, fn in jobs.items()}
    out: dict[str, dict[str, Any]] = {}
    done, _ = cf.wait(futs.values(), timeout=timeout)
    for name, f in futs.items():
        if f not in done:
            out[name] = {"status": "timeout", "error": f"no answer within {timeout:.0f} s"}
            continue
        try:
            out[name] = {"status": "ok", **f.result()}
        except Exception as e:
            msg = str(e) if isinstance(e, (net.SourceError, ValueError)) else f"{e.__class__.__name__}: {e}"
            out[name] = {"status": "error", "error": net.redact(msg)}
    return out


def _verdict(r: dict[str, dict[str, Any]], radius: float) -> tuple[list[str], list[str]]:
    ev: list[str] = []

    def ok(k: str) -> dict[str, Any] | None:
        v = r.get(k)
        return v if v and v.get("status") == "ok" else None

    t = ok("tns")
    tns_objs = (t or {}).get("objects") or []
    sim = (ok("simbad") or {}).get("objects") or []
    vsx_objs = (ok("vsx") or {}).get("objects") or []
    gaia_r = ok("gaia") or {}
    toi = (ok("exofop") or {}).get("objects") or []
    ast = (ok("asteroids") or {}).get("objects") or []
    ztf = (ok("ztf") or {}).get("objects") or []

    for o in tns_objs:
        ev.append(
            f"TNS: {o['name']}"
            + (f" ({o['type']})" if o.get("type") else "")
            + (f' at {o["sep_arcsec"]}"' if o.get("sep_arcsec") is not None else "")
        )
    sim_trans = [o for o in sim if o.get("otype") in simbad.TRANSIENT_OTYPES]
    sim_var = [o for o in sim if o.get("otype") in simbad.VARIABLE_OTYPES]
    for o in sim[:3]:
        ev.append(f'SIMBAD: {o["main_id"]} [{o["otype"]}] at {o["sep_arcsec"]}"')
    for o in vsx_objs[:3]:
        ev.append(f'VSX: {o["name"]} ({o["type"]}) at {o["sep_arcsec"]}"')
    near = gaia_r.get("nearest")
    if near:
        ev.append(
            f'Gaia DR3 {near["source_id"]} at {near["sep_arcsec"]}" G={near["g_mag"]} plx={near["parallax_mas"]} '
            f"(S/N {near['parallax_snr']}) pm={near['pm_total_mas_yr']} mas/yr"
            + (" VARIABLE" if near.get("gaia_variable") else "")
        )
    for o in toi[:3]:
        ev.append(f'ExoFOP: {o["id"]} (TIC {o["tic"]}) at {o.get("sep_arcsec")}"')
    for o in ast[:3]:
        ev.append(
            f'SkyBoT: {o.get("number") or ""} {o["name"]} ({o["class"]}, V={o["v_mag"]}) at {o["sep_arcsec"]}"'.replace("  ", " ")
        )
    for o in ztf[:3]:
        ev.append(f"ZTF: {o['oid']} ndet={o['ndet']} class={o.get('class')}")

    labels: list[str] = []
    if tns_objs or sim_trans:
        labels.append("known transient")
    if toi:
        labels.append("known TESS object of interest")
    gaia_var_star = bool(near and near.get("gaia_variable") and near["sep_arcsec"] is not None and near["sep_arcsec"] <= 1.5)
    if vsx_objs or sim_var or gaia_var_star:
        labels.append("known variable")
    if [o for o in ast if o.get("sep_arcsec") is not None and o["sep_arcsec"] <= max(radius, 10)]:
        labels.append("known asteroid")
    star = bool(near and near.get("likely_star") and near["sep_arcsec"] is not None and near["sep_arcsec"] <= 1.5)
    if star or any(str(o.get("otype", "")).endswith("*") and (o.get("sep_arcsec") or 99) <= 1.5 for o in sim):
        labels.append("star")
    if sim and not labels:
        labels.append("known object")
    return (labels or ["nothing known"]), ev


def whats_here(
    ra: float, dec: float, radius_arcsec: float = 5.0, epoch: str | None = None, timeout: float = PER_SOURCE_TIMEOUT
) -> dict[str, Any]:
    jobs: dict[str, Callable[[], Any]] = {
        "tns": lambda: tns.search(ra, dec, radius_arcsec),
        "simbad": lambda: simbad.cone(ra, dec, radius_arcsec),
        "vsx": lambda: vizier.vsx(ra, dec, radius_arcsec),
        "gaia": lambda: vizier.gaia(ra, dec, radius_arcsec),
        "exofop": lambda: exofop.find(None, ra, dec, max(radius_arcsec, 10.0)),
        "ztf": lambda: alerce.objects_near(ra, dec, radius_arcsec),
    }
    if epoch:
        jobs["asteroids"] = lambda: skybot.cone(ra, dec, epoch, max(radius_arcsec, 30.0))
    results = _run(jobs, timeout)
    labels, evidence = _verdict(results, radius_arcsec)
    failed = sorted(k for k, v in results.items() if v["status"] != "ok")
    out: dict[str, Any] = {
        "query": {"ra": ra, "dec": dec, "radius_arcsec": radius_arcsec, "epoch": epoch},
        "verdict": labels[0],
        "labels": labels,
        "evidence": evidence,
        "sources_failed": failed,
        "caveat": (f"verdict may be incomplete: {', '.join(failed)} did not answer" if failed else None),
        "details": results,
        "images": cutouts.urls(ra, dec, 60),
    }
    if not epoch:
        out["note"] = "pass epoch (ISO UTC of the detection) to also check known asteroids"
    return out
