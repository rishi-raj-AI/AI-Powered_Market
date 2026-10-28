"""Regression coverage for the guarded release entry point.

The deployment script executes on the server, so these tests replace its
external commands with a temporary command log. That exercises the actual
normal and rollback branches without contacting Docker, GitHub, or a live
environment.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RELEASE_SCRIPT = PROJECT_ROOT / "deploy" / "release.sh"
BACKUP_SCRIPT = PROJECT_ROOT / "deploy" / "backup.sh"
DEPLOY_RUNNER_INSTALLER = PROJECT_ROOT / "deploy" / "install_deploy_runner.sh"
DEPLOY_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "production-deploy.yml"
DEPLOYMENT_RUNBOOK = PROJECT_ROOT / "docs" / "PRODUCTION_DEPLOYMENT.md"
SMOKE_SCRIPT = PROJECT_ROOT / "deploy" / "smoke.sh"
TARGET_SHA = "a" * 40
PREVIOUS_SHA = "b" * 40
SUDO_RELEASE_PATH = "/usr/local/sbin/gaonone-release"
PROTECTED_RELEASE_ROOT = "/srv/gaonone"
SAFE_COMMAND_PATH = "/usr/sbin:/usr/bin:/sbin:/bin"


def _write_executable(
    path: Path,
    body: str,
    *,
    interpreter: str = "/usr/bin/env bash",
) -> None:
    path.write_text(f"#!{interpreter}\nset -euo pipefail\n{body}")
    path.chmod(0o755)


def _make_fake_checkout(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "checkout"
    deploy_dir = root / "deploy"
    bin_dir = tmp_path / "bin"
    event_log = tmp_path / "events.log"
    find_count_file = tmp_path / "find-count"
    deploy_dir.mkdir(parents=True)
    bin_dir.mkdir()
    event_log.touch()

    # The production script deliberately sets a fixed system command path. Use
    # an equally fixed fixture command path so this test can exercise the real
    # release flow without placing fake Git or Docker binaries on the host.
    release_source = RELEASE_SCRIPT.read_text()
    production_path_assignment = f'PATH="{SAFE_COMMAND_PATH}"\nexport PATH'
    assert production_path_assignment in release_source
    release_source = release_source.replace(
        production_path_assignment,
        f'PATH="{bin_dir}:{SAFE_COMMAND_PATH}"\nexport PATH',
        1,
    )
    assert f'ROOT_DIR="{PROTECTED_RELEASE_ROOT}"' in release_source
    release_source = release_source.replace(
        f'ROOT_DIR="{PROTECTED_RELEASE_ROOT}"',
        f'ROOT_DIR="{root}"',
        1,
    )
    assert "assert_root_owned_path /srv" in release_source
    release_source = release_source.replace(
        "assert_root_owned_path /srv",
        f'assert_root_owned_path "{root.parent}"',
        1,
    )
    assert 'LOCK_FILE="$ROOT_DIR/.gaonone-${ENVIRONMENT}-deploy.lock"' in release_source
    release_source = release_source.replace(
        "sleep 15",
        "sleep 0",
        1,
    )
    (deploy_dir / "release.sh").write_text(release_source)
    (deploy_dir / "release.sh").chmod(0o755)
    (root / ".git").mkdir()
    (root / ".env.production").write_text("# fake deployment environment\n")
    (root / ".deployed-sha").write_text(f"{PREVIOUS_SHA}\n")

    _write_executable(
        deploy_dir / "backup.sh",
        f"""
secret_status=absent
if [[ -n "${{GAONONE_UNRELATED_SECRET+x}}" ]]; then
  secret_status=present
fi
printf 'sudo-probe expected=%s environment=%s root=%s branch=%s secret=%s\\n' \\
  "${{GAONONE_EXPECTED_SHA:-missing}}" \\
  "${{GAONONE_ENVIRONMENT:-missing}}" \\
  "${{GAONONE_ROOT:-missing}}" \\
  "${{GAONONE_DEPLOY_BRANCH:-main}}" \\
  "$secret_status" >> {shlex.quote(str(event_log))}
