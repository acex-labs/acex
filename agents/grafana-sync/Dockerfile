FROM python:3.13-slim

WORKDIR /app

RUN pip install poetry && poetry config virtualenvs.create false

COPY client/ /deps/client/
COPY devkit/ /deps/devkit/

COPY agents/grafana-sync/ /app/

RUN sed -i 's|../../client|/deps/client|' pyproject.toml && \
    pip install /deps/devkit && \
    poetry install --no-interaction

ENTRYPOINT ["acex-grafana-sync"]
