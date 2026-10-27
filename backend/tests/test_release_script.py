"""Regression coverage for the guarded release entry point.

The deployment script executes on the server, so these tests replace its
external commands with a temporary command log. That exercises the actual
normal and rollback branches without contacting Docker, GitHub, or a live
environment.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RELEASE_SCRIPT = PROJECT_ROOT / "deploy" / "release.sh"
DEPLOY_RUNNER_INSTALLER = PROJECT_ROOT / "deploy" / "install_deploy_runner.sh"
DEPLOY_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "production-deploy.yml"
DEPLOYMENT_RUNBOOK = PROJECT_ROOT / "docs" / "PRODUCTION_DEPLOYMENT.md"
TARGET_SHA = "a" * 40
PREVIOUS_SHA = "b" * 40


def _write_executable(path: Path, body: str) -> None:
    path.write_text(f"#!/usr/bin/env bash\nset -euo pipefail\n{body}")
    path.chmod(0o755)


def _make_fake_checkout(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "checkout"
    deploy_dir = root / "deploy"
    bin_dir = tmp_path / "bin"
    event_log = tmp_path / "events.log"
    deploy_dir.mkdir(parents=True)
    bin_dir.mkdir()
    event_log.touch()

    shutil.copy(RELEASE_SCRIPT, deploy_dir / "release.sh")
    (root / ".env.production").write_text("# fake deployment environment\n")
    (root / ".deployed-sha").write_text(f"{PREVIOUS_SHA}\n")

    _write_executable(
        deploy_dir / "backup.sh",
        'printf "backup\\n" >> "$EVENT_LOG"\n',
    )
    _write_executable(
        deploy_dir / "smoke.sh",
        """
printf "smoke\\n" >> "$EVENT_LOG"
if [[ "${SMOKE_FAIL_ONCE:-}" == "1" && ! -f .smoke-failed-once ]]; then
  touch .smoke-failed-once
  exit 1
fi
""",
    )
    _write_executable(
        deploy_dir / "monitor.sh",
        'printf "monitor\\n" >> "$EVENT_LOG"\n',
    )

    _write_executable(bin_dir / "flock", "exit 0\n")
    _write_executable(
        bin_dir / "git",
        """
printf "git %s\\n" "$*" >> "$EVENT_LOG"
case "${1:-}" in
  config|diff|fetch|checkout|reset|cat-file) exit 0 ;;
  rev-parse) printf '%s\\n' "$TARGET_SHA" ;;
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
        """
printf "make %s\\n" "$*" >> "$EVENT_LOG"
[[ "${1:-}" == "prod-check" ]]
""",
    )
    _write_executable(
        bin_dir / "docker",
        """
if [[ "${1:-}" == "info" ]]; then
  exit 0
fi
if [[ "${1:-}" != "compose" ]]; then
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
printf "compose %s\\n" "$*" >> "$EVENT_LOG"
if [[ "${1:-}" == "ps" && "${2:-}" == "--status" && "${PROXY_RUNNING:-1}" == "1" ]]; then
  printf 'proxy\\n'
fi
""",
    )
    return root, bin_dir, event_log


def _run_release(
    tmp_path: Path,
    *,
    smoke_fails_once: bool = False,
    proxy_running: bool = True,
    environment: str | None = "production",
) -> tuple[subprocess.CompletedProcess[str], Path]:
    root, bin_dir, event_log = _make_fake_checkout(tmp_path)
    env = os.environ.copy()
    env.update(
        {
            "EVENT_LOG": str(event_log),
            "TARGET_SHA": TARGET_SHA,
            "PATH": f"{bin_dir}{os.pathsep}{env['PATH']}",
            "GAONONE_ROOT": str(root),
            "GAONONE_EXPECTED_SHA": TARGET_SHA,
            "GAONONE_DEPLOY_SETTLE_SECONDS": "0",
            "GAONONE_DEPLOY_LOCK": str(tmp_path / "release.lock"),
        }
    )
    if environment is None:
        env.pop("GAONONE_ENVIRONMENT", None)
    else:
        env["GAONONE_ENVIRONMENT"] = environment
    if smoke_fails_once:
        env["SMOKE_FAIL_ONCE"] = "1"
    if not proxy_running:
        env["PROXY_RUNNING"] = "0"

    result = subprocess.run(
        ["bash", "deploy/release.sh"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return result, root


def _events(root: Path) -> list[str]:
    return (root.parent / "events.log").read_text().splitlines()


def test_release_requires_an_explicit_deployment_environment(tmp_path: Path) -> None:
    result, _ = _run_release(tmp_path, environment=None)

    assert result.returncode == 1
    assert "GAONONE_ENVIRONMENT must be explicitly set" in result.stderr


def test_release_requires_an_exact_expected_sha(tmp_path: Path) -> None:
    root, bin_dir, event_log = _make_fake_checkout(tmp_path)
    env = os.environ.copy()
    env.update(
        {
            "EVENT_LOG": str(event_log),
            "TARGET_SHA": TARGET_SHA,
            "PATH": f"{bin_dir}{os.pathsep}{env['PATH']}",
            "GAONONE_ROOT": str(root),
            "GAONONE_ENVIRONMENT": "production",
            "GAONONE_DEPLOY_SETTLE_SECONDS": "0",
            "GAONONE_DEPLOY_LOCK": str(tmp_path / "release.lock"),
        }
    )

    result = subprocess.run(
        ["bash", "deploy/release.sh"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "GAONONE_EXPECTED_SHA must be set" in result.stderr


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


def test_privileged_release_preserves_only_its_nonsecret_selectors() -> None:
    installer = DEPLOY_RUNNER_INSTALLER.read_text()
    workflow = DEPLOY_WORKFLOW.read_text()
    runbook = DEPLOYMENT_RUNBOOK.read_text()

    assert 'env_keep += "GAONONE_EXPECTED_SHA GAONONE_ENVIRONMENT"' in installer
    assert "NOPASSWD: %s/deploy/release.sh" in installer
    assert "sudo /home/ubuntu/gaonone/deploy/release.sh" in workflow
    assert "sudo /home/ubuntu/gaonone/deploy/release.sh" in runbook
    assert "sudo bash /home/ubuntu/gaonone/deploy/install_deploy_runner.sh" in runbook
    assert "sudo /usr/bin/env \\\n" not in workflow
    assert "sudo /usr/bin/env \\\n" not in runbook
    assert "source .env.production" not in runbook