printf "backup\\n" >> {shlex.quote(str(event_log))}
""",
    )
    _write_executable(
        deploy_dir / "smoke.sh",
        f"""
printf "smoke\\n" >> {shlex.quote(str(event_log))}
if [[ "${{SMOKE_FAIL_ONCE:-}}" == "1" && ! -f .smoke-failed-once ]]; then
  touch .smoke-failed-once
  exit 1
fi
""",
    )
    _write_executable(
        deploy_dir / "monitor.sh",
        f'printf "monitor\\n" >> {shlex.quote(str(event_log))}\n',
    )

    _write_executable(bin_dir / "flock", "exit 0\n")
    _write_executable(
        bin_dir / "stat",
        """
if [[ "${1:-}" != "-c" ]]; then
  echo "Unexpected fake stat command: $*" >&2
  exit 1
fi
case "${2:-}" in
  %U) printf 'root\\n' ;;
  %a) printf '755\\n' ;;
  *)
    echo "Unexpected fake stat format: ${2:-}" >&2
    exit 1
    ;;
esac
""",
    )
    _write_executable(
        bin_dir / "find",
        f"""
find_count=0
if [[ -f {shlex.quote(str(find_count_file))} ]]; then
  find_count="$(< {shlex.quote(str(find_count_file))})"
fi
find_count=$((find_count + 1))
printf '%s\\n' "$find_count" > {shlex.quote(str(find_count_file))}
if [[ "${{INSECURE_CHECKOUT:-0}}" == "1" || ( "${{INSECURE_CHECKOUT_AFTER_RESET:-0}}" == "1" && "$find_count" -gt 1 ) || ( "${{INSECURE_ROLLBACK_CHECKOUT:-0}}" == "1" && "$find_count" -gt 2 ) ]]; then
  printf '%s/deploy/release.sh\\n' "$1"
fi
""",
    )
    _write_executable(
        bin_dir / "git",
        f"""
printf "git %s\\n" "$*" >> {shlex.quote(str(event_log))}
case "${{1:-}}" in
  config|diff|fetch|checkout|reset|cat-file) exit 0 ;;
  rev-parse) printf '%s\\n' "{TARGET_SHA}" ;;
  log) printf 'target test commit\\n' ;;
  *)
    echo "Unexpected fake git command: $*" >&2
    exit 1
    ;;
esac
""",
    )
    _write_executable(
        bin_dir / "make",
        f"""
printf "make %s\\n" "$*" >> {shlex.quote(str(event_log))}
[[ "${{1:-}}" == "prod-check" ]]
""",
    )
    _write_executable(
        bin_dir / "docker",
        f"""
if [[ "${{1:-}}" == "info" ]]; then
  exit 0
fi
if [[ "${{1:-}}" != "compose" ]]; then
  echo "Unexpected fake docker command: $*" >&2
  exit 1
fi
shift
while (( $# )); do
  case "$1" in
    --env-file|-f|--profile) shift 2 ;;
    *) break ;;
  esac
done
printf "compose %s\\n" "$*" >> {shlex.quote(str(event_log))}
if [[ "${{1:-}}" == "ps" && "${{2:-}}" == "--status" && "${{PROXY_RUNNING:-1}}" == "1" ]]; then
  printf 'proxy\\n'
