#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse

ENV_FILE = Path('.env.production')


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def fail(message: str, errors: list[str]) -> None:
    errors.append(message)


def main() -> int:
    if not ENV_FILE.exists():
        print('ERROR: .env.production is missing. Copy .env.production.example first.', file=sys.stderr)
        return 1

    env = load_env(ENV_FILE)
    errors: list[str] = []

    if env.get('APP_ENV') != 'production':
        fail('APP_ENV must be production', errors)
    if env.get('APP_DEBUG', '').lower() not in {'false', '0', 'no'}:
        fail('APP_DEBUG must be false', errors)

    domain = env.get('DOMAIN', '').strip()
    if not domain or domain == 'example.com' or '://' in domain:
        fail('DOMAIN must be a real hostname without http:// or https://', errors)

    public_url = env.get('PUBLIC_BASE_URL', '')
    if domain and public_url != f'https://{domain}':
        fail('PUBLIC_BASE_URL must exactly match https://DOMAIN', errors)

    origins = {x.strip() for x in env.get('CORS_ORIGINS', '').split(',') if x.strip()}
    if domain and f'https://{domain}' not in origins:
        fail('CORS_ORIGINS must include the production HTTPS domain', errors)

    hosts = {x.strip() for x in env.get('TRUSTED_HOSTS', '').split(',') if x.strip()}
    if domain and domain not in hosts:
        fail('TRUSTED_HOSTS must include DOMAIN', errors)

    secret = env.get('SECRET_KEY', '')
    if len(secret.encode()) < 32 or secret.startswith('REPLACE_') or secret == 'change-this-in-production':
        fail('SECRET_KEY must be a non-placeholder value of at least 32 bytes', errors)

    db_password = env.get('POSTGRES_PASSWORD', '')
    if len(db_password) < 16 or db_password.startswith('REPLACE_'):
        fail('POSTGRES_PASSWORD must be a non-placeholder value of at least 16 characters', errors)

    database_url = env.get('DATABASE_URL', '')
    try:
        parsed = urlparse(database_url.replace('postgresql+psycopg://', 'postgresql://', 1))
        if parsed.password != db_password:
            fail('DATABASE_URL password must match POSTGRES_PASSWORD', errors)
        if parsed.hostname != 'db':
            fail('Pilot production DATABASE_URL host must be db', errors)
    except Exception:
        fail('DATABASE_URL is invalid', errors)

    if env.get('DEV_OTP'):
        fail('DEV_OTP must be empty in production', errors)

    sms_provider = env.get('SMS_PROVIDER', 'none').strip().lower()
    if sms_provider not in {'none', 'msg91'}:
        fail('SMS_PROVIDER must be none or msg91', errors)
    if sms_provider == 'msg91':
        if not env.get('MSG91_AUTH_KEY', '').strip():
            fail('MSG91_AUTH_KEY is required when SMS_PROVIDER=msg91', errors)
        if not env.get('MSG91_TEMPLATE_ID', '').strip():
            fail('MSG91_TEMPLATE_ID is required when SMS_PROVIDER=msg91', errors)

    email = env.get('ACME_EMAIL', '')
    if '@' not in email or email.endswith('@example.com'):
        fail('ACME_EMAIL must be a real operational email address', errors)

    if errors:
        print('Production environment validation FAILED:', file=sys.stderr)
        for item in errors:
            print(f'  - {item}', file=sys.stderr)
        return 1

    print('Production environment validation passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
