# Maps client integration and QA

## Source and scope

Audited main `575df507e879dff94569d04f6c57878c259446e2` and QA PR #225 head `599ff6c5d5dbf72edf460e464cd9edfb83af2f19`. Integration is isolated on `feat/maps-client-integration`, stacked on #225; neither PR may merge without approval. No server, production environment file, Firebase authentication, backend permission, address schema, or stored address is changed.

Before this change, Flutter used `flutter_map` 8.2.2 and OpenStreetMap tiles in customer delivery tracking, plus `geolocator` for GPS. Opening rider coordinates in external Google Maps is a URL link, not Maps SDK or an embedded browser Maps API. There was no Android Maps key consumer. Next.js already loads Maps JavaScript in `web/components/LocationMap.tsx`. FastAPI has separately gated Places/autocomplete/details, Geocoding and Routes clients.

This change adds official `google_maps_flutter` 2.19.0 to the existing Android delivery-tracking surface only. The pinned QA toolchain Flutter 3.47.1 / Dart 3.13.1 meets its requirements. iOS/web Flutter retain the previous renderer. Dependency resolution includes the plugin's other platform packages; no iOS Google key or initialization is introduced and no iOS build acceptance is claimed. Customer GPS, village selection, landmarks, house details and manual directions remain unchanged.

## Android configuration

1. Repository Settings → Secrets and variables → Actions → **Variables**: set `GAONONE_GOOGLE_MAPS_ANDROID_API_KEY` to the public **GaonOne Android Maps - QA** key. Owner confirmed it is set; a names-only API read verified its presence. Never paste it into code or commit generated configuration.
2. Keep the existing five Firebase/Google-login Variables unchanged. Maps is separate from Firebase API configuration.
3. Mobile CI explicitly maps the new Variable through the reusable workflow's masked channel. `mobile/tool/qa_build_config.py` includes it in temporary Dart-define JSON and derives `GAONONE_ANDROID_MAPS_ENABLED=true` only when it is nonblank. There is no additional repository flag to configure. Without it, the existing OpenStreetMap fallback remains usable.
4. Flutter receives `--dart-define-from-file`. Gradle decodes Flutter's `dart-defines` property and injects only the Maps key into `${gaononeMapsApiKey}` → manifest metadata `com.google.android.geo.API_KEY`. Enabling native Maps without a key fails. CI compares the compiled APK metadata with the intended key without printing either value.
5. Restrict the key to **Maps SDK for Android** (`maps-android-backend.googleapis.com`) and package **`in.gaonone.gaonone_mobile`**, with the **certificate SHA-1 of the exact APK being installed**. API restriction and API enablement are distinct; verify both in `gaonone-staging`.
6. QA runners generate a new debug signing key per build. The known previous #225 certificate SHA-1 was `9E:02:35:3D:4F:F6:99:47:21:97:25:96:92:7B:A7:78:6B:EB:16:45`; do not assume it matches a new build. Register the new artifact certificate in the Android Maps key restriction and Firebase Android app for login. Do not remove the prior fingerprint while its APK is still being tested. Stable QA signing requires separate owner-managed secure storage; no private key is uploaded or reused here.

Native SDK authorization failures may leave blank tiles without a Dart error. The tracking view always offers **Use alternative map** when native Maps is selected; this restores the existing OpenStreetMap view for that mounted view. It is not an offline tile cache. Existing textual tracking and external-map links remain. No new background location collection or extra GPS permission is requested.

## Website configuration (future authorized deployment only)

The production environment name is **`GOOGLE_MAPS_BROWSER_KEY`**, in the existing `.env.production` file. `docker-compose.prod.yml` maps it to Docker build argument `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`; `web/Dockerfile.prod` exposes it during `next build`. Changing only the running container environment is insufficient; rebuild the web image in the approved release process. Nothing is applied to the server by this PR.

For existing tracking markers, also configure **`GOOGLE_MAPS_MAP_ID`** with a JavaScript map ID from the same project; Compose maps it to `NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID`. It is a public map identifier, not an API key. Base-map rendering can work without it, but existing Advanced Markers cannot. Do not use a demo ID for production.

Restrict the browser key to **Maps JavaScript API** (`maps-backend.googleapis.com`), with website referrers exactly `https://gaonone.in/*` and `https://www.gaonone.in/*` (no regex escapes). These restrictions intentionally exclude localhost and GitHub preview domains; use mocked tests locally, not a weakened production key.

Deployment prerequisite: the repository Caddy CSP currently allows `maps.googleapis.com` but lacks Maps resource allowances such as `maps.gstatic.com` and Google font resources. Live server policy may differ. No Caddy/server configuration is changed in this PR. Before website activation, review the actual response policy against Google's CSP guide in a separately approved release change, preserve all working Firebase allowances, and validate real map loading on an allowed hostname. Source tests do not prove provider-console settings or production CSP compatibility.

Web fixes here synchronize coordinates/overlays after asynchronous map initialization and retain serviceability/manual landmarks when optional reverse-geocoding is disabled or returns no address. They do not add new provider endpoints or enable search billing.

## Cost boundary

Keep backend **`MAPS_PROVIDER=none`** and **`MAPS_API_KEY` empty**. Do not put either client key into `MAPS_API_KEY`. The backend's shared provider switch gates existing Places, Geocoding and Routes clients together. Native/browser key injection does not change it. Basic map display follows the owner's enabled Maps SDK/Maps JavaScript billing arrangements; loading a map must not be described as a blanket zero-cost guarantee.

Places autocomplete/details, reverse-geocoding and route/ETA activation require a separate review of current SKU prices, expected calls per user/tracking session, cache behavior, quotas/budget alerts and explicit owner approval. Existing UI requests to disabled backend location routes can return unavailable; manual/GPS entry remains. Tests use fake platforms/providers and do not call Google services.

## QA checklist

- Run Flutter analysis, all tests, the native-enabled fake-platform test, and Python configuration/manifest regression tests. Run TypeScript, location/tracking/fallback browser tests, and Next.js build.
- Require exact-head Android CI success, compiled manifest comparison, package/QA-label/signature verification, APK checksum and artifact publication. Keep artifact source SHA and public signing-certificate report together.
- Register the **new** APK certificate as above. Confirm enabled APIs, package, restriction names and referrers in Cloud Console; these settings are owner-reported, not independently verified by source inspection. Do not request/export credentials to prove them.
- Install on an authorized Google Play-enabled Android 7.0+ physical device. Avoid overwriting an app signed by another key; use a test device/profile and never automatically uninstall user data.
- Using an authorized existing active-delivery test scenario, check native map tiles, store/customer/rider markers, rider updates, stale-position warning and delivery-completion privacy. Creating production orders is not authorized by this checklist.
- Use the alternative-map control; deny GPS, switch location services off, and test weak/offline connectivity. Confirm village/landmark/house/directions entry and saved addresses remain intact.
- Test Google login, cancellation, session restoration and logout; code is unchanged, but signing registration still governs native login.
- Check configuration status says `google_configured_unverified` for the Maps-enabled artifact. Build success is not physical map/login acceptance. No merge, deploy or app publication is automatic.

References: [Flutter setup](https://developers.google.com/maps/flutter-package/config), [Android key restrictions](https://developers.google.com/maps/documentation/android-sdk/get-api-key), [Advanced Markers](https://developers.google.com/maps/documentation/javascript/advanced-markers/start), [Maps CSP](https://developers.google.com/maps/documentation/javascript/content-security-policy).
