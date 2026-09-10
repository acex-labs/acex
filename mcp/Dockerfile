FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir poetry && poetry config virtualenvs.create false

# Placed so the path dependencies resolve as written: "../client" from /app is
# /client, and client's own "../devkit" is /devkit. Rewriting the paths instead
# would change pyproject.toml and invalidate poetry.lock's content hash.
COPY client/ /client/
COPY devkit/ /devkit/

# Manifests first so the dependency layer caches across source edits.
COPY mcp/pyproject.toml mcp/poetry.lock mcp/README.md /app/
RUN poetry install --no-interaction --only main --no-root

COPY mcp/src/ /app/src/
RUN poetry install --no-interaction --only main

RUN useradd --create-home --uid 10001 acex
USER acex

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD python -c "import os,socket; socket.create_connection(('127.0.0.1', int(os.environ.get('ACEX_MCP_PORT','8000'))), 2).close()"

CMD ["python", "-m", "acex_mcp"]