fi
""",
    )
    return root, bin_dir, event_log


def _release_environment(
    root: Path,
    bin_dir: Path,
    *,
    expected_sha: str | None = TARGET_SHA,
    environment: str | None = "production",
) -> dict[str, str]:
    env = os.environ.copy()
    for name in (
        "GAONONE_ROOT",
        "GAONONE_DEPLOY_BRANCH",
        "GAONONE_UNRELATED_SECRET",
    ):
        env.pop(name, None)
    env.update(
        {
            "PATH": f"{bin_dir}{os.pathsep}{env['PATH']}",
        }
    )
    if expected_sha is None:
        env.pop("GAONONE_EXPECTED_SHA", None)
    else:
        env["GAONONE_EXPECTED_SHA"] = expected_sha
    if environment is None:
        env.pop("GAONONE_ENVIRONMENT", None)
    else:
        env["GAONONE_ENVIRONMENT"] = environment
    return env


def _run_release(
    tmp_path: Path,
    *,
    expected_sha: str | None = TARGET_SHA,
    smoke_fails_once: bool = False,
    proxy_running: bool = True,
    insecure_checkout: bool = False,
    insecure_after_reset: bool = False,
    insecure_rollback_checkout: bool = False,
    environment: str | None = "production",
) -> tuple[subprocess.CompletedProcess[str], Path]:
    root, bin_dir, _ = _make_fake_checkout(tmp_path)
    env = _release_environment(
        root,
        bin_dir,
        expected_sha=expected_sha,
        environment=environment,
    )
    if smoke_fails_once:
        env["SMOKE_FAIL_ONCE"] = "1"
    if not proxy_running:
        env["PROXY_RUNNING"] = "0"
    if insecure_checkout:
        env["INSECURE_CHECKOUT"] = "1"
    if insecure_after_reset:
        env["INSECURE_CHECKOUT_AFTER_RESET"] = "1"
    if insecure_rollback_checkout:
        env["INSECURE_ROLLBACK_CHECKOUT"] = "1"

    result = subprocess.run(
        [str(root / "deploy" / "release.sh")],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return result, root


def _events(root: Path) -> list[str]:
    return (root.parent / "events.log").read_text().splitlines()


def _run_backup_without_running_api(
    tmp_path: Path,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    """Exercise the actual backup script with no long-running API container.

    The fake Compose implementation rejects ``exec api`` outright. A successful
    run therefore proves that the media archive uses the one-shot, no-dependency
    API-image path rather than relying on an already-running application.
    """

    root = tmp_path / "backup-checkout"
    bin_dir = tmp_path / "backup-bin"
    event_log = tmp_path / "backup-events.log"
    root.mkdir()
    bin_dir.mkdir()
    event_log.touch()
    (root / ".env.production").write_text("# fake production environment\n")

    _write_executable(
        bin_dir / "docker",
        f"""
if [[ "${{1:-}}" == "info" ]]; then
  exit 0
fi
if [[ "${{1:-}}" != "compose" ]]; then
  echo "Unexpected fake docker command: $*" >&2
  exit 1
fi
shift
while (( $# )); do
  case "$1" in
    --env-file|-f) shift 2 ;;
    *) break ;;
  esac
done
case "${{1:-}}" in
  exec)
    shift
    [[ "${{1:-}}" == "-T" ]] && shift
    service="${{1:-}}"
    shift
    case "$service:$*" in
      "db:printenv POSTGRES_USER")
        printf 'db-user\n' >> {shlex.quote(str(event_log))}
        printf 'gaonone\n'
        ;;
      "db:printenv POSTGRES_DB")
        printf 'db-name\n' >> {shlex.quote(str(event_log))}
        printf 'gaonone\n'
        ;;
      "db:pg_dump -U gaonone -d gaonone -Fc")
        printf 'db-dump\n' >> {shlex.quote(str(event_log))}
        printf 'database-backup\n'
        ;;
      "api:"*)
        echo "backup must not exec into a running API service" >&2
        exit 88
        ;;
      *)
        echo "Unexpected fake compose exec: $service $*" >&2
        exit 1
        ;;
    esac
    ;;
  run)
    shift
    if [[ "${{1:-}}" == "--rm" && "${{2:-}}" == "--no-deps" && "${{3:-}}" == "api" && "${{4:-}}" == "sh" && "${{5:-}}" == "-c" && "${{6:-}}" == "cd /app/data && tar -czf - uploads" ]]; then
      printf 'media-run\n' >> {shlex.quote(str(event_log))}
      printf 'media-backup\n'
      exit 0
    fi
    echo "Unexpected fake compose run: $*" >&2
    exit 1
    ;;
  *)
    echo "Unexpected fake compose command: $*" >&2
    exit 1
    ;;
