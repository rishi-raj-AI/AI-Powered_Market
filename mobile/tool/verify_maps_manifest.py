"""Check the native Maps key in the APK without emitting configuration values."""
import argparse
import json
from pathlib import Path
import re
import subprocess


def matches(manifest, expected):
    blocks = re.split(r"\n\s*E: ", manifest)
    maps = [block for block in blocks if block.startswith("meta-data")
            and '"com.google.android.geo.API_KEY"' in block]
    if len(maps) != 1:
        return False
    value = re.search(r'android:value[^=]*="([^"]*)"', maps[0])
    return value is not None and value.group(1) == expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aapt", required=True)
    parser.add_argument("--apk", required=True)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    result = subprocess.run([args.aapt, "dump", "xmltree", args.apk, "AndroidManifest.xml"],
                            capture_output=True, text=True, check=False)
    if result.returncode or not matches(result.stdout, config["GAONONE_GOOGLE_MAPS_ANDROID_API_KEY"]):
        raise SystemExit("APK Maps metadata does not match the intended public configuration")
    print("APK native Maps metadata matches build configuration; values withheld.")


if __name__ == "__main__":
    main()
