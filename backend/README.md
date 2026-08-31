
## Reproducible builds

Every dependency set is locked so that a given commit always builds the same
tree — the exact-SHA principle only holds if `pip install` and `npm install`
cannot quietly resolve something new.

| Component | Lock file | Regenerate |
|---|---|---|
| Backend runtime | `backend/requirements.lock.txt` | `cd backend && pip-compile --generate-hashes --output-file requirements.lock.txt pyproject.toml` |
| Backend dev/test | `backend/requirements-dev.lock.txt` | `cd backend && pip-compile --generate-hashes --extra dev --output-file requirements-dev.lock.txt pyproject.toml` |
| Web | `web/package-lock.json` | `cd web && npm install` |
| Mobile | `mobile/pubspec.lock` | `cd mobile && flutter pub get` |

After changing a dependency in `backend/pyproject.toml`, regenerate both
backend locks. CI runs `scripts/check_dependency_lock.py`, which fails if a
declared dependency is missing from a lock.

Backend images and CI install with `--require-hashes`, the web image and Web CI
use `npm ci`, and Mobile CI uses `flutter pub get --enforce-lockfile` once
`mobile/pubspec.lock` is committed.
