FROM python:3.13-slim@sha256:d0a9e379c0c588befb0e427db17ca9731751d281f32c6cb1a90a1277b680bdad

# Same layout as the pyproject path dependencies (../client, ../devkit) expect.
COPY devkit/ /deps/devkit/
COPY client/ /deps/client/
COPY worker/pyproject.toml /deps/worker/pyproject.toml
COPY worker/README.md /deps/worker/README.md
COPY worker/src/ /deps/worker/src/

# Pinned versions of the third-party dependencies, written by scripts/lock-images.sh.
COPY worker/constraints.txt /deps/constraints.txt

# NEDs are not baked in: the worker downloads them from the API at startup and
# pip-installs them, so it needs a package index for their dependencies.
RUN pip install --no-cache-dir -c /deps/constraints.txt /deps/devkit /deps/client /deps/worker

# ACEX_BASE_URL, ACEX_CLIENT_ID and ACEX_CLIENT_SECRET are set by the deployment.
ENTRYPOINT ["acex-worker"]