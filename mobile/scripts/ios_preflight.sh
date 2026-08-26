#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MOBILE_DIR="$PROJECT_ROOT/mobile"

fail() {
  printf '\n[FAIL] %s\n' "$1" >&2
  exit 1
}

ok() {
  printf '[OK] %s\n' "$1"
}

command -v flutter >/dev/null 2>&1 || fail "Flutter is not installed or is not on PATH."
command -v xcodebuild >/dev/null 2>&1 || fail "Xcode command-line tools are unavailable."
command -v pod >/dev/null 2>&1 || fail "CocoaPods is unavailable."

FLUTTER_VERSION="$(flutter --version | head -n 1)"
XCODE_VERSION="$(xcodebuild -version | tr '\n' ' ')"
MACOS_VERSION="$(sw_vers -productVersion)"

ok "$FLUTTER_VERSION"
ok "$XCODE_VERSION"
ok "macOS $MACOS_VERSION"
ok "CocoaPods $(pod --version)"

if [[ ! -d "$MOBILE_DIR/ios" ]]; then
  fail "mobile/ios does not exist. Generate native projects with: cd mobile && flutter create . --platforms=ios,android --org in.gaonone"
fi

if ! xcrun simctl list devices available | grep -q 'iPhone'; then
  fail "No available iPhone simulator was found. Open Xcode > Settings > Components and install an iOS Simulator runtime."
fi

# Best-effort cleanup. On macOS 26, com.apple.provenance may be synthesized by the OS
# and can remain even after xattr reports success; this command is intentionally non-fatal.
xattr -cr "$MOBILE_DIR" 2>/dev/null || true

FLUTTER_BIN="$(command -v flutter)"
if command -v python3 >/dev/null 2>&1; then
  FLUTTER_BIN="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$FLUTTER_BIN")"
fi
FLUTTER_ROOT="$(cd "$(dirname "$FLUTTER_BIN")/.." && pwd)"
ENGINE_DIR="$FLUTTER_ROOT/bin/cache/artifacts/engine"
if [[ -d "$ENGINE_DIR" ]]; then
  xattr -cr "$ENGINE_DIR" 2>/dev/null || true
fi

printf '\nPreflight complete.\n'
printf 'If Flutter still fails at debug_unpack_ios with "resource fork, Finder information, or similar detritus not allowed",\n'
printf 'the failure is the known macOS 26 / Xcode 26 Flutter framework codesigning issue rather than GaonOne application code.\n'
