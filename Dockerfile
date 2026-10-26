# Runs AstroMCP over stdio: docker run -i --rm [-e TNS_BOT_ID=... -e TNS_BOT_NAME=... -e TNS_API_KEY=...] astromcp
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable && useradd -m astro
USER astro
ENV ASTROMCP_CACHE_DIR=/home/astro/.cache/astromcp
ENTRYPOINT ["/app/.venv/bin/astromcp"]
