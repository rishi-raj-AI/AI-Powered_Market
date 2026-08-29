#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${GAONONE_ROOT:-/home/ubuntu/gaonone}"
RUNNER_USER="${GAONONE_RUNNER_USER:-ubuntu}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with sudo: sudo bash deploy/install_deploy_runner.sh" >&2
  exit 1
fi
if [[ ! -d "$ROOT_DIR/.git" || ! -f "$ROOT_DIR/.env.production" ]]; then
  echo "GaonOne checkout or .env.production missing at $ROOT_DIR" >&2
  exit 1
fi

# Permit the dedicated GitHub Actions runner job to invoke only the audited
# GaonOne release entry point as root. No shell, Docker or arbitrary sudo grant.
SUDOERS_FILE="/etc/sudoers.d/gaonone-deploy"
printf '%s ALL=(root) NOPASSWD: %s/deploy/release.sh\n' "$RUNNER_USER" "$ROOT_DIR" > "$SUDOERS_FILE"
chmod 0440 "$SUDOERS_FILE"
visudo -cf "$SUDOERS_FILE"

chmod 0755 "$ROOT_DIR/deploy/release.sh"

echo "GaonOne deploy permission installed for $RUNNER_USER."
echo "Next: register a GitHub self-hosted runner with labels: gaonone-production"
echo "Then install/start it with the runner's svc.sh service commands."
