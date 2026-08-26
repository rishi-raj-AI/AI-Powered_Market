# GaonOne Mobile

Flutter source for the shared Android/iOS application. It currently implements phone OTP login, village selection, store discovery, catalogue browsing and add-to-cart using the same FastAPI backend.

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
