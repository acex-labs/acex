FROM python:3.13-slim

WORKDIR /app

RUN pip install poetry && poetry config virtualenvs.create false

# Copy local dependencies
COPY client/ /deps/client/
COPY devkit/ /deps/devkit/
COPY drivers/cisco_ios_cli/ /deps/cisco_ios_cli/

# Copy agent
COPY agents/collection-agent/ /app/

# Adjust paths for container context, fix ned path dep, install everything
RUN sed -i 's|../../client|/deps/client|' pyproject.toml && \
    sed -i 's|acex-devkit = .*|acex-devkit = ">=2"|' /deps/cisco_ios_cli/pyproject.toml && \
    pip install /deps/devkit && \
    pip install /deps/cisco_ios_cli && \
    poetry install --no-interaction

ENTRYPOINT ["acex-collection-agent"]
