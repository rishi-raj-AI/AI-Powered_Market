import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from qa_build_config import API_URL, PUBLIC_KEYS, configuration


class QaBuildConfigurationTests(unittest.TestCase):
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
            "API_URL", "GAONONE_LEGACY_OTP_ENABLED", "GAONONE_QA_BUILD"})
        self.assertNotIn("private", json.dumps(values))
        self.assertEqual(values["API_URL"], API_URL)
        self.assertEqual(values["GAONONE_LEGACY_OTP_ENABLED"], "false")
        self.assertEqual(report["firebase_public_configuration"], "provided_unverified")

    def test_whitespace_is_missing(self):
        _, report = configuration(dict.fromkeys(PUBLIC_KEYS, " \n"))
        self.assertEqual(report["missing_public_variables"], list(PUBLIC_KEYS))

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
            result = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("qa_build_config.py")),
                 "--output", str(root / "config.json"), "--report", str(root / "report.json")],
                env=env, capture_output=True, text=True, check=True,
            )
            self.assertNotIn("public-fixture", result.stdout + result.stderr)
            self.assertEqual(json.loads((root / "config.json").read_text())[PUBLIC_KEYS[0]],
                             'public-fixture-"escaped"')
            self.assertEqual(json.loads((root / "report.json").read_text())["api_url"], API_URL)


if __name__ == "__main__":
    unittest.main()
