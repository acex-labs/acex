FROM python:3.13-slim@sha256:d0a9e379c0c588befb0e427db17ca9731751d281f32c6cb1a90a1277b680bdad

WORKDIR /app

RUN pip install poetry && poetry config virtualenvs.create false

COPY client/ /deps/client/
COPY devkit/ /deps/devkit/

COPY agents/grafana-sync/ /app/

RUN sed -i 's|../../client|/deps/client|' pyproject.toml && \
    pip install /deps/devkit && \
    poetry install --no-interaction

ENTRYPOINT ["acex-grafana-sync"]