esac
""",
    )
    _write_executable(
        bin_dir / "sha256sum",
        """
for backup_file in "$@"; do
  printf 'fixture-sha  %s\\n' "$backup_file"
done
""",
    )

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    result = subprocess.run(
        ["bash", str(BACKUP_SCRIPT)],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return result, root, event_log


def test_backup_archives_media_before_migration_without_a_running_api(
    tmp_path: Path,
) -> None:
    result, root, event_log = _run_backup_without_running_api(tmp_path)

    assert result.returncode == 0, result.stderr
    assert event_log.read_text().splitlines() == [
        "db-user",
        "db-name",
        "db-dump",
        "media-run",
    ]
    backups = root / "backups"
    assert len(list(backups.glob("gaonone-db-*.dump"))) == 1
    assert len(list(backups.glob("gaonone-media-*.tar.gz"))) == 1
    assert len(list(backups.glob("gaonone-*.sha256"))) == 1
    backup_source = BACKUP_SCRIPT.read_text()
    assert "compose run --rm --no-deps api" in backup_source
    assert "compose exec -T api" not in backup_source


def _write_scoped_sudo_shim(bin_dir: Path, root: Path) -> None:
    """Emulate the release command's sudo env_reset/env_keep boundary.

    The fixture's copied script has a fixed temporary checkout path. After
    clearing the caller's environment, the only caller values deliberately
    carried through are the two values allowed by the rendered sudoers policy.
    """

    release_script = root / "deploy" / "release.sh"
    _write_executable(
        bin_dir / "sudo",
        f"""
if [[ "$#" -ne 1 || "$1" != "{SUDO_RELEASE_PATH}" ]]; then
  echo "scoped sudo only permits the direct no-argument release command" >&2
  exit 64
fi
exec /usr/bin/env -i \\
  PATH="{bin_dir}:{SAFE_COMMAND_PATH}" \\
  GAONONE_EXPECTED_SHA="${{GAONONE_EXPECTED_SHA:-}}" \\
  GAONONE_ENVIRONMENT="${{GAONONE_ENVIRONMENT:-}}" \\
  {shlex.quote(str(release_script))}
