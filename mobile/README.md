# GaonOne Mobile

Flutter source for the shared Android/iOS application. The launch login is Firebase/Google Sign-In with a GaonOne backend session; the legacy backend-owned phone OTP UI is retained only for an explicitly enabled compatible build. It also implements village selection, store discovery, catalogue browsing and add-to-cart using the same FastAPI backend.

## One-time platform generation on a development Mac
From this directory run:

```bash
flutter create . --platforms=android,ios --org in.gaonone
flutter pub get
```

Then run iOS simulator with:
```bash
flutter run --dart-define=API_URL=http://127.0.0.1:8000/api/v1
```

Android emulator uses the default `10.0.2.2:8000` API URL.

## Legacy direct OTP development

The Firebase launch build hides the legacy OTP controls by default. To exercise
the local development OTP flow, explicitly opt in while using a backend that
has `AUTH_PROVIDER=local_otp` and `SMS_AUTH_ENABLED=true`:

```bash
flutter run --dart-define=API_URL=http://127.0.0.1:8000/api/v1 --dart-define=GAONONE_LEGACY_OTP_ENABLED=true
```

This presentation flag never enables a backend route and must remain false for
the Firebase launch. Production SMS activation additionally requires the
server-side MSG91/DLT configuration and device validation; do not place any
provider credentials in this build flag.


## Android build and acceptance gate

The pull-request workflow runs `flutter analyze lib`, `flutter test`, and
`flutter build apk --debug`. This is a development artifact, **not** a
production-signed APK. Build validation must not be inferred from a queued CI run.

On a development Mac with Flutter and Android SDK installed:

```bash
cd mobile
flutter doctor -v
flutter pub get --enforce-lockfile # if pubspec.lock is committed
flutter analyze lib
flutter test
flutter build apk --debug --dart-define=API_URL=https://gaonone.in/api/v1 --dart-define=GAONONE_LEGACY_OTP_ENABLED=false
```

Release builds deliberately fail unless `mobile/android/key.properties` exists.
Create it **locally**, never in Git, with these four properties:

```properties
storePassword=YOUR_LOCAL_SECRET
keyPassword=YOUR_LOCAL_SECRET
keyAlias=YOUR_RELEASE_KEY_ALIAS
storeFile=/absolute/path/to/private/upload-keystore.jks
```

Then run `flutter build apk --release --dart-define=API_URL=https://gaonone.in/api/v1 --dart-define=GAONONE_LEGACY_OTP_ENABLED=false`.
Do not distribute the APK until the production backend supports the chosen
mobile authentication flow and release signing is independently verified.

**Real-device acceptance checklist:** Google sign-in and token exchange;
GPS-denied village discovery; slow/failed GPS lookup; offline refresh and retry;
store inventory and cart quantity; COD quote and idempotent checkout recovery;
landmark-only address; order history; Hindi/Marathi text clipping; low-memory
Android startup; flaky 2G/3G networking; delivery proof and cash collection.
Use a real low-end Android device and preserve the test evidence. A successful
debug build alone does not satisfy these gates.
