#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${GAONONE_ROOT:-/home/ubuntu/gaonone}"
SERVICE_SRC="$ROOT_DIR/deploy/systemd/gaonone-maintenance.service"
TIMER_SRC="$ROOT_DIR/deploy/systemd/gaonone-maintenance.timer"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with sudo: sudo bash deploy/install_maintenance_timer.sh" >&2
  exit 1
fi
if [[ ! -d "$ROOT_DIR/.git" || ! -f "$ROOT_DIR/.env.production" ]]; then
  echo "GaonOne production checkout or .env.production not found at $ROOT_DIR" >&2
  exit 1
fi
if [[ ! -f "$SERVICE_SRC" || ! -f "$TIMER_SRC" ]]; then
  echo "Maintenance unit files are missing." >&2
  exit 1
fi

# Keep the unit portable if the checkout path is overridden.
sed "s|WorkingDirectory=/home/ubuntu/gaonone|WorkingDirectory=$ROOT_DIR|" "$SERVICE_SRC" >/etc/systemd/system/gaonone-maintenance.service
install -m 0644 "$TIMER_SRC" /etc/systemd/system/gaonone-maintenance.timer
systemctl daemon-reload
systemctl enable --now gaonone-maintenance.timer

echo "=== GaonOne maintenance timer ==="
systemctl status gaonone-maintenance.timer --no-pager
systemctl list-timers gaonone-maintenance.timer --no-pager
