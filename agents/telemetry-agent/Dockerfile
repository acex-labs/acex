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
COPY agents/telemetry-agent/pyproject.toml agents/telemetry-agent/poetry.lock agents/telemetry-agent/README.md /app/
RUN poetry install --no-interaction --only main --no-root

COPY agents/telemetry-agent/src/ /app/src/
RUN poetry install --no-interaction --only main

ARG BUILD_ID=""
ENV ACEX_BUILD_ID=$BUILD_ID
ARG BUILD_REF=""
ENV ACEX_BUILD_REF=$BUILD_REF

ENTRYPOINT ["acex-telemetry-agent"]
