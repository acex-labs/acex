#!/usr/bin/env bash
set -euo pipefail

FRONTEND_REPO="https://github.com/acex-labs/acex-frontend.git"
FRONTEND_DEFAULT="../acex-frontend"

log()  { echo "▸ $*"; }
ok()   { echo "✓ $*"; }
warn() { echo "! $*"; }

# Prerequisites
if ! command -v docker &>/dev/null; then
  echo "Error: docker is not installed." >&2; exit 1
fi
if ! docker compose version &>/dev/null; then
  echo "Error: docker compose (v2) is not available." >&2; exit 1
fi

# /etc/hosts — keycloak must resolve to localhost so the browser and backend
# use the same issuer URL (http://keycloak:8180/realms/acex) in JWT tokens.
if grep -qE '^\s*127\.0\.0\.1\s+keycloak' /etc/hosts 2>/dev/null; then
  ok "keycloak already in /etc/hosts"
else
  log "Adding '127.0.0.1 keycloak' to /etc/hosts (requires sudo)…"
  echo "127.0.0.1 keycloak" | sudo tee -a /etc/hosts > /dev/null
  ok "keycloak added to /etc/hosts"
fi

# .env
if [ ! -f .env ]; then
  log "Creating .env from .env.example"
  cp .env.example .env
  ok ".env created — edit it if you need custom passwords or paths"
else
  ok ".env already exists"
fi

# Load FRONTEND_PATH from .env (if set)
FRONTEND_PATH=$(grep -E '^FRONTEND_PATH=' .env | cut -d= -f2- | tr -d '"' || true)
FRONTEND_PATH="${FRONTEND_PATH:-$FRONTEND_DEFAULT}"

# Clone frontend if missing
if [ ! -d "$FRONTEND_PATH" ]; then
  log "Cloning acex-frontend to $FRONTEND_PATH"
  git clone "$FRONTEND_REPO" "$FRONTEND_PATH"
  ok "acex-frontend cloned"
else
  ok "acex-frontend found at $FRONTEND_PATH"
fi

# Build and start
log "Building images (this takes a few minutes on first run)…"
FRONTEND_PATH="$FRONTEND_PATH" docker compose build

log "Starting stack…"
FRONTEND_PATH="$FRONTEND_PATH" docker compose up -d

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ACEX is starting up"
echo ""
echo "  Frontend   http://localhost:3000"
echo "  Backend    http://localhost:8080"
echo "  Keycloak   http://keycloak:8180   (admin / admin)"
echo "  Grafana    http://localhost:3001  (admin / admin)"
echo ""
echo "  Default login: admin / admin"
echo ""
echo "  Keycloak may take ~30 s on first boot."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
