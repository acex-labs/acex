FROM python:3.13-slim

WORKDIR /app

RUN pip install poetry && poetry config virtualenvs.create false

COPY mcp/ /app/

RUN poetry install --no-interaction

EXPOSE 8000

ENTRYPOINT ["acex-mcp"]
