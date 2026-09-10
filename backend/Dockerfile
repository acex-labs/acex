FROM python:3.13-slim

RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# Local dependencies
COPY devkit/ /deps/devkit/
COPY client/ /deps/client/
COPY drivers/cisco_ios_cli/ /deps/cisco_ios_cli/

# Backend source (installed with pip like the other local packages)
COPY backend/pyproject.toml /deps/backend/pyproject.toml
COPY backend/README.md /deps/backend/README.md
COPY backend/src/ /deps/backend/src/

# Replace local path dependencies with version requirements
RUN sed -i 's|acex-devkit = .*|acex-devkit = ">=2"|' /deps/cisco_ios_cli/pyproject.toml && \
    sed -i 's|acex-devkit = .*|acex-devkit = ">=2"|' /deps/backend/pyproject.toml && \
    pip install --no-cache-dir /deps/devkit /deps/client /deps/cisco_ios_cli /deps/backend[vault]

CMD ["python", "-m", "acex"]
