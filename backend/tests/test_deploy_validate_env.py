"""Keep the public direct-OTP affordance aligned with the production server gate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = PROJECT_ROOT / "deploy" / "validate_env.py"
PRODUCTION_EXAMPLE = PROJECT_ROOT / ".env.production.example"


def _valid_production_env() -> str:
    values = PRODUCTION_EXAMPLE.read_text()
    replacements = {
        "example.com": "gaonone.example",
        "REPLACE_WITH_STRONG_DATABASE_PASSWORD": "ci_strong_database_password_123456789",
        "REPLACE_WITH_AT_LEAST_32_RANDOM_BYTES": "ci_secret_key_0123456789abcdef0123456789abcdef",
        "REPLACE_WITH_FIREBASE_PROJECT_ID": "gaonone-ci",
        "REPLACE_WITH_BASE64_SERVICE_ACCOUNT_JSON": "e30=",
        "REPLACE_WITH_FIREBASE_WEB_API_KEY": "ci-firebase-api-key",
        "REPLACE_WITH_FIREBASE_WEB_AUTH_DOMAIN": "gaonone-ci.firebaseapp.com",
        "REPLACE_WITH_FIREBASE_WEB_APP_ID": "1:123456789:web:ci",
    }
    for source, replacement in replacements.items():
        values = values.replace(source, replacement)
    return values


def _validate(tmp_path: Path, values: str) -> subprocess.CompletedProcess[str]:
    (tmp_path / ".env.production").write_text(values)
    return subprocess.run(
        [sys.executable, str(VALIDATOR)],
        cwd=tmp_path,
        check=False,
        text=True,
        capture_output=True,
    )


def test_firebase_launch_hides_direct_otp_in_the_built_web_client(tmp_path: Path) -> None:
    result = _validate(tmp_path, _valid_production_env())

    assert result.returncode == 0, result.stderr


def test_production_rejects_a_visible_direct_otp_form_when_server_otp_is_disabled(
    tmp_path: Path,
) -> None:
    values = _valid_production_env().replace(
        "NEXT_PUBLIC_DIRECT_OTP_ENABLED=false",
        "NEXT_PUBLIC_DIRECT_OTP_ENABLED=true",
    )

    result = _validate(tmp_path, values)

    assert result.returncode == 1
    assert "NEXT_PUBLIC_DIRECT_OTP_ENABLED must match" in result.stderr


def test_production_rejects_nonliteral_direct_otp_flag_values(tmp_path: Path) -> None:
    values = _valid_production_env().replace(
        "NEXT_PUBLIC_DIRECT_OTP_ENABLED=false",
        "NEXT_PUBLIC_DIRECT_OTP_ENABLED=FALSE",
    )

    result = _validate(tmp_path, values)

    assert result.returncode == 1
    assert "NEXT_PUBLIC_DIRECT_OTP_ENABLED must be true or false" in result.stderr


def test_production_accepts_explicit_direct_otp_only_with_its_server_gate(
    tmp_path: Path,
) -> None:
    values = _valid_production_env()
    values = values.replace("AUTH_PROVIDER=firebase", "AUTH_PROVIDER=local_otp")
    values = values.replace("SMS_AUTH_ENABLED=false", "SMS_AUTH_ENABLED=true")
    values = values.replace("SMS_PROVIDER=none", "SMS_PROVIDER=msg91")
    values = values.replace("MSG91_AUTH_KEY=", "MSG91_AUTH_KEY=configured-direct-otp-key")
    values = values.replace(
        "MSG91_TEMPLATE_ID=",
        "MSG91_TEMPLATE_ID=configured-direct-otp-template",
    )
    values = values.replace(
        "NEXT_PUBLIC_DIRECT_OTP_ENABLED=false",
        "NEXT_PUBLIC_DIRECT_OTP_ENABLED=true",
    )

    result = _validate(tmp_path, values)

    assert result.returncode == 0, result.stderr
