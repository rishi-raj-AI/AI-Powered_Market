"""Write only allowlisted public client identifiers, never server/signing secrets."""

import argparse
import json
import os
from pathlib import Path
import sys

API_URL = "https://gaonone.in/api/v1"
MAPS_KEY = "GAONONE_GOOGLE_MAPS_ANDROID_API_KEY"
PUBLIC_KEYS = (
    "GAONONE_FIREBASE_ANDROID_API_KEY",
    "GAONONE_FIREBASE_ANDROID_APP_ID",
    "GAONONE_FIREBASE_ANDROID_MESSAGING_SENDER_ID",
    "GAONONE_FIREBASE_ANDROID_PROJECT_ID",
    "GAONONE_GOOGLE_SERVER_CLIENT_ID",
)


def configuration(environment):
    values = {key: environment.get(key, "").strip() for key in PUBLIC_KEYS}
    missing = [key for key, value in values.items() if not value]
    values.update(API_URL=API_URL, GAONONE_LEGACY_OTP_ENABLED="false", GAONONE_QA_BUILD="true")
    maps_key = environment.get(MAPS_KEY, "").strip()
    values[MAPS_KEY] = maps_key
    values["GAONONE_ANDROID_MAPS_ENABLED"] = "true" if maps_key else "false"
    report = {
        "api_url": API_URL,
        "legacy_otp_enabled": False,
        "firebase_public_configuration": "missing" if missing else "provided_unverified",
        "missing_public_variables": missing,
        "physical_device_tested": False,
        "production_release": False,
        "android_maps": "google_configured_unverified" if maps_key else "openstreetmap_fallback",
    }
    return values, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    values, report = configuration(os.environ)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    # Values are intentionally never logged, even though this allowlist is public.
    print(json.dumps(report, indent=2))
    if report["missing_public_variables"]:
        print("QA APK blocked: missing required GitHub Actions repository variables: "
              + ", ".join(report["missing_public_variables"]), file=sys.stderr)
        raise SystemExit(2)
    args.output.write_text(json.dumps(values, indent=2) + "\n")


if __name__ == "__main__":
    main()
