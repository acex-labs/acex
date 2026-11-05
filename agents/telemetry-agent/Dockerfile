FROM python:3.13-slim@sha256:d0a9e379c0c588befb0e427db17ca9731751d281f32c6cb1a90a1277b680bdad

WORKDIR /app

RUN pip install poetry && poetry config virtualenvs.create false

# Copy client dependency
COPY client/ /deps/client/
COPY devkit/ /deps/devkit/

# Copy agent
COPY agents/telemetry-agent/ /app/

# Adjust paths for container context
RUN sed -i 's|../../client|/deps/client|' pyproject.toml && \
    poetry install --no-interaction && \
    pip install /deps/devkit

ARG BUILD_ID=""
ENV ACEX_BUILD_ID=$BUILD_ID
ARG BUILD_REF=""
ENV ACEX_BUILD_REF=$BUILD_REF

ENTRYPOINT ["acex-telemetry-agent"]
