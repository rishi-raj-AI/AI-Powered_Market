#!/usr/bin/env python3
"""Fail if a declared dependency is missing from the compiled lock.

Guards the common drift: someone adds a package to pyproject.toml and forgets
to recompile, so CI keeps installing the old tree and the build stops matching
the source. Deliberately does not compare exact versions — that would make CI
fail whenever an upstream release appears, which is noise rather than signal.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "backend"
PYPROJECT = ROOT / "pyproject.toml"
LOCKS = {
    "runtime": ROOT / "requirements.lock.txt",
    "dev": ROOT / "requirements-dev.lock.txt",
}

NAME = re.compile(r"^\s*([A-Za-z0-9._-]+)")


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def declared() -> tuple[set[str], set[str]]:
    data = tomllib.loads(PYPROJECT.read_text())
    project = data["project"]
    runtime = {normalize(NAME.match(dep).group(1)) for dep in project.get("dependencies", [])}
    dev = set()
    for extra in project.get("optional-dependencies", {}).values():
        dev |= {normalize(NAME.match(dep).group(1)) for dep in extra}
    return runtime, dev


def locked(path: Path) -> set[str]:
    if not path.exists():
        print(f"ERROR: missing lock file {path}", file=sys.stderr)
        raise SystemExit(1)
    names = set()
    for line in path.read_text().splitlines():
        if not line or line.startswith((" ", "#", "-")):
            continue
        match = NAME.match(line)
        if match:
            names.add(normalize(match.group(1)))
    return names


def main() -> int:
    runtime, dev = declared()
    runtime_locked = locked(LOCKS["runtime"])
    dev_locked = locked(LOCKS["dev"])

    problems = []
    for missing in sorted(runtime - runtime_locked):
        problems.append(f"{missing} is declared in pyproject.toml but absent from requirements.lock.txt")
    for missing in sorted((runtime | dev) - dev_locked):
        problems.append(f"{missing} is declared in pyproject.toml but absent from requirements-dev.lock.txt")

    if problems:
        print("Dependency lock is out of date:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print(
            "\nRegenerate with:\n"
            "  cd backend\n"
            "  pip-compile --generate-hashes --output-file requirements.lock.txt pyproject.toml\n"
            "  pip-compile --generate-hashes --extra dev --output-file requirements-dev.lock.txt pyproject.toml",
            file=sys.stderr,
        )
        return 1

    print(f"Dependency lock covers {len(runtime)} runtime and {len(dev)} dev dependencies.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
