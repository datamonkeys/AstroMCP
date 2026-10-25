"""AstroMCP MCP server: tools for checking astronomical objects against public archives."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from . import __version__, net
from .sources import alerce, fink, skybot, tess, tns, vizier
from .sources import cutouts as cut
from .sources import simbad as sim
from .util import validate_position
from .whats_here import whats_here as _whats_here

logging.basicConfig(level=logging.WARNING)

mcp = MCPServer(
    name="astromcp",
    version=__version__,
    instructions=(
        "Read-only access to public astronomy archives (TNS, SIMBAD, VSX, Gaia DR3, ExoFOP-TESS, "
        "ALeRCE/ZTF, Fink/Rubin, IMCCE SkyBoT, image cutouts). Coordinates are ICRS decimal degrees. "
        "Start with whats_here(ra, dec) to ask 'is this already known?'."
    ),
)
RO = ToolAnnotations(read_only_hint=True, open_world_hint=True, idempotent_hint=True)


def _safe(fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Uniform error envelope; never leaks credentials."""
    try:
        return fn()
    except ValueError as e:
        return {"error": f"invalid input: {e}"}
    except net.SourceError as e:
        return {"error": net.redact(str(e))}
    except Exception as e:
        return {"error": net.redact(f"{e.__class__.__name__}: {e}")}


@mcp.tool(annotations=RO)
def whats_here(ra: float, dec: float, radius_arcsec: float = 5.0, epoch: str | None = None) -> dict[str, Any]:
    """Is it already known? Query TNS, SIMBAD, VSX, Gaia DR3, ExoFOP TOI/CTOI, ZTF (ALeRCE) and,
    if `epoch` (ISO UTC, e.g. '2026-10-20T03:15:00') is given, known asteroids (SkyBoT), all in
    parallel. Returns a verdict (the most specific of: 'known transient', 'known TESS object of interest',
    'known variable', 'known asteroid', 'star', 'known object', 'nothing known'), all matching labels, one-line evidence per hit, which
    sources failed, per-source details and image cutout links. ra/dec in decimal degrees (ICRS)."""

    def go() -> dict[str, Any]:
        validate_position(ra, dec, radius_arcsec, 120)
        return _whats_here(ra, dec, radius_arcsec, epoch)

    return _safe(go)


@mcp.tool(annotations=RO)
def tns_object(name: str) -> dict[str, Any]:
    """Look up a Transient Name Server object by name, e.g. '2026agtq' or 'AT 2026agtq': position,
    type, redshift, discovery date/mag, reporting group, internal names."""
    return _safe(lambda: tns.get_object(name))


@mcp.tool(annotations=RO)
def tns_search(ra: float, dec: float, radius_arcsec: float = 5.0) -> dict[str, Any]:
    """Transient Name Server cone search (live API if bot credentials are set, rate-limited to
    10/min; otherwise the cached daily public archive)."""

    def go() -> dict[str, Any]:
        validate_position(ra, dec, radius_arcsec, 300)
        return tns.search(ra, dec, radius_arcsec)

    return _safe(go)


@mcp.tool(annotations=RO)
def ztf_lightcurve(oid: str) -> dict[str, Any]:
    """ZTF light curve from ALeRCE for an object id like 'ZTF26acatcla': per-band summary,
    detections (magpsf and magpsf_corr) and non-detection summary (last limit before first detection)."""
    return _safe(lambda: alerce.lightcurve(oid))


@mcp.tool(annotations=RO)
def ztf_objects_near(ra: float, dec: float, radius_arcsec: float = 5.0) -> dict[str, Any]:
    """ZTF objects (ALeRCE) within radius of a position."""

    def go() -> dict[str, Any]:
        validate_position(ra, dec, radius_arcsec, 600)
        return alerce.objects_near(ra, dec, radius_arcsec)

    return _safe(go)


