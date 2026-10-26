# AstroMCP

[![CI](https://github.com/louisperner/AstroMCP/actions/workflows/ci.yml/badge.svg)](https://github.com/louisperner/AstroMCP/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/astromcp.svg)](https://pypi.org/project/astromcp/)
[![Python](https://img.shields.io/pypi/pyversions/astromcp.svg)](https://pypi.org/project/astromcp/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

<!-- mcp-name: io.github.louisperner/astromcp -->

An [MCP](https://modelcontextprotocol.io) server that gives AI assistants (Claude, Cursor, VS Code, ...)
direct, **read-only** access to public astronomy archives, so you can check a sky position in seconds and
answer the first question of any discovery: *is it already known?*

It queries the Transient Name Server (TNS), SIMBAD, AAVSO VSX, Gaia DR3, ExoFOP-TESS, ALeRCE/ZTF,
Fink/Rubin (LSST), IMCCE SkyBoT and several image surveys, and returns compact JSON the model can reason about.

> **Note:** answers depend on third-party services. Archives go down, rate-limit, or lag behind reality
> (for example, the public TNS archive is refreshed once a day). AstroMCP reports failed sources explicitly
> instead of pretending nothing is there, but always confirm important results at the source before
> reporting a discovery.

## Tools (14)

| Tool | What it does |
|---|---|
| `whats_here(ra, dec, radius_arcsec=5, epoch=None)` | Queries all archives in parallel and returns a verdict (`known transient`, `known TESS object of interest`, `known variable`, `known asteroid`, `star`, `known object`, `nothing known`) with evidence, failed sources and image links |
| `tns_object(name)` | Looks up a transient on TNS by name (e.g. `2026agtq`) |
| `tns_search(ra, dec, radius_arcsec=5)` | TNS cone search |
| `ztf_lightcurve(oid)` | ZTF light curve from ALeRCE (detections with `magpsf`/`magpsf_corr`, non-detection summary) |
| `ztf_objects_near(ra, dec, radius_arcsec=5)` | ZTF alert objects near a position (ALeRCE) |
| `rubin_object(dia_object_id)` | Rubin/LSST object light curve and cutouts (Fink) |
| `rubin_recent(tag="most_likely_sn", days=3)` | Recent Rubin objects in a Fink classification tag |
| `simbad(ra, dec, radius_arcsec=10)` | SIMBAD cone search (TAP) |
| `vsx(ra, dec, radius_arcsec=10)` | AAVSO VSX variable-star cone search |
| `gaia(ra, dec, radius_arcsec=5)` | Gaia DR3 sources (via VizieR) |
| `tess_known(tic=None, ra=None, dec=None)` | TESS TOIs, CTOIs and eclipsing binaries (ExoFOP-TESS, VizieR, TIC v8.2) |
| `asteroids_at(ra, dec, epoch_iso, radius_arcsec=30)` | Known solar-system objects at a position and time (IMCCE SkyBoT) |
| `cutout_urls(ra, dec, size_arcsec=60)` | Image links: Legacy Survey DR10, Pan-STARRS, DSS2, Aladin |
| `observe_tonight(lat, lon, ...)` | Bright, recent, still-unclassified TNS transients observable from your site tonight, ranked |

Coordinates are ICRS decimal degrees; times are ISO 8601 UTC. Errors come back as `{"error": "..."}` and, in
`whats_here`, as `sources_failed` plus a `caveat`, so a missing archive is never mistaken for "nothing known".

## Examples

These are real checks (also in `tests/test_integration.py`):

**"Is there anything known at RA 40.22898, Dec +12.601026?"**

```text
whats_here(40.22898, 12.601026)
→ verdict: "known transient"
  evidence: ["TNS: AT 2026agtq at 0.0\"", "ZTF: ZTF26acatcla ndet=10 class=None"]
```

**"What is at the position of TOI-2330?"**

```text
whats_here(172.85872, -41.68953)
→ verdict: "known TESS object of interest"
  labels: ["known TESS object of interest", "known variable", "star"]
  evidence: ["SIMBAD: WASP-128 [*] at 0.01\"", "SIMBAD: WASP-128b [BD?] at 0.01\"", "VSX: WASP-128 (EA/BD+ROT) at 0.04\"", ...]
```

The assistant can then answer: *"That's TOI-2330, already known as WASP-128 b, a brown dwarf transiting WASP-128."*

**An empty patch of sky:**

```text
whats_here(200.5, -20.3, 3)
→ verdict: "nothing known", sources_failed: []
```

**"What should I observe tonight from Curitiba?"**

```text
observe_tonight(lat=-25.43, lon=-49.27)
→ night_utc: ["2026-10-26T22:27Z", "2026-10-27T07:37Z"], moon illumination 0.99, 33 matching targets
  1. AT 2026afvp  mag 10.3, 8.1 d old, max alt 40.9°, window 03:57–07:37 UTC
  2. AT 2026agsu  mag 17.27, 2.2 d old, max alt 82.8°, window 22:27–02:37 UTC
  ...
```

`observe_tonight` selects transients up to 21 days old, TNS discovery mag ≤ 18.5, still unclassified, above 30°
while the Sun is below −12° and at least 20° from the Moon (all adjustable). Sun/Moon positions use the
Astronomical Almanac low-precision formulas (arcminute level). It is meant to help small telescopes and
spectroscopy groups pick classification targets.

## Install

Requires Python 3.11+.

```bash
uvx astromcp            # run without installing (recommended; needs uv)
pip install astromcp    # or install into an environment, then run `astromcp`
```

Or with Docker (from a clone): `docker build -t astromcp . && docker run -i --rm astromcp`.
See [`.env.example`](.env.example) for the optional variables.

The server speaks MCP over stdio; you normally don't run it by hand, your MCP client launches it.

## Configure your MCP client

### Claude Code

```bash
claude mcp add astromcp -- uvx astromcp
# with TNS credentials:
claude mcp add astromcp -e TNS_BOT_ID=12345 -e TNS_BOT_NAME=my_bot -e TNS_API_KEY=... -- uvx astromcp
```

Add `--scope user` to make it available in every project.

### Claude Desktop

Edit `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/`; Windows: `%APPDATA%\Claude\`):

```json
{
  "mcpServers": {
    "astromcp": {
      "command": "uvx",
      "args": ["astromcp"],
      "env": { "TNS_BOT_ID": "12345", "TNS_BOT_NAME": "my_bot", "TNS_API_KEY": "..." }
    }
  }
}
```

The `env` block is optional.

### Other clients (Cursor, VS Code, Zed, Continue, ...)

Any client that launches stdio MCP servers works with command `uvx` and args `["astromcp"]`, or command
`astromcp` if you installed it with pip. Try it interactively with the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector uvx astromcp
```

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `TNS_BOT_ID`, `TNS_BOT_NAME`, `TNS_API_KEY` | unset | Optional TNS **bot** credentials ([create a bot](https://www.wis-tns.org/bots)) for live TNS queries |
| `TNS_PUBLIC_CSV` | unset | Path to a downloaded `tns_public_objects.csv.zip`, used when there are no credentials |
| `ASTROMCP_CACHE_DIR` | `~/.cache/astromcp` | Disk cache (HTTP responses for minutes to hours; ExoFOP tables 12 h; TNS archive 20 h) |

Without TNS credentials, TNS answers come from the daily public objects archive (cached copy or `TNS_PUBLIC_CSV`);
objects reported since 00:00 UTC are missing from it, and `whats_here` flags this instead of returning a clean
"nothing known". The API key is never returned in responses, written to logs, or stored in the cache.

## Rate limits and good citizenship

These archives are free public services run by small teams. AstroMCP is built to be polite:

- TNS cone searches are serialized and spaced 6.5 s apart (TNS allows 10 per minute); `Retry-After` is honored on HTTP 429.
- Every request has a timeout, retries with backoff, and a per-host circuit breaker: when a host fails
  repeatedly it is skipped for two minutes instead of stalling every query.
- Large tables (ExoFOP TOI/CTOI, TNS public archive) are downloaded once and cached on disk.

Please do the same: don't run `whats_here` over thousands of positions in a loop (use the archives' bulk
services for that), keep your own TNS bot for live queries, and credit the archives in publications
(TNS, SIMBAD/CDS, AAVSO VSX, ESA Gaia, ExoFOP-TESS, ALeRCE, Fink, IMCCE, Legacy Survey, Pan-STARRS).

## Development

```bash
git clone https://github.com/louisperner/AstroMCP && cd AstroMCP
uv sync
uv run pytest                      # offline tests (recorded responses in tests/fixtures)
uv run pytest -m integration       # live queries against the real archives (TNS test needs credentials)
uv run ruff check . && uv run ruff format --check . && uv run mypy --strict
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CHANGELOG.md](CHANGELOG.md).

### Publishing to the MCP Registry (maintainers)

`server.json` describes the PyPI package for the official [MCP Registry](https://github.com/modelcontextprotocol/registry).
After the version is on PyPI (the `mcp-name` comment above must be in the published README):

```bash
brew install mcp-publisher        # or download a release binary
mcp-publisher login github        # authenticates the io.github.louisperner namespace
mcp-publisher publish             # reads ./server.json
```

Bump `version` in `pyproject.toml`, `src/astromcp/__init__.py` and both places in `server.json` together.

## Em português

O AstroMCP é um servidor MCP que dá a assistentes de IA acesso direto (somente leitura) a bases públicas de
astronomia — TNS, SIMBAD, VSX, Gaia DR3, ExoFOP-TESS, ALeRCE/ZTF, Fink/Rubin, SkyBoT e cutouts de imagem —
para verificar rapidamente se um objeto já é conhecido. Comece por `whats_here(ra, dec)`; para planejar a noite,
`observe_tonight(lat, lon)`. Instale com `uvx astromcp` ou `pip install astromcp` e, no Claude Code,
`claude mcp add astromcp -- uvx astromcp`. Credenciais do bot do TNS (opcionais) vão nas variáveis
`TNS_BOT_ID`, `TNS_BOT_NAME` e `TNS_API_KEY` e nunca aparecem nas respostas. As respostas dependem de serviços
externos: confirme na fonte antes de anunciar uma descoberta.

## License

[MIT](LICENSE) © 2026 Louis Perner
