# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0]

- Published on PyPI as **`astro-checker`** (`astromcp` was rejected as too similar to the unrelated `astro-mcp`); commands `astro-checker` and `astromcp`. - 2026-10-25

### Added

- First public release: MCP server (stdio) with 14 read-only tools.
- `whats_here`: parallel check of TNS, SIMBAD, VSX, Gaia DR3, ExoFOP-TESS, ZTF (ALeRCE) and SkyBoT with a
  single verdict, evidence, failed sources and image links; archive-only TNS checks are flagged.
- `tns_object`, `tns_search` (live API with bot credentials, daily public archive otherwise).
- `ztf_lightcurve`, `ztf_objects_near` (ALeRCE); `rubin_object`, `rubin_recent` (Fink LSST).
- `simbad`, `vsx`, `gaia`, `tess_known`, `asteroids_at`, `cutout_urls`.
- `observe_tonight`: bright, recent, unclassified TNS transients observable from a site tonight, ranked.
- Polite networking: timeouts, retries with backoff, per-host circuit breaker, disk cache, TNS rate limiting.

[Unreleased]: https://github.com/louisperner/AstroMCP/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/louisperner/AstroMCP/releases/tag/v0.1.0
