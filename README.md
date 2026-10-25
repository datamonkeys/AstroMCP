# AstroMCP

An [MCP](https://modelcontextprotocol.io) server that gives AI assistants direct, read-only access to
public astronomy archives, so astronomers can check an object in seconds: *is it already known?*

| Tool | What it does | Sources |
|---|---|---|
| `whats_here(ra, dec, radius_arcsec=5, epoch=None)` | Queries everything below in parallel and returns a verdict (`known transient`, `known TESS object of interest`, `known variable`, `known asteroid`, `star`, `known object`, `nothing known`), all matching labels, one-line evidence, failed sources and image links | all |
| `tns_object(name)` / `tns_search(ra, dec, radius_arcsec)` | Transient Name Server lookup / cone search | TNS API or daily public archive |
| `ztf_lightcurve(oid)` / `ztf_objects_near(ra, dec, radius_arcsec)` | ZTF light curve (detections with `magpsf` and `magpsf_corr`, non-detection summary) / objects near a position | ALeRCE |
| `rubin_object(dia_object_id)` / `rubin_recent(tag, days)` | Rubin/LSST object light curve and cutouts / recent objects in a Fink tag | Fink LSST |
| `simbad`, `vsx`, `gaia` `(ra, dec, radius_arcsec)` | Cone searches | SIMBAD TAP, AAVSO VSX, Gaia DR3 (VizieR) |
| `tess_known(tic=None, ra=None, dec=None)` | TOIs, CTOIs and TESS eclipsing binaries | ExoFOP-TESS, VizieR J/ApJS/258/16, TIC v8.2 |
| `asteroids_at(ra, dec, epoch_iso, radius_arcsec)` | Known solar-system objects at a position and time | IMCCE SkyBoT |
| `cutout_urls(ra, dec, size_arcsec)` | Image links | Legacy Survey DR10, Pan-STARRS, DSS2, Aladin |

Coordinates are ICRS decimal degrees; times are ISO 8601 UTC. Responses are compact JSON; errors come back as
`{"error": "..."}` and, in `whats_here`, as `sources_failed` plus a `caveat` so a missing archive is never
mistaken for "nothing known".


### `observe_tonight` — what to observe tonight

Recent (default ≤ 21 days), bright (TNS discovery mag ≤ 18.5) transients that are **still unclassified**
on TNS and observable from your site tonight (above 30° while the Sun is below −12°, ≥ 20° from the Moon),
ranked by brightness, age and window length. Built to help small telescopes and spectroscopy groups pick
classification targets. Example: `observe_tonight(lat=-25.43, lon=-49.27)` (Curitiba).
Sun/Moon from the Astronomical Almanac low-precision formulas (arcminute level; tests check Polaris,
equinox/solstice and the 2026-10-26 full Moon).

## Install

Requires [uv](https://docs.astral.sh/uv/) and Python 3.13+.

```bash
git clone <this repo> AstroMCP && cd AstroMCP
uv sync
uv run astromcp        # starts the server on stdio (what MCP clients do for you)
```

### TNS credentials (optional but recommended)

Live TNS queries need a TNS **bot** ([create one](https://www.wis-tns.org/bots)). Set:

```bash
export TNS_BOT_ID=12345 TNS_BOT_NAME=my_bot TNS_API_KEY=...
```

Without them, TNS answers come from the daily public objects archive if a copy exists in the cache directory
(or point `TNS_PUBLIC_CSV` at a downloaded `tns_public_objects.csv.zip`); objects reported since 00:00 UTC are
missing from it. The key is never returned in responses, written to logs, or stored in the cache (cache keys are hashes).

### Other environment variables

| Variable | Default | Meaning |
|---|---|---|
| `ASTROMCP_CACHE_DIR` | `~/.cache/astromcp` | Disk cache (HTTP responses for minutes to hours; ExoFOP tables 12 h; TNS archive 20 h) |

## Add to an MCP client

### Claude Code

```bash
claude mcp add astromcp -- uv run --directory /path/to/AstroMCP astromcp
# with TNS credentials:
claude mcp add astromcp -e TNS_BOT_ID=12345 -e TNS_BOT_NAME=my_bot -e TNS_API_KEY=... \
  -- uv run --directory /path/to/AstroMCP astromcp
```

Add `--scope user` to make it available in every project.

### Claude Desktop

Edit `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/`; Windows: `%APPDATA%\Claude\`):

```json
{
  "mcpServers": {
    "astromcp": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/AstroMCP", "astromcp"],
      "env": { "TNS_BOT_ID": "12345", "TNS_BOT_NAME": "my_bot", "TNS_API_KEY": "..." }
    }
  }
}
```

### Other clients (Cursor, VS Code, Zed, Continue, ...)

Any client that launches stdio MCP servers works with command `uv` and args
`["run", "--directory", "/path/to/AstroMCP", "astromcp"]` (or `python -m astromcp` inside the venv).
Try it interactively with the MCP Inspector: `npx @modelcontextprotocol/inspector uv run --directory . astromcp`.

## Good citizenship

- TNS cone searches are serialized and spaced 6.5 s apart (TNS allows 10/min); `Retry-After` is honored on HTTP 429.
- Every request has a timeout, retries with backoff, and a per-host circuit breaker: when VizieR (or any host)
  fails repeatedly it is skipped for two minutes instead of stalling every query.
- Large tables (ExoFOP TOI/CTOI, TNS archive) are downloaded once and cached.

## Development

```bash
uv run pytest                      # offline tests (recorded responses in tests/fixtures)
uv run pytest -m integration       # live queries against the real archives (TNS test needs credentials)
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

`tests/fixtures/skybot_*.txt` follow the documented SkyBoT text format (the service was down when the
others were recorded); everything else is a real archive response, trimmed where large.

## Em português

O AstroMCP é um servidor MCP que dá a assistentes de IA acesso direto (somente leitura) a bases públicas de
astronomia — TNS, SIMBAD, VSX, Gaia DR3, ExoFOP-TESS, ALeRCE/ZTF, Fink/Rubin, SkyBoT e cutouts de imagem —
para verificar rapidamente se um objeto já é conhecido. Comece por `whats_here(ra, dec)`. Para usar no
Claude Code: `claude mcp add astromcp -- uv run --directory /caminho/AstroMCP astromcp`. Credenciais do bot do
TNS vão nas variáveis `TNS_BOT_ID`, `TNS_BOT_NAME` e `TNS_API_KEY` (nunca aparecem nas respostas).

## License

MIT
