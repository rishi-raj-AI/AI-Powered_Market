#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f .env.production ]]; then
  echo "Missing .env.production" >&2
  exit 1
fi

set -a
source .env.production
set +a

BASE="https://${DOMAIN}"

echo "Checking ${BASE}"
curl --fail --silent --show-error --max-time 15 "${BASE}/api/v1/health" | tee /tmp/gaonone-health.json
echo
curl --fail --silent --show-error --max-time 15 "${BASE}/api/v1/health/ready" | tee /tmp/gaonone-ready.json
echo
curl --fail --silent --show-error --max-time 15 -o /dev/null "${BASE}/"

echo "GaonOne production smoke checks passed."
