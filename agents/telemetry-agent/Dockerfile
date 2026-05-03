FROM python:3.13-slim

WORKDIR /app

RUN pip install poetry && poetry config virtualenvs.create false

# Copy client dependency
COPY client/ /deps/client/
COPY devkit/ /deps/devkit/

# Copy agent
COPY agents/telemetry-agent/ /app/

# Adjust paths for container context
RUN sed -i 's|../../client|/deps/client|' pyproject.toml && \
    pip install /deps/devkit && \
    poetry install --no-interaction

ENTRYPOINT ["acex-telemetry-agent"]
