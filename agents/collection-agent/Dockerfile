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

# NEDs are deliberately not baked in: the drivers live in the backend image, and
# the agent downloads the wheels it needs from the API and pip-installs them at
# runtime (CollectionAgent._ensure_neds). The container therefore needs to reach
# a package index for the drivers' own dependencies.

# Manifests first so the dependency layer caches across source edits.
COPY agents/collection-agent/pyproject.toml agents/collection-agent/poetry.lock agents/collection-agent/README.md /app/
RUN poetry install --no-interaction --only main --no-root

COPY agents/collection-agent/src/ /app/src/
RUN poetry install --no-interaction --only main

ARG BUILD_ID=""
ENV ACEX_BUILD_ID=$BUILD_ID
ARG BUILD_REF=""
ENV ACEX_BUILD_REF=$BUILD_REF

ENTRYPOINT ["acex-collection-agent"]
