# Contributing to AstroMCP

Thanks for helping! Bug reports, new archive sources and fixes are welcome.

## Setup

```bash
git clone https://github.com/louisperner/AstroMCP && cd AstroMCP
uv sync
```

## Before opening a pull request

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict
uv run pytest                    # offline; integration tests are skipped by default
```

CI runs the same checks on Python 3.11, 3.12 and 3.13.

## Guidelines

- **Tests are offline.** Record a real (trimmed) archive response in `tests/fixtures/` and test the parser
  against it. Live checks go in `tests/test_integration.py` with the `integration` marker
  (`uv run pytest -m integration`).
- **Be polite to the archives.** New sources must go through `astromcp.net` (timeouts, retries, circuit
  breaker, cache) and respect the service's published rate limits.
- **Never leak credentials.** Keys must not appear in responses, logs or cache keys; use `net.redact`.
- **Failures are explicit.** A source that fails must show up in `sources_failed`, never as "nothing known".
- Keep tool responses compact JSON with ICRS decimal degrees and ISO 8601 UTC times.
- Add a line to `CHANGELOG.md` under "Unreleased".

## Reporting bugs

Include the tool call (name and arguments), the response, and the date/time (UTC): archive contents change.
