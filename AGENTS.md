# GaonOne Agent Development Contract

## Product mission
GaonOne is a delivery-first commerce platform for rural, semi-urban and Tier-1 India. It connects customers with local merchants and delivery partners for food, grocery, daily essentials, agriculture supplies, hardware, general retail, parcels and other deliverable goods.

## Explicit non-goals
- No passenger ride hailing.
- No taxi, bike-taxi, auto or passenger mobility domain.
- Do not introduce ride/trip/passenger pricing models.

## Product principles
1. One shared commerce and fulfilment platform; verticals are capabilities, not independent cloned apps.
2. Rural-first constraints: low bandwidth, imperfect addresses, landmarks, multilingual/voice-ready UX, COD and scheduled/batched delivery.
3. Tier-1 quality: the same APIs and data model must support dense urban usage and fast delivery.
4. Delivery is a first-class domain: merchant acceptance, dispatch, assignment, pickup, tracking, proof of delivery, cancellation and settlement must be auditable.
5. Prefer a modular monolith until scale measurements justify service extraction.
6. Keep external integrations behind provider interfaces.

## Current stack
- Backend: Python + FastAPI + SQLAlchemy + Alembic
- Database: PostgreSQL + PostGIS
- Cache/async infrastructure: Redis
- Mobile: Flutter
- Web/Admin: Next.js
- Containers: Docker
- CI/CD: GitHub Actions

## Engineering rules
- Never commit secrets or real credentials.
- Preserve API compatibility unless a migration is explicitly documented.
- Every schema change requires an Alembic migration.
- New backend behavior requires tests.
- Authorization must be server-side and role/ownership checked.
- Money uses fixed-precision decimal/minor-unit representations, never binary float for accounting.
- Store timestamps in UTC and expose explicit timezone semantics at boundaries.
- Use idempotency for payment and order-creation side effects.
- Delivery/order state transitions must be validated; never allow arbitrary status mutation.
- Prefer PostGIS indexed spatial queries for production geo discovery/dispatch rather than loading all coordinates into Python.
- Log important order/payment/delivery transitions with correlation identifiers.
- Do not put provider-specific payment, SMS, maps, storage or logistics logic directly in domain routes.

## Required validation before completion
Run the relevant commands for the changed surface. Prefer repository Makefile targets when available. At minimum for backend changes run formatting/lint/type checks if configured and the backend test suite. For mobile/web changes run their configured analysis/build/test commands.

## Delivery domain vocabulary
- `Order`: commercial commitment between customer and merchant.
- `DeliveryTask`: fulfilment job moving goods from pickup to drop-off.
- `DeliveryPartner`: person/organization capable of fulfilling delivery tasks.
- `Assignment`: relationship between a delivery task and partner.
- `TrackingEvent`: append-oriented operational location/status evidence.
- `ProofOfDelivery`: evidence of completed handoff.

Do not use `Ride`, `PassengerTrip`, `Taxi`, or equivalent passenger-mobility abstractions for delivery.

## Agent workflow
For substantial work: inspect existing models/routes/tests first, implement the smallest coherent vertical slice, add migrations/tests, run validation, then summarize changed files, migration impact, API impact and remaining risks. Avoid unrelated refactors in feature branches.