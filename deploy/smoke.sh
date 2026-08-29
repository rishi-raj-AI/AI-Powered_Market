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

secret_status="$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 15 "${BASE}/.env")"
[[ "$secret_status" == "404" ]] || { echo "Expected /.env to return 404, got $secret_status" >&2; exit 1; }
root_post_status="$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 15 -X POST "${BASE}/")"
[[ "$root_post_status" == "405" ]] || { echo "Expected POST / to return 405, got $root_post_status" >&2; exit 1; }

if [[ -n "${PILOT_VILLAGE_LATITUDE:-}" && -n "${PILOT_VILLAGE_LONGITUDE:-}" ]]; then
  serviceability="$(curl --fail --silent --show-error --max-time 15 \
    "${BASE}/api/v1/location/serviceability?latitude=${PILOT_VILLAGE_LATITUDE}&longitude=${PILOT_VILLAGE_LONGITUDE}")"
  python3 - "$serviceability" <<'PY'
import json, sys
payload=json.loads(sys.argv[1])
if payload.get("serviceable") is not True:
    raise SystemExit(f"Pilot hub unexpectedly not serviceable: {payload}")
print("Pilot serviceability OK:", payload.get("service_area_name") or payload.get("service_area_id"))
PY
fi

echo "GaonOne production smoke checks passed."
