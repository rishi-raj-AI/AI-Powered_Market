# Android QA APK — Issue #224

This is a **debug-signed QA build**, not a production release or proof of physical-device acceptance. It uses the existing shared Flutter app and `https://gaonone.in/api/v1`. No server, database, role, Firebase Admin credential, or deployment configuration is changed. Google Maps billing is not required.

## Download and install

1. Open the focused APK PR's **analyze-and-build-android** check, or GitHub Actions → **Mobile CI** → the successful run for the exact PR head.
2. Download `gaonone-qa-apk-<full-source-sha>` from **Artifacts** (GitHub sign-in/repository access required; retention 14 days). Unzip it. The APK is `gaonone-qa.apk`.
3. Read `configuration-status.json` first. All five public variables must be present or CI fails before building/publishing the APK. `provided_unverified` is not provider/device acceptance; nonempty inputs can still have incorrect project/client/certificate registration.
4. Compare the file with `SHA256SUMS`; retain `source-sha.txt`, `source-tree.txt`, APK metadata, toolchain versions, and `signing-certificate.txt` with test evidence. The certificate's SHA-1/SHA-256 are public; the private QA key is never uploaded.
5. Transfer to an authorized Android phone and install using Android's normal package installer, granting that installer permission if needed. App label: **GaonOne QA**. Alternatively, an authorized tester can use `adb install -r gaonone-qa.apk`.
6. The package remains `in.gaonone.gaonone_mobile` so Firebase identity and existing role behavior remain compatible. A previous installation signed with a different certificate will reject an update. Do not automatically uninstall: uninstalling clears local session/data. Use a separate test device/profile, or explicitly accept local-data loss before uninstalling the prior app. Never replace a production installation casually.

Flutter 3.47.1 defaults to Android API 24 minimum (Android 7.0) and target/compile API 36. The universal debug APK supports Flutter's Android debug architectures; the actual `native-code` entry in `apk-metadata.txt` is authoritative. It is larger/slower than an optimized release build, so do not use it for final performance acceptance. Google Sign-In requires a compatible Google-enabled device/account configuration.

## Owner actions for Google login

In repository Settings → Secrets and variables → Actions → **Variables**, add the existing public values for the same Firebase project used by the backend:

- `GAONONE_FIREBASE_ANDROID_API_KEY`
- `GAONONE_FIREBASE_ANDROID_APP_ID` (registered Android app, not the web app ID)
- `GAONONE_FIREBASE_ANDROID_MESSAGING_SENDER_ID`
- `GAONONE_FIREBASE_ANDROID_PROJECT_ID`
- `GAONONE_GOOGLE_SERVER_CLIENT_ID` (**Web OAuth client ID**, not Android OAuth client ID)

Verify the Firebase Android registration uses exactly `in.gaonone.gaonone_mobile`, Google provider is enabled, OAuth consent/test-user eligibility is correct, and the APK certificate SHA-1/SHA-256 from `signing-certificate.txt` are registered. A fresh hosted runner generates a fresh debug certificate; register the fingerprint of the artifact being tested. A stable internal QA signing identity can be introduced separately through an approved secret store; never cache/upload private debug keys as artifacts.

The existing implementation initializes Firebase with Dart options and Google with `serverClientId`; no new `google-services.json` is required for this path. Do not add server service-account JSON to the app. See [Google Sign-In Android integration](https://pub.dev/packages/google_sign_in_android) and [Firebase Android setup](https://firebase.google.com/docs/auth/android/google-signin).

After variables are set, re-run Mobile CI for the intended source revision. Variable updates do not alter an already-built APK. The manual workflow trigger is usable once this workflow revision is on the default branch; until then use the PR check's **Re-run jobs**. No production user or Super Admin record should be edited for this setup.

## Reproducible QA command

Use JDK 17, Flutter 3.47.1, Android SDK/platform 36 and the SDK-selected NDK (`28.2.13676358`). Export only the five public identifiers above. From repository root:

```bash
task_build_dir=$(mktemp -d)
python3 mobile/tool/qa_build_config.py --output "$task_build_dir/client.json" --report "$task_build_dir/status.json"
cd mobile
flutter pub get --enforce-lockfile
flutter analyze lib
flutter test
flutter test --no-pub --dart-define-from-file="$task_build_dir/client.json" test/qa_build_contract_test.dart test/auth_accounts_test.dart
flutter build apk --debug --no-pub --dart-define-from-file="$task_build_dir/client.json"
```

Expected local output after a successful build: `mobile/build/app/outputs/flutter-apk/app-debug.apk`. CI verifies nonempty output, package/QA label, APK signature, and records its actual hash before uploading. The generator fixes the HTTPS API and disables legacy OTP; it ignores unrelated environment variables and never logs public values or copies server/signing inputs. Missing/blank required variables exit with code 2, name only the missing inputs, and do not write build configuration. Configuration JSON is temporary and must not be committed.

## Production signing — separate, fail closed

Release no longer falls back to the debug key. An approved signing runner must inject all four inputs:

- `GAONONE_RELEASE_KEYSTORE_PATH` — secure external keystore path.
- `GAONONE_RELEASE_KEY_ALIAS`
- `GAONONE_RELEASE_STORE_PASSWORD`
- `GAONONE_RELEASE_KEY_PASSWORD`

Missing inputs reject the release task graph before execution; known Android debug alias/path are rejected. CI proves the missing-input rejection without reading any private key. Actual production certificate validation must still compare the built certificate to the owner-approved fingerprint; alias checks alone do not prove key ownership.

Owner must select/reuse the existing release key and distribution identity, store/recover it securely, and authorize release signing separately. Do not generate a replacement key without that decision. A future protected release job may map GitHub Actions **Secrets** to those environment variables and materialize the key in its private temporary directory. Never expose release credentials to pull-request jobs, print them, commit them, or upload the keystore. For Play distribution, register the actual Play app-signing certificate separately from the upload certificate. See [Flutter Android signing](https://docs.flutter.dev/deployment/android).

No signed production APK/AAB or app-store publication is produced by this QA workflow.

## Physical-device acceptance — not executed by CI

Record artifact hash, source SHA, device/OS, network condition, account role, result, and redacted evidence. Start with installation/launch and Google first/repeat login, cancellation, offline recovery, session restoration/expiry, and logout. Verify customer/merchant/delivery/admin routing from the backend account and denied cross-role requests; never manufacture role claims or change production users.

Then verify manual village/location fallback, catalogue, cart, COD checkout/status, merchant orders, rider pickup/proof/cash, and admin access only with explicitly authorized test operations/accounts. This APK points to the live API: placing orders or performing role workflows changes live business data. Obtain owner approval for such operations; building/downloading the APK does not authorize them. Preserve the existing Super Admin account and production Caddy CSP changes.

Maps, paid providers, SMS/OTP, FCM activation, UI redesign, and competitive features remain out of this P0 PR. Backend roles/permissions and all existing workspaces are unchanged. Passing CI/build/signature validation must be reported separately from install, native Google login, and field acceptance.
