FROM python:3.13-slim@sha256:d0a9e379c0c588befb0e427db17ca9731751d281f32c6cb1a90a1277b680bdad

WORKDIR /app

RUN pip install poetry && poetry config virtualenvs.create false

# Placed so the path dependencies resolve as written: "../../client" from /app is
# /client (the extra ".." stops at the root), and client's own "../devkit" is
# /devkit. Rewriting the paths instead would change pyproject.toml and invalidate
# poetry.lock's content hash. The lock also holds devkit as a path package, so the
# local devkit is installed without a separate pip install.
COPY client/ /client/
COPY devkit/ /devkit/

# Manifests first so the dependency layer caches across source edits.
COPY agents/grafana-sync/pyproject.toml agents/grafana-sync/poetry.lock agents/grafana-sync/README.md /app/
RUN poetry install --no-interaction --only main --no-root

COPY agents/grafana-sync/src/ /app/src/
RUN poetry install --no-interaction --only main

ENTRYPOINT ["acex-grafana-sync"]
