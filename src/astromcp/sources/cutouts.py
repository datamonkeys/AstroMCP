"""Image cutout links (no network needed)."""

from __future__ import annotations

from typing import Any


def urls(ra: float, dec: float, size_arcsec: float = 60.0) -> dict[str, Any]:
    ls_px = max(32, min(3000, round(size_arcsec / 0.262)))
    ps_px = max(32, min(6000, round(size_arcsec / 0.25)))
    arcmin = max(0.5, round(size_arcsec / 60, 3))
    return {
        "legacy_survey_jpeg": f"https://www.legacysurvey.org/viewer/jpeg-cutout?ra={ra:.6f}&dec={dec:.6f}&size={ls_px}&layer=ls-dr10&pixscale=0.262",
        "legacy_survey_fits": f"https://www.legacysurvey.org/viewer/fits-cutout?ra={ra:.6f}&dec={dec:.6f}&size={ls_px}&layer=ls-dr10&pixscale=0.262&bands=griz",
        "legacy_survey_viewer": f"https://www.legacysurvey.org/viewer?ra={ra:.6f}&dec={dec:.6f}&layer=ls-dr10&zoom=16&mark={ra:.6f},{dec:.6f}",
        "panstarrs_jpeg": f"https://ps1images.stsci.edu/cgi-bin/ps1cutouts?pos={ra:.6f}+{dec:+.6f}&filter=color&filetypes=stack&size={ps_px}&output_size=0&verbose=0&autoscale=99.5",
        "dss_gif": f"https://archive.stsci.edu/cgi-bin/dss_search?v=poss2ukstu_red&r={ra:.6f}&d={dec:+.6f}&e=J2000&h={arcmin}&w={arcmin}&f=gif",
        "aladin_lite": f"https://aladin.cds.unistra.fr/AladinLite/?target={ra:.6f}%20{dec:+.6f}&fov={max(arcmin / 60, 0.01):.4f}&survey=P%2FDSS2%2Fcolor",
        "notes": "Legacy Survey covers dec > -68 roughly (DR10); Pan-STARRS covers dec > -30; DSS is all-sky.",
    }
