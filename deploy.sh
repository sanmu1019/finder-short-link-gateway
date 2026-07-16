#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "Missing .env. Run: cp .env.example .env" >&2
  exit 1
fi

docker compose build finder-gateway
docker compose up -d finder-gateway
docker compose ps

echo
echo "Finder health:"
curl --fail --silent http://127.0.0.1:8790/health
echo
echo "Optional parser:"
echo "docker compose --profile wxsph up -d --build wxsph-api"
