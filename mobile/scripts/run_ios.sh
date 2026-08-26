#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOBILE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
API_URL="${API_URL:-http://127.0.0.1:8000/api/v1}"
DEVICE_ID="${DEVICE_ID:-}"
LOG_FILE="$MOBILE_DIR/ios_run.log"
ERROR_FILE="$MOBILE_DIR/ios_error_summary.log"

cd "$MOBILE_DIR"

bash "$SCRIPT_DIR/ios_preflight.sh"

flutter clean
rm -rf build
flutter pub get

if [[ -z "$DEVICE_ID" ]]; then
  DEVICE_ID="$(flutter devices --machine | python3 -c 'import json,sys; devices=json.load(sys.stdin); sims=[d for d in devices if d.get("targetPlatform")=="ios" and d.get("emulator")]; print(sims[0]["id"] if sims else "")')"
fi

if [[ -z "$DEVICE_ID" ]]; then
  echo "[FAIL] No booted/available iOS Simulator detected." >&2
  echo "Open Simulator, then rerun this script." >&2
  exit 1
fi

echo "Launching GaonOne on iOS Simulator: $DEVICE_ID"
echo "API: $API_URL"
echo "Verbose log: $LOG_FILE"

rm -f "$LOG_FILE" "$ERROR_FILE"

set +e
flutter run -v -d "$DEVICE_ID" --dart-define="API_URL=$API_URL" 2>&1 | tee "$LOG_FILE"
STATUS=${PIPESTATUS[0]}
set -e

if [[ $STATUS -ne 0 ]]; then
  grep -n -i -E "error:|codesign|resource fork|Finder information|provenance|debug_unpack_ios|failed|exception" "$LOG_FILE" | tail -80 > "$ERROR_FILE" || true

  echo >&2
  echo "[IOS BUILD FAILED]" >&2
  echo "Error summary saved to: $ERROR_FILE" >&2

  if [[ -s "$ERROR_FILE" ]]; then
    echo >&2
    echo "--- Relevant build errors ---" >&2
    cat "$ERROR_FILE" >&2
    echo "--- End build errors ---" >&2
  else
    echo "No known error signature was extracted. Review $LOG_FILE." >&2
  fi

  if grep -q "resource fork, Finder information, or similar detritus not allowed" "$LOG_FILE"; then
    cat >&2 <<'EOF'

[BLOCKED BY TOOLCHAIN]
Flutter reached the iOS codesigning stage but macOS/Xcode rejected Flutter.framework because of extended metadata.
This is an upstream Flutter/macOS 26/Xcode 26 issue, not a GaonOne source-code failure.
EOF
  fi

  exit "$STATUS"
fi

echo "[OK] GaonOne launched successfully on iOS Simulator."
