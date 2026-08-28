#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env.production ]]; then
  echo "Missing .env.production"
  exit 1
fi

echo "Docker disk usage before cleanup:"
docker system df

echo "Removing stopped containers, dangling images and build cache older than 24h..."
docker container prune -f
docker image prune -f
docker builder prune -f --filter "until=24h"

echo "Docker disk usage after cleanup:"
docker system df

echo "GaonOne production Docker cleanup complete."
