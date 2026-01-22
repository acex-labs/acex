# Base image (same as devcontainer.json)
FROM mcr.microsoft.com/devcontainers/python:2-3.13-trixie

# Install pipx + poetry
RUN pip install --no-cache-dir pipx \
    && pipx ensurepath \
    && pipx install poetry \
    && pipx inject poetry poetry-plugin-shell

# Set working directory
# WORKDIR /workspace