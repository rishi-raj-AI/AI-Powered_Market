# Firebase authentication plan

## Intended flow

`Google Sign-In → Firebase client session → Firebase ID token → GaonOne server verification → provider identity (Firebase UID) → GaonOne account → GaonOne backend session → normal GaonOne authorization`

Authentication answers “who is this external person?” Authorization answers “what can this GaonOne account do?” Firebase never grants merchant ownership, delivery permissions, admin rights, or domain state authority.

## Implementation design to validate before coding

- Add a provider identity model/table rather than permanently keying identity by email. Store provider, immutable UID, linked user, creation/link/audit timestamps, and only necessary verified profile metadata.
- Verify Firebase ID tokens server-side with configured project/audience/issuer constraints; classify malformed, expired, revoked/disabled, and unknown identities safely.
- On first login, create or explicitly link a GaonOne customer account without role escalation. Repeated login resolves the same UID.
- Define a safe migration/linking policy for pre-existing phone-based accounts. Never silently match only on a mutable email. Resolve duplicate or ambiguous matches through an authenticated, auditable linking flow.
- Preserve room for multiple methods per account; do not delete SMS provider code. SMS is disabled for MVP.
- Backend session expiry, logout, revocation, account deactivation, and identity-link audit events remain GaonOne responsibilities.

## Required tests

Valid, invalid, expired, malformed, revoked/disabled, and unknown-UID tokens; first/repeat login; duplicate prevention; account linking; inactive account; role/merchant/delivery/admin authorization; backend logout/revocation; disabled SMS routes; disabled SMS configuration; and production rejection of development OTP.

## Owner configuration boundary

Owner must supply Firebase project/server credentials securely, web OAuth origins, Android package/SHA configuration, iOS bundle/reversed-client configuration and signing, and launch domains. No secrets belong in Git or test fixtures.

## Phase 2B client integration

- Web reads only public `NEXT_PUBLIC_FIREBASE_*` identifiers at runtime, uses the Firebase Google provider to obtain an ID token, and exchanges that token at `/auth/firebase/exchange`. It must not trust Firebase profile fields for GaonOne roles or ownership.
- Flutter uses public build-time Firebase identifiers (`GAONONE_FIREBASE_<PLATFORM>_*`) plus an optional `GAONONE_GOOGLE_SERVER_CLIENT_ID`; it uses Google Sign-In only to obtain a Firebase session and then exchanges the Firebase ID token with GaonOne.
- Before Android/iOS device acceptance, the owner must register `in.gaonone.gaonone_mobile`, add the Android SHA fingerprints, configure iOS reversed-client URL handling/signing, enable Google as a Firebase Authentication provider, and provide the Firebase options/build identifiers. These configuration artifacts and credentials are not to be committed by an agent.
- Both clients fail closed with a visible configuration error when required public Firebase identifiers are absent. Local GaonOne tokens are only stored after the backend exchange succeeds.