""",
        interpreter="/bin/bash",
    )


def _rendered_sudoers_policy() -> str:
    return (
        f"Defaults!{SUDO_RELEASE_PATH} env_reset\n"
        f'Defaults!{SUDO_RELEASE_PATH} env_keep = "GAONONE_EXPECTED_SHA GAONONE_ENVIRONMENT"\n'
        f'ubuntu ALL=(root) NOPASSWD: NOSETENV: {SUDO_RELEASE_PATH} ""\n'
    )


def test_release_requires_an_explicit_deployment_environment(tmp_path: Path) -> None:
    result, _ = _run_release(tmp_path, environment=None)

    assert result.returncode == 1
    assert "GAONONE_ENVIRONMENT must be explicitly set" in result.stderr


def test_release_requires_an_exact_expected_sha(tmp_path: Path) -> None:
    root, bin_dir, _ = _make_fake_checkout(tmp_path)
    env = _release_environment(root, bin_dir, expected_sha=None)

    result = subprocess.run(
        [str(root / "deploy" / "release.sh")],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "GAONONE_EXPECTED_SHA must be set" in result.stderr


def test_release_rejects_an_invalid_deployment_environment_before_side_effects(
    tmp_path: Path,
) -> None:
    result, root = _run_release(tmp_path, environment="preview")

    assert result.returncode == 1
    assert "GAONONE_ENVIRONMENT must be staging or production" in result.stderr
    assert _events(root) == []


def test_release_refuses_an_insecure_checkout_before_side_effects(tmp_path: Path) -> None:
    result, root = _run_release(tmp_path, insecure_checkout=True)

    assert result.returncode == 1
    assert "Protected release checkout contains a non-root-owned or writable path" in result.stderr
    assert _events(root) == []


def test_release_rechecks_the_synced_checkout_before_running_target_helpers(
    tmp_path: Path,
) -> None:
    result, root = _run_release(tmp_path, insecure_after_reset=True)

    assert result.returncode == 1
    assert "Synced checkout failed the protected release integrity check" in result.stderr
    events = _events(root)
    assert "backup" in events
    assert "make prod-check" not in events
    assert "compose build api web worker migrate" not in events
    assert "compose run --rm migrate" not in events
    assert "compose up -d --no-build --force-recreate api web worker proxy" not in events
    assert "smoke" not in events
    assert "monitor" not in events


def test_rollback_rechecks_the_restored_checkout_before_starting_services(
    tmp_path: Path,
) -> None:
    result, root = _run_release(
        tmp_path,
        smoke_fails_once=True,
        insecure_rollback_checkout=True,
    )

    assert result.returncode == 1
    assert "Rollback checkout failed the protected release integrity check" in result.stderr
    events = _events(root)
    assert "compose build api web worker migrate" in events
    assert "compose build api web worker" not in events
    assert events.count("compose up -d --no-build --force-recreate api web worker proxy") == 1
    assert events.count("smoke") == 1
    assert "monitor" not in events


def test_mismatched_expected_sha_aborts_before_migration_or_runtime_start(
    tmp_path: Path,
) -> None:
    result, root = _run_release(tmp_path, expected_sha="c" * 40)

    assert result.returncode == 1
    assert "refusing stale deployment" in result.stderr
    events = _events(root)
    assert "backup" in events
    assert "make prod-check" not in events
    assert "compose build api web worker migrate" not in events
    assert "compose run --rm migrate" not in events
    assert "compose up -d --no-build --force-recreate api web worker proxy" not in events
    assert "smoke" not in events
    assert "monitor" not in events


def test_normal_release_starts_proxy_before_https_smoke_and_preserves_backup_order(
    tmp_path: Path,
) -> None:
    result, root = _run_release(tmp_path)

    assert result.returncode == 0, result.stderr
    events = _events(root)
    up = "compose up -d --no-build --force-recreate api web worker proxy"
    proxy_check = "compose ps --status running --services"
    migrate = "compose run --rm migrate"
    assert events.count(up) == 1
    assert events.index("backup") < events.index(migrate)
    assert events.index(proxy_check) < events.index("smoke")
    assert (root / ".deployed-sha").read_text() == f"{TARGET_SHA}\n"


def test_rollback_starts_proxy_before_its_https_smoke_after_failed_release(tmp_path: Path) -> None:
    result, root = _run_release(tmp_path, smoke_fails_once=True)

    assert result.returncode == 1
    assert "ROLLBACK SUCCEEDED" in result.stderr
    events = _events(root)
    up = "compose up -d --no-build --force-recreate api web worker proxy"
    proxy_check = "compose ps --status running --services"
    assert events.count(up) == 2
    assert events.count(proxy_check) == 2
    smoke_events = [index for index, event in enumerate(events) if event == "smoke"]
    proxy_checks = [index for index, event in enumerate(events) if event == proxy_check]
    assert len(smoke_events) == len(proxy_checks) == 2
    assert all(check < smoke for check, smoke in zip(proxy_checks, smoke_events, strict=True))
    assert (root / ".deployed-sha").read_text() == f"{PREVIOUS_SHA}\n"


def test_proxy_start_failure_rolls_back_without_running_https_smoke(tmp_path: Path) -> None:
    result, root = _run_release(tmp_path, proxy_running=False)

    assert result.returncode == 1
    assert "Caddy proxy is not running" in result.stderr
    events = _events(root)
    up = "compose up -d --no-build --force-recreate api web worker proxy"
    assert events.count(up) == 2
    assert "smoke" not in events


def test_manual_prod_deploy_also_starts_the_public_proxy() -> None:
    makefile = (PROJECT_ROOT / "Makefile").read_text()

    assert "up -d --no-build --force-recreate api web worker proxy" in makefile


def test_privileged_release_uses_a_fixed_command_path(tmp_path: Path) -> None:
    root, bin_dir, event_log = _make_fake_checkout(tmp_path)
    attacker_bin = tmp_path / "attacker-bin"
    attacker_bin.mkdir()
    _write_executable(
        attacker_bin / "git",
        f'printf "attacker-git\\n" >> {shlex.quote(str(event_log))}\nexit 97\n',
        interpreter="/bin/bash",
    )
    env = _release_environment(root, bin_dir)
    env["PATH"] = f"{attacker_bin}{os.pathsep}{env['PATH']}"

    result = subprocess.run(
        [str(root / "deploy" / "release.sh")],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "attacker-git" not in _events(root)


def test_privileged_release_policy_and_documentation_are_narrow() -> None:
    installer = DEPLOY_RUNNER_INSTALLER.read_text()
    workflow = DEPLOY_WORKFLOW.read_text()
    runbook = DEPLOYMENT_RUNBOOK.read_text()

    assert RELEASE_SCRIPT.read_text().splitlines()[0] == "#!/bin/bash"
    assert f'PATH="{SAFE_COMMAND_PATH}"' in RELEASE_SCRIPT.read_text()
    assert installer.splitlines()[0] == "#!/bin/bash"
    assert f'ROOT_DIR="{PROTECTED_RELEASE_ROOT}"' in RELEASE_SCRIPT.read_text()
    assert 'BRANCH="main"' in RELEASE_SCRIPT.read_text()
    assert "GAONONE_ROOT" not in RELEASE_SCRIPT.read_text()
    assert "GAONONE_DEPLOY_BRANCH" not in RELEASE_SCRIPT.read_text()
    assert "GAONONE_DEPLOY_LOCK" not in RELEASE_SCRIPT.read_text()
    assert "GAONONE_DEPLOY_SETTLE_SECONDS" not in RELEASE_SCRIPT.read_text()
    assert 'LOCK_FILE="$ROOT_DIR/.gaonone-${ENVIRONMENT}-deploy.lock"' in RELEASE_SCRIPT.read_text()
    assert "-type l" in RELEASE_SCRIPT.read_text()
    assert f'RELEASE_ENTRYPOINT="{SUDO_RELEASE_PATH}"' in installer
    assert 'RUNNER_USER="ubuntu"' in installer
    assert "GAONONE_RUNNER_USER" not in installer
    assert "assert_root_owned_path /usr/local/sbin" in installer
    assert "-type l" in installer
    assert "Defaults!%s env_reset" in installer
    assert 'Defaults!%s env_keep = "GAONONE_EXPECTED_SHA GAONONE_ENVIRONMENT"' in installer
    assert '%s ALL=(root) NOPASSWD: NOSETENV: %s ""' in installer
    assert "NOPASSWD: ALL" not in installer
    assert f"sudo {SUDO_RELEASE_PATH}" in workflow
    assert f"sudo {SUDO_RELEASE_PATH}" in runbook
    assert "sudo /bin/bash /srv/gaonone/deploy/install_deploy_runner.sh" in runbook
    assert "runner-writable workspace" in runbook
    assert "/home/ubuntu/gaonone/deploy/release.sh" not in workflow
    assert "git reset --hard" not in workflow
    assert "GAONONE_ENVIRONMENT: staging" in workflow
    assert "self-hosted runner service must therefore run as `ubuntu`" in runbook
    assert "sudo /usr/bin/env \\\n" not in workflow
    assert "sudo /usr/bin/env \\\n" not in runbook
    assert "source .env.production" not in runbook
    assert "tee /tmp/gaonone-" not in SMOKE_SCRIPT.read_text()


def test_rendered_sudo_policy_is_parseable(tmp_path: Path) -> None:
    visudo = shutil.which("visudo")
    if visudo is None:
        pytest.skip("visudo is required to validate the sudoers fixture")
    policy_file = tmp_path / "gaonone-deploy"
    policy_file.write_text(_rendered_sudoers_policy())

    result = subprocess.run(
        [visudo, "-cf", str(policy_file)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_documented_manual_sudo_form_forwards_only_the_required_selectors(
    tmp_path: Path,
) -> None:
    line_continuation = chr(92)
    documented_invocation = "\n".join(
        (
            f"GAONONE_EXPECTED_SHA=<full-approved-main-sha> {line_continuation}",
            f"GAONONE_ENVIRONMENT=production {line_continuation}",
            f"sudo {SUDO_RELEASE_PATH}",
        )
    )
    assert documented_invocation in DEPLOYMENT_RUNBOOK.read_text()

    root, bin_dir, _ = _make_fake_checkout(tmp_path)
    _write_scoped_sudo_shim(bin_dir, root)
    env = _release_environment(root, bin_dir)
    caller_controlled_root = tmp_path / "caller-controlled-checkout"
    command = (
        'GAONONE_EXPECTED_SHA="$1" '
        'GAONONE_ENVIRONMENT=production '
        'GAONONE_ROOT="$2" '
        'GAONONE_DEPLOY_BRANCH=untrusted '
        'GAONONE_UNRELATED_SECRET=not-for-root '
        f"sudo {SUDO_RELEASE_PATH}"
    )

    result = subprocess.run(
        ["/bin/bash", "-c", command, "manual-release", TARGET_SHA, str(caller_controlled_root)],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    events = _events(root)
    assert (
        f"sudo-probe expected={TARGET_SHA} environment=production root=missing "
        "branch=main secret=absent"
    ) in events
    assert "git fetch --prune origin main" in events


def test_workflow_sudo_form_forwards_only_the_required_selectors(tmp_path: Path) -> None:
    workflow = DEPLOY_WORKFLOW.read_text()
    assert "GAONONE_EXPECTED_SHA: ${{ needs.verify-green-main.outputs.sha }}" in workflow
    assert "GAONONE_ENVIRONMENT: staging" in workflow
    assert f"sudo {SUDO_RELEASE_PATH}" in workflow

    root, bin_dir, _ = _make_fake_checkout(tmp_path)
    _write_scoped_sudo_shim(bin_dir, root)
    env = _release_environment(root, bin_dir, environment="staging")
    env.update(
        {
            "GAONONE_ROOT": str(tmp_path / "caller-controlled-checkout"),
            "GAONONE_DEPLOY_BRANCH": "untrusted",
            "GAONONE_UNRELATED_SECRET": "not-for-root",
        }
    )

    result = subprocess.run(
        ["sudo", SUDO_RELEASE_PATH],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    events = _events(root)
    assert (
        f"sudo-probe expected={TARGET_SHA} environment=staging root=missing "
        "branch=main secret=absent"
    ) in events
    assert "git fetch --prune origin main" in events


def test_scoped_sudo_entry_rejects_extra_arguments(tmp_path: Path) -> None:
    root, bin_dir, _ = _make_fake_checkout(tmp_path)
    _write_scoped_sudo_shim(bin_dir, root)
    env = _release_environment(root, bin_dir)

    result = subprocess.run(
        ["sudo", SUDO_RELEASE_PATH, "unexpected-argument"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 64
    assert _events(root) == []


def test_scoped_sudo_entry_rejects_environment_preservation_flag(tmp_path: Path) -> None:
    root, bin_dir, _ = _make_fake_checkout(tmp_path)
    _write_scoped_sudo_shim(bin_dir, root)
    env = _release_environment(root, bin_dir)

    result = subprocess.run(
        ["sudo", "-E", SUDO_RELEASE_PATH],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 64
    assert _events(root) == []
