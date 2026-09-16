FROM python:3.13-slim

WORKDIR /app

RUN pip install poetry && poetry config virtualenvs.create false

# Copy local dependencies
COPY client/ /deps/client/
COPY devkit/ /deps/devkit/

# Copy agent
COPY agents/collection-agent/ /app/

# NEDs are deliberately not baked in: the drivers live in the backend image, and
# the agent downloads the wheels it needs from the API and pip-installs them at
# runtime (CollectionAgent._ensure_neds). The container therefore needs to reach
# a package index for the drivers' own dependencies.

# Adjust paths for container context and install everything
RUN sed -i 's|../../client|/deps/client|' pyproject.toml && \
    pip install /deps/devkit && \
    poetry install --no-interaction

ENTRYPOINT ["acex-collection-agent"]
