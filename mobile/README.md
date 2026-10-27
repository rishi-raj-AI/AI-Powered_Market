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