@mcp.tool(annotations=RO)
def rubin_object(dia_object_id: str) -> dict[str, Any]:
    """Rubin/LSST object from the Fink broker by diaObjectId: position, light curve (AB mag from
    nJy flux), and cutout links of the latest alert."""
    return _safe(lambda: fink.obj(dia_object_id))


@mcp.tool(annotations=RO)
def rubin_recent(tag: str = "most_likely_sn", days: float = 3.0) -> dict[str, Any]:
    """Recent Rubin objects in a Fink LSST tag over the last N days (max 30), brightest first.
    Tags: most_likely_sn, sn_near_galaxy_candidate, extragalactic_new_candidate,
    extragalactic_lt20mag_candidate, hostless_candidate."""
    return _safe(lambda: fink.recent(tag, days))


@mcp.tool(annotations=RO)
def simbad(ra: float, dec: float, radius_arcsec: float = 10.0) -> dict[str, Any]:
    """SIMBAD objects within radius (nearest first): main id, object type, spectral type, redshift."""

    def go() -> dict[str, Any]:
        validate_position(ra, dec, radius_arcsec, 600)
        return sim.cone(ra, dec, radius_arcsec)

    return _safe(go)


@mcp.tool(annotations=RO)
def vsx(ra: float, dec: float, radius_arcsec: float = 10.0) -> dict[str, Any]:
    """AAVSO VSX variable stars within radius: name, variability type, range, period."""

    def go() -> dict[str, Any]:
        validate_position(ra, dec, radius_arcsec, 600)
        return vizier.vsx(ra, dec, radius_arcsec)

    return _safe(go)


@mcp.tool(annotations=RO)
def gaia(ra: float, dec: float, radius_arcsec: float = 5.0) -> dict[str, Any]:
    """Gaia DR3 sources within radius, nearest first: G, BP-RP, parallax (+S/N), proper motion,
    RUWE, variability flag, and a 'likely_star' flag (parallax S/N > 3 or PM > 5 mas/yr)."""

    def go() -> dict[str, Any]:
        validate_position(ra, dec, radius_arcsec, 120)
        return vizier.gaia(ra, dec, radius_arcsec)

    return _safe(go)


@mcp.tool(annotations=RO)
def tess_known(
    tic: int | None = None, ra: float | None = None, dec: float | None = None, radius_arcsec: float = 30.0
) -> dict[str, Any]:
    """Known TESS objects for a TIC id and/or position: TOIs and CTOIs (ExoFOP-TESS) and TESS
    eclipsing binaries (Prsa et al. 2022). With only a TIC, its position comes from TIC v8.2."""

    def go() -> dict[str, Any]:
        if ra is not None and dec is not None:
            validate_position(ra, dec, radius_arcsec, 300)
        return tess.known(tic, ra, dec, radius_arcsec)

    return _safe(go)


@mcp.tool(annotations=RO)
def asteroids_at(ra: float, dec: float, epoch_iso: str, radius_arcsec: float = 30.0) -> dict[str, Any]:
    """Known solar-system objects near a position at a given time (IMCCE SkyBoT, geocentric):
    name, class, V mag, separation, motion. epoch_iso is UTC, e.g. '2026-10-20T03:15:00'."""

    def go() -> dict[str, Any]:
        validate_position(ra, dec, radius_arcsec, 3600)
        return skybot.cone(ra, dec, epoch_iso, radius_arcsec)

    return _safe(go)


@mcp.tool(annotations=RO)
def cutout_urls(ra: float, dec: float, size_arcsec: float = 60.0) -> dict[str, Any]:
    """Image cutout links for a position: Legacy Survey DR10 (JPEG/FITS/viewer), Pan-STARRS color,
    DSS2 red and Aladin Lite."""

    def go() -> dict[str, Any]:
        validate_position(ra, dec, size_arcsec, 3600)
        return cut.urls(ra, dec, size_arcsec)

    return _safe(go)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
