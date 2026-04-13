#!/usr/bin/env bash
# Run on the VPS (invoked by GitHub Actions over SSH).
# Expects a git clone of this repo at $ROOT (e.g. /opt/auto-concierge-v1).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BRANCH="${DEPLOY_BRANCH:-main}"

if [ ! -d .git ]; then
  echo "ERROR: $ROOT is not a git clone."
  echo "One-time setup: see docs/DEPLOY_CI_CD.md (init git on VPS)."
  exit 1
fi

echo ">>> Fetch origin / reset to origin/${BRANCH}"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git reset --hard "origin/${BRANCH}"

if command -v docker-compose >/dev/null 2>&1; then
  DC=(docker-compose)
else
  DC=(docker compose)
fi

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
export COMPOSE_FILE

echo ">>> docker compose build (backend worker frontend)"
"${DC[@]}" -f "$COMPOSE_FILE" build backend worker frontend

echo ">>> docker compose up -d"
"${DC[@]}" -f "$COMPOSE_FILE" up -d

echo ">>> alembic upgrade head"
"${DC[@]}" -f "$COMPOSE_FILE" exec -T backend alembic upgrade head

echo ">>> status"
"${DC[@]}" -f "$COMPOSE_FILE" ps

echo "Deploy finished OK."
