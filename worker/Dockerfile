FROM python:3.13-slim

# Same layout as the pyproject path dependencies (../client, ../devkit) expect.
COPY devkit/ /deps/devkit/
COPY client/ /deps/client/
COPY worker/pyproject.toml /deps/worker/pyproject.toml
COPY worker/README.md /deps/worker/README.md
COPY worker/src/ /deps/worker/src/

# NEDs are not baked in: the worker downloads them from the API at startup and
# pip-installs them, so it needs a package index for their dependencies.
RUN pip install --no-cache-dir /deps/devkit /deps/client /deps/worker

# ACEX_BASE_URL, ACEX_CLIENT_ID and ACEX_CLIENT_SECRET are set by the deployment.
ENTRYPOINT ["acex-worker"]