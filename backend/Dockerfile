FROM python:3.13-slim@sha256:d0a9e379c0c588befb0e427db17ca9731751d281f32c6cb1a90a1277b680bdad

RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# Local dependencies
COPY devkit/ /deps/devkit/
COPY client/ /deps/client/
COPY drivers/cisco_ios_cli/ /deps/cisco_ios_cli/
COPY drivers/juniper_junos_cli/ /deps/juniper_junos_cli/

# Backend source (installed with pip like the other local packages)
COPY backend/pyproject.toml /deps/backend/pyproject.toml
COPY backend/README.md /deps/backend/README.md
COPY backend/src/ /deps/backend/src/

# Release notes of the components that run as their own service. They are not installed
# here, so the backend serves their compiled files from this directory (Settings > What's new).
COPY cli/src/acex_cli/changelog.json /deps/backend/src/acex/changelog_components/acex-cli.json
COPY mcp/src/acex_mcp/changelog.json /deps/backend/src/acex/changelog_components/acex-mcp.json
COPY worker/src/acex_worker/changelog.json /deps/backend/src/acex/changelog_components/acex-worker.json
COPY agents/collection-agent/src/acex_collection_agent/changelog.json /deps/backend/src/acex/changelog_components/acex-collection-agent.json
COPY agents/telemetry-agent/src/acex_telemetry_agent/changelog.json /deps/backend/src/acex/changelog_components/acex-telemetry-agent.json
COPY agents/grafana-sync/src/acex_grafana_sync/changelog.json /deps/backend/src/acex/changelog_components/acex-grafana-sync.json

# Pinned versions of the third-party dependencies, written by scripts/lock-images.sh.
COPY backend/constraints.txt /deps/constraints.txt

# Replace local path dependencies with version requirements
RUN sed -i 's|acex-devkit = .*|acex-devkit = ">=2"|' /deps/cisco_ios_cli/pyproject.toml && \
    sed -i 's|acex-devkit = .*|acex-devkit = ">=2"|' /deps/juniper_junos_cli/pyproject.toml && \
    sed -i 's|acex-devkit = .*|acex-devkit = ">=2"|' /deps/backend/pyproject.toml && \
    pip install --no-cache-dir -c /deps/constraints.txt /deps/devkit /deps/client /deps/cisco_ios_cli /deps/juniper_junos_cli /deps/backend[vault]


ARG BUILD_ID=""
ENV ACEX_BUILD_ID=$BUILD_ID
ARG BUILD_REF=""
ENV ACEX_BUILD_REF=$BUILD_REF


CMD ["python", "-m", "acex_api"]
