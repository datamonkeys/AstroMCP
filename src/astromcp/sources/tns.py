"""Transient Name Server (wis-tns.org): cone search and object lookup.

With bot credentials (env TNS_BOT_ID, TNS_BOT_NAME, TNS_API_KEY) the live API is used,
throttled to the TNS limit of 10 cone searches per minute. The daily public objects
archive (tns_public_objects.csv.zip, refreshed at 00:00 UTC) is cached on disk and
indexed locally; it is used when there are no credentials (if a copy exists or can be
downloaded) or when the API fails. Objects reported after midnight UTC are not in it.
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import threading
import time
import zipfile
from collections import defaultdict
from typing import Any

from .. import net
from ..util import rnd, sep_arcsec

API = "https://www.wis-tns.org/api/get"
ARCHIVE_URL = "https://www.wis-tns.org/system/files/tns_public_objects/tns_public_objects.csv.zip"
ARCHIVE_MAX_AGE = 20 * 3600
CONE_INTERVAL = 6.5  # seconds between cone searches (10/min limit)


def credentials() -> dict[str, Any] | None:
    if all(os.environ.get(k) for k in ("TNS_BOT_ID", "TNS_BOT_NAME", "TNS_API_KEY")):
        return {
            "bot_id": os.environ["TNS_BOT_ID"],
            "bot_name": os.environ["TNS_BOT_NAME"],
            "api_key": os.environ["TNS_API_KEY"],
        }
    return None


def _marker(cfg: dict[str, Any]) -> dict[str, str]:
    return {"User-Agent": "tns_marker" + json.dumps({"tns_id": cfg["bot_id"], "type": "bot", "name": cfg["bot_name"]})}


_cone_lock = threading.Lock()
_last_cone = [0.0]


def _api(endpoint: str, cfg: dict[str, Any], payload: dict[str, Any], cone: bool = False) -> Any:
    data = {"api_key": cfg["api_key"], "data": json.dumps(payload)}
    if not cone:
        return net.fetch_json(f"{API}/{endpoint}", data=data, headers=_marker(cfg), ttl=600, timeout=30)
    with _cone_lock:  # one cone search at a time, spaced to respect 10/min
        wait = CONE_INTERVAL - (time.time() - _last_cone[0])
        if wait > 0:
            time.sleep(wait)
        try:
            return net.fetch_json(f"{API}/{endpoint}", data=data, headers=_marker(cfg), ttl=600, timeout=30)
        finally:
            _last_cone[0] = time.time()


# ---------------------------------------------------------------- local archive index


class TNSIndex:
    """Public TNS objects bucketed by 1-degree declination strips."""

    def __init__(self, rows: list[dict[str, str]]) -> None:
        self.strips: dict[int, list[dict[str, Any]]] = defaultdict(list)
        self.by_name: dict[str, dict[str, Any]] = {}
        for d in rows:
            try:
                ra, dec = float(d["ra"]), float(d["declination"])
            except (KeyError, ValueError):
                continue
            obj = _compact_archive_row(d, ra, dec)
            self.strips[math.floor(dec)].append(obj)
            self.by_name[d.get("name", "").strip().upper()] = obj
        self.total = len(self.by_name)

    def cone(self, ra: float, dec: float, radius_arcsec: float) -> list[dict[str, Any]]:
        r = radius_arcsec / 3600
        out = []
        for strip in range(math.floor(dec - r), math.floor(dec + r) + 1):
            for o in self.strips.get(strip, []):
                if abs(o["dec"] - dec) > r:
                    continue
                s = sep_arcsec(ra, dec, o["ra"], o["dec"])
                if s <= radius_arcsec:
                    out.append({**o, "sep_arcsec": round(s, 2)})
        return sorted(out, key=lambda o: o["sep_arcsec"])

    def get(self, name: str) -> dict[str, Any] | None:
        return self.by_name.get(_bare_name(name))


def _compact_archive_row(d: dict[str, str], ra: float, dec: float) -> dict[str, Any]:
    name = f"{d.get('name_prefix', '')} {d.get('name', '')}".strip()
    return {
        "name": name,
        "ra": ra,
        "dec": dec,
        "type": d.get("type") or None,
        "redshift": rnd(d.get("redshift")),
        "discovery_date": d.get("discoverydate") or None,
        "discovery_mag": rnd(d.get("discoverymag"), 2),
        "reporting_group": _clean(d.get("reporting_group")),
        "internal_names": d.get("internal_names") or None,
        "url": f"https://www.wis-tns.org/object/{d.get('name', '')}",
    }


def _clean(v: Any) -> Any:
    return None if v in ("", "None", "null") else v


def _bare_name(name: str) -> str:
    s = name.strip().upper()
    for p in ("AT ", "SN ", "TDE ", "FRB ", "AT", "SN"):
        if s.startswith(p) and len(s) > len(p) and s[len(p)].isdigit():
            return s[len(p) :].strip()
        if s.startswith(p + " "):
            return s[len(p) + 1 :].strip()
    return s.replace(" ", "")


def parse_archive(content: bytes) -> list[dict[str, str]]:
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        text = z.read(z.namelist()[0]).decode("utf-8", "replace")
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 2:
        return []
    header = rows[1]  # first line is the archive timestamp
    return [dict(zip(header, r)) for r in rows[2:]]


_index_lock = threading.Lock()
_index: dict[str, Any] = {"mtime": 0.0, "index": None}


def archive_index() -> TNSIndex | None:
    """Index of the cached public archive, refreshed if older than 20 h (needs credentials
    to download; a manually placed copy in the cache dir, or TNS_PUBLIC_CSV, also works)."""
    path = os.environ.get("TNS_PUBLIC_CSV") or str(net.cache_dir() / "tns_public_objects.csv.zip")
    cfg = credentials()
    with _index_lock:
        fresh = os.path.exists(path) and time.time() - os.path.getmtime(path) < ARCHIVE_MAX_AGE
        if not fresh and cfg and not os.environ.get("TNS_PUBLIC_CSV"):
            try:
                content = net.fetch(ARCHIVE_URL, data={"api_key": cfg["api_key"]}, headers=_marker(cfg), ttl=0, timeout=300)
                tmp = path + ".tmp"
                with open(tmp, "wb") as f:
                    f.write(content)
                os.replace(tmp, path)
            except Exception:
                pass
        if not os.path.exists(path):
            return None
        mtime = os.path.getmtime(path)
        if _index["index"] is None or _index["mtime"] != mtime:
            try:
                with open(path, "rb") as f:
                    _index["index"] = TNSIndex(parse_archive(f.read()))
                _index["mtime"] = mtime
            except Exception:
                return None
        idx: TNSIndex = _index["index"]
        return idx


# ---------------------------------------------------------------- public functions


def search(ra: float, dec: float, radius_arcsec: float = 5.0) -> dict[str, Any]:
    """TNS objects within radius. Prefers the live API; falls back to the daily archive."""
    cfg = credentials()
    api_error = None
    if cfg:
        try:
            resp = _api(
                "search",
                cfg,
                {"ra": f"{ra:.6f}", "dec": f"{dec:.6f}", "radius": f"{radius_arcsec}", "units": "arcsec"},
                cone=True,
            )
            names = [f"{o.get('prefix', '')} {o['objname']}".strip() for o in resp.get("data", []) or []]
            objs: list[dict[str, Any]] = []
            idx = archive_index()
            for n in names:
                extra = idx.get(n) if idx else None
                o: dict[str, Any] = {"name": n}
                if extra:
                    o.update({k: v for k, v in extra.items() if k != "name"})
                    o["sep_arcsec"] = round(sep_arcsec(ra, dec, extra["ra"], extra["dec"]), 2)
                else:  # reported after the archive was built: ask the API for details
                    try:
                        full = get_object(n)
                        o.update({k: v for k, v in full.items() if k not in ("name", "source")})
                        if full.get("ra") is not None and full.get("dec") is not None:
                            o["sep_arcsec"] = round(sep_arcsec(ra, dec, full["ra"], full["dec"]), 2)
                    except Exception:
                        o["url"] = f"https://www.wis-tns.org/object/{_bare_name(n).lower()}"
                objs.append(o)
            return {"source": "TNS API", "count": len(objs), "objects": objs}
        except Exception as e:
            api_error = net.redact(str(e))
    idx = archive_index()
    if idx is None:
        why = api_error or "no TNS credentials (set TNS_BOT_ID, TNS_BOT_NAME, TNS_API_KEY) and no cached archive"
        raise net.SourceError(f"TNS unavailable: {why}")
    objs = idx.cone(ra, dec, radius_arcsec)
    out: dict[str, Any] = {
        "source": "TNS public archive (daily, misses objects reported since 00:00 UTC)",
        "count": len(objs),
        "objects": objs,
    }
    if api_error:
        out["api_error"] = api_error
    return out


def get_object(name: str) -> dict[str, Any]:
    """One TNS object by name ("2026agtq", "AT 2026agtq", "SN2024abc")."""
    bare = _bare_name(name).lower()
    if not bare or not bare[:4].isdigit():
        raise ValueError("TNS names look like '2026agtq' or 'AT 2026agtq'")
    cfg = credentials()
    if cfg:
        resp = _api("object", cfg, {"objname": bare, "photometry": "0", "spectra": "0"})
        d = resp.get("data") or {}
        if not d or d.get("objname") is None:
            raise net.SourceError(f"TNS has no object named {bare}")
        return {
            "source": "TNS API",
            "name": f"{d.get('name_prefix', '')} {d.get('objname')}".strip(),
            "ra": rnd(d.get("radeg"), 6),
            "dec": rnd(d.get("decdeg"), 6),
            "type": (d.get("object_type") or {}).get("name"),
            "redshift": rnd(d.get("redshift")),
            "discovery_date": d.get("discoverydate"),
            "discovery_mag": rnd(d.get("discoverymag"), 2),
            "discovery_filter": (d.get("discmagfilter") or {}).get("name"),
            "reporting_group": _clean((d.get("reporting_group") or {}).get("group_name")),
            "discovery_data_source": _clean((d.get("discovery_data_source") or {}).get("group_name")),
            "internal_names": d.get("internal_names"),
            "host_name": d.get("hostname") or None,
            "url": f"https://www.wis-tns.org/object/{bare.lower()}",
        }
    idx = archive_index()
    if idx is None:
        raise net.SourceError("TNS unavailable: no credentials and no cached public archive")
    obj = idx.get(bare)
    if obj is None:
        raise net.SourceError(f"{bare} not in the TNS public archive (reported today, or unknown)")
    return {"source": "TNS public archive", **obj}
