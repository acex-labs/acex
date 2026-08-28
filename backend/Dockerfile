FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# Local dependencies
COPY devkit/ /deps/devkit/
COPY client/ /deps/client/
COPY drivers/cisco_ios_cli/ /deps/cisco_ios_cli/
RUN sed -i 's|acex-devkit = .*|acex-devkit = ">=2"|' /deps/cisco_ios_cli/pyproject.toml && \
    pip install --no-cache-dir /deps/devkit /deps/client /deps/cisco_ios_cli

# Runtime dependencies
RUN pip install --no-cache-dir \
    uvicorn \
    fastapi \
    sqlmodel \
    requests \
    "python-jose[cryptography]" \
    psycopg2-binary \
    jinja2 \
    openai \
    mcp \
    fastmcp \
    cryptography \
    hvac

# Backend source
COPY backend/src/ /app/src/
COPY backend/app.dev.py /app/app.dev.py

ENV PYTHONPATH=/app/src

CMD ["python", "app.dev.py"]