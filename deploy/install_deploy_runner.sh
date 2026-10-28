#!/bin/bash
set -euo pipefail

PATH="/usr/sbin:/usr/bin:/sbin:/bin"
export PATH

ROOT_DIR="/srv/gaonone"
RUNNER_USER="ubuntu"
RELEASE_ENTRYPOINT="/usr/local/sbin/gaonone-release"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with sudo: sudo /bin/bash deploy/install_deploy_runner.sh" >&2
  exit 1
fi
if [[ ! -d "$ROOT_DIR/.git" || ! -f "$ROOT_DIR/.env.production" ]]; then
  echo "Protected GaonOne checkout or .env.production missing at $ROOT_DIR" >&2
  exit 1
fi

assert_root_owned_path() {
  local path="$1" owner mode
  if [[ -L "$path" || ! -e "$path" ]]; then
    echo "Protected release path is missing or symlinked: $path" >&2
    return 1
  fi
  owner="$(stat -c '%U' "$path")"
  mode="$(stat -c '%a' "$path")"
  if [[ "$owner" != "root" || $((8#$mode & 022)) -ne 0 ]]; then
    echo "Protected release path must be root-owned and not group/world writable: $path" >&2
    return 1
  fi
}

assert_root_owned_path /srv
assert_root_owned_path "$ROOT_DIR"
insecure_path="$(find "$ROOT_DIR" -xdev \( -type l -o ! -user root -o -perm /022 \) -print -quit)"
if [[ -n "$insecure_path" ]]; then
  echo "Protected release checkout contains a non-root-owned or writable path: $insecure_path" >&2
  exit 1
fi

# Install the reviewed release script outside the runner-writable workspace,
# then permit the dedicated GitHub Actions runner job to invoke only that
# root-owned entry point. Force the standard minimal sudo environment and
# preserve only the non-secret release selectors required by this command.
# Never grant a root shell, Docker, arbitrary environment, or a
# caller-controlled checkout path.
assert_root_owned_path /usr
assert_root_owned_path /usr/local
install -d -o root -g root -m 0755 /usr/local/sbin
assert_root_owned_path /usr/local/sbin
install -o root -g root -m 0755 "$ROOT_DIR/deploy/release.sh" "$RELEASE_ENTRYPOINT"
assert_root_owned_path "$RELEASE_ENTRYPOINT"
SUDOERS_FILE="/etc/sudoers.d/gaonone-deploy"
printf 'Defaults!%s env_reset\n' "$RELEASE_ENTRYPOINT" > "$SUDOERS_FILE"
printf 'Defaults!%s env_keep = "GAONONE_EXPECTED_SHA GAONONE_ENVIRONMENT"\n' "$RELEASE_ENTRYPOINT" >> "$SUDOERS_FILE"
printf '%s ALL=(root) NOPASSWD: NOSETENV: %s ""\n' "$RUNNER_USER" "$RELEASE_ENTRYPOINT" >> "$SUDOERS_FILE"
chmod 0440 "$SUDOERS_FILE"
visudo -cf "$SUDOERS_FILE"

echo "GaonOne deploy permission installed for $RUNNER_USER."
echo "Protected release entry point installed at $RELEASE_ENTRYPOINT."
echo "Next: register a GitHub self-hosted runner with labels: gaonone-production"
echo "Then install/start it with the runner's svc.sh service commands."
