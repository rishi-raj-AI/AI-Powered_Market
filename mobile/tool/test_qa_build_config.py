import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest

from qa_build_config import API_URL, MAPS_KEY, PUBLIC_KEYS, configuration
from verify_maps_manifest import matches


class QaBuildConfigurationTests(unittest.TestCase):
    def test_native_manifest_key_must_match_exactly_once(self):
        manifest = '\n  E: meta-data\n    A: android:name(0x01010003)="com.google.android.geo.API_KEY"\n    A: android:value(0x01010024)="public-fixture"\n  E: activity\n'
        self.assertTrue(matches(manifest, "public-fixture"))
        self.assertFalse(matches(manifest, "wrong-fixture"))
        self.assertFalse(matches(manifest + manifest, "public-fixture"))
        self.assertFalse(matches("", "public-fixture"))
        self.assertTrue(matches(manifest.replace('="public-fixture"', '=""'), ""))

    def test_workflow_passes_only_exact_public_variables_via_masked_channel(self):
        root = Path(__file__).resolve().parents[2]
        caller = (root / ".github/workflows/mobile-ci.yml").read_text()
        builder = (root / ".github/workflows/android-qa-build.yml").read_text()
        mappings = dict(re.findall(r"(GAONONE_\w+): \$\{\{ vars\.(\w+) \}\}", caller))
        self.assertEqual(mappings, {key: key for key in (*PUBLIC_KEYS, MAPS_KEY)})
        masked = dict(re.findall(r"(GAONONE_\w+): \$\{\{ secrets\.(\w+) \}\}", builder))
        self.assertEqual(masked, mappings)
        self.assertNotIn("secrets: inherit", caller)
        self.assertNotIn("${{ vars.", builder)
        self.assertIn("uses: ./.github/workflows/android-qa-build.yml", caller)
        self.assertIn('python3 mobile/tool/qa_build_config.py', builder)
        self.assertIn('--dart-define-from-file="$RUNNER_TEMP/gaonone-qa.json"', builder)

    def test_required_gate_runs_and_rejects_every_unsuccessful_build_state(self):
        root = Path(__file__).resolve().parents[2]
        workflow = (root / ".github/workflows/mobile-ci.yml").read_text()
        gate = workflow.split("  analyze-and-build-android:\n", 1)[1]
        self.assertIn("needs: android-qa", gate)
        self.assertIn("if: ${{ always() }}", gate)
        self.assertIn("ANDROID_QA_RESULT: ${{ needs.android-qa.result }}", gate)
        script = textwrap.dedent(gate.split("        run: |\n", 1)[1])
        for state in ("success", "failure", "cancelled", "skipped", ""):
            with self.subTest(state=state):
                result = subprocess.run(["bash", "-eu", "-c", script],
                                        env={**os.environ, "ANDROID_QA_RESULT": state},
                                        capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 0 if state == "success" else 1)

    def test_missing_configuration_is_reported_not_invented(self):
        values, report = configuration({})
        self.assertEqual(values["API_URL"], "https://gaonone.in/api/v1")
        self.assertEqual(values["GAONONE_LEGACY_OTP_ENABLED"], "false")
        self.assertEqual(report["missing_public_variables"], list(PUBLIC_KEYS))
        self.assertFalse(report["production_release"])
        self.assertFalse(report["physical_device_tested"])

    def test_only_public_allowlist_crosses_build_boundary(self):
        env = dict.fromkeys(PUBLIC_KEYS, "public-fixture")
        env.update(FIREBASE_SERVICE_ACCOUNT_JSON_B64="private-server-fixture",
                   GAONONE_RELEASE_KEY_PASSWORD="private-signing-fixture",
                   API_URL="http://untrusted.invalid", GAONONE_LEGACY_OTP_ENABLED="true")
        values, report = configuration(env)
        self.assertEqual(set(values), set(PUBLIC_KEYS) | {
            "API_URL", "GAONONE_LEGACY_OTP_ENABLED", "GAONONE_QA_BUILD",
            MAPS_KEY, "GAONONE_ANDROID_MAPS_ENABLED"})
        self.assertNotIn("private", json.dumps(values))
        self.assertEqual(values["API_URL"], API_URL)
        self.assertEqual(values["GAONONE_LEGACY_OTP_ENABLED"], "false")
        self.assertEqual(report["firebase_public_configuration"], "provided_unverified")

    def test_whitespace_is_missing(self):
        _, report = configuration(dict.fromkeys(PUBLIC_KEYS, " \n"))
        self.assertEqual(report["missing_public_variables"], list(PUBLIC_KEYS))

    def test_maps_opt_in_never_enables_backend_providers(self):
        for key in ("", "  ", "public-maps-fixture"):
            with self.subTest(key=bool(key.strip())):
                values, report = configuration({**dict.fromkeys(PUBLIC_KEYS, "public-fixture"),
                    MAPS_KEY: key, "MAPS_API_KEY": "server-fixture", "MAPS_PROVIDER": "google"})
                self.assertEqual(values["GAONONE_ANDROID_MAPS_ENABLED"],
                                 "true" if key.strip() else "false")
                self.assertEqual(report["android_maps"], "google_configured_unverified"
                                 if key.strip() else "openstreetmap_fallback")
                self.assertNotIn("MAPS_PROVIDER", values)
                self.assertNotIn("MAPS_API_KEY", values)
                self.assertNotIn("public-maps-fixture", json.dumps(report))

    def test_cli_rejects_each_missing_variable_before_build_configuration(self):
        for missing in PUBLIC_KEYS:
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                env = os.environ.copy()
                env.update(dict.fromkeys(PUBLIC_KEYS, "public-fixture"))
                env.pop(missing, None)
                result = subprocess.run(
                    [sys.executable, str(Path(__file__).with_name("qa_build_config.py")),
                     "--output", str(root / "config.json"), "--report", str(root / "report.json")],
                    env=env, capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn(missing, result.stderr)
                self.assertNotIn("public-fixture", result.stdout + result.stderr)
                self.assertFalse((root / "config.json").exists())

    def test_real_cli_writes_valid_json_without_logging_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = os.environ.copy()
            env.update(dict.fromkeys(PUBLIC_KEYS, 'public-fixture-"escaped"'))
            env[MAPS_KEY] = 'public-maps-fixture'
            result = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("qa_build_config.py")),
                 "--output", str(root / "config.json"), "--report", str(root / "report.json")],
                env=env, capture_output=True, text=True, check=True,
            )
            self.assertNotIn("public-fixture", result.stdout + result.stderr)
            self.assertNotIn("public-maps-fixture", result.stdout + result.stderr)
            self.assertEqual(json.loads((root / "config.json").read_text())[PUBLIC_KEYS[0]],
                             'public-fixture-"escaped"')
            self.assertEqual(json.loads((root / "report.json").read_text())["api_url"], API_URL)


if __name__ == "__main__":
    unittest.main()
