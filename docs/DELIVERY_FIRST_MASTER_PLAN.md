# GaonOne Delivery-First Master Plan

## Vision
A single delivery-first marketplace for India: discover anything locally available, order it, pay for it, and get it delivered or fulfilled through one platform. Rural India is the entry wedge; the architecture must remain suitable for Tier-1 density and service levels.

## Scope
### Initial verticals
- Restaurant/food delivery
- Kirana and grocery
- Fruits, vegetables and dairy
- General local retail
- Hardware/home essentials
- Agriculture inputs and supplies
- Parcel/local courier

Regulated categories such as medicines require capability flags, compliance review and jurisdiction/provider-specific controls before activation.

### Excluded
Passenger mobility and ride hailing are outside the product.

## Users and applications
1. Customer mobile app and web/PWA
2. Merchant app/portal
3. Delivery partner app
4. Operations/admin portal
5. Platform APIs and integration layer

## Core domains
### Identity and trust
Users, roles, OTP/session authentication, merchant onboarding, delivery-partner onboarding, verification, device/session controls and audit trails.

### Geography
States/districts/blocks/villages/localities, service zones, PostGIS points/polygons, landmark-aware addresses and serviceability.

### Catalogue and inventory
Merchant stores, categories, products, variants, prices, stock, availability windows, images and vertical-specific attributes.

### Discovery
Nearby stores, search, category browse, availability, serviceability, delivery ETA and later personalized ranking.

### Cart and pricing
Cart, item pricing, taxes where applicable, merchant charges, delivery fees, promotions, tips and final quote snapshots.

### Orders
Immutable commercial snapshots, explicit order state machine, merchant acceptance/rejection, preparation, cancellation/refunds and customer history.

### Delivery
Delivery tasks, dispatch, offers/assignment, pickup verification, live tracking, delivery verification, proof of delivery, failures/retries and batched/scheduled delivery.

### Payments and settlements
Provider abstraction, UPI/provider checkout, COD, idempotent callbacks, refunds, merchant settlement ledger, delivery-partner earnings and reconciliation.

### Notifications and support
Push/SMS/WhatsApp-ready provider boundaries, order event notifications, issue/ticket model and admin intervention.

### AI layer
Introduce after transactional correctness: multilingual intent/search, voice ordering, catalogue extraction, support assistant, demand forecasting, dispatch scoring and merchant recommendations. AI must not be the source of truth for money, authorization or order/delivery state transitions.

## Rural-first requirements
- Low-bandwidth/mobile-first UX and graceful retries.
- Landmark + GPS + village/locality addressing.
- COD and assisted digital-payment compatibility.
- Scheduled and route-batched delivery, not only instant delivery.
- Merchant self-delivery and GaonOne delivery-partner modes.
- Local-language/voice-ready data and UI architecture.
- Offline-tolerant delivery-partner event queue with server reconciliation.

## Architecture strategy
Use a modular monolith initially. Maintain domain boundaries inside the FastAPI application and database. Extract services only when scaling, ownership or reliability data demonstrates the need.

### Platform modules
identity -> geography -> merchant -> catalogue -> inventory -> discovery -> cart/pricing -> orders -> payments -> delivery/dispatch -> tracking -> notifications -> settlements -> support -> AI/integrations

### Infrastructure
PostgreSQL/PostGIS is the transactional and geospatial source of truth. Redis supports cache, locks, rate limits and ephemeral dispatch state. Object storage holds media/proof artifacts. Introduce a durable event broker/outbox when asynchronous volume requires it. Search can begin with PostgreSQL and later move to a dedicated engine when measured need justifies it.

## Order state model
Recommended high-level lifecycle:
`PENDING_PAYMENT -> PLACED -> MERCHANT_ACCEPTED -> PREPARING -> READY_FOR_PICKUP -> PICKED_UP -> OUT_FOR_DELIVERY -> DELIVERED`

Terminal/exception paths include `PAYMENT_FAILED`, `MERCHANT_REJECTED`, `CANCELLED`, `DELIVERY_FAILED`, and refund states. Exact transitions must be centralized and validated.

## Delivery task state model
`CREATED -> SEARCHING -> ASSIGNED -> ARRIVED_PICKUP -> PICKED_UP -> EN_ROUTE -> ARRIVED_DROPOFF -> DELIVERED`

Exception paths include assignment expiry/reassignment, partner cancellation, pickup failure and delivery failure. Delivery state and order state are related but must not be the same field.

## Dispatch evolution
### V1
Nearest eligible available partner within service zone; deterministic scoring and explicit assignment timeout.

### V2
Score distance-to-pickup, vehicle/capacity, current load, merchant preparation ETA, destination direction, reliability and estimated cost.

### V3
Batching/route optimization for rural scheduled delivery and dense urban multi-order delivery. Add ML only after enough operational data exists.

## Security/reliability baseline
- Role and ownership authorization on every privileged operation.
- Rate limiting for auth/OTP and abuse-sensitive endpoints.
- Idempotency keys for order/payment mutations.
- Webhook signature verification and replay protection.
- Audit logs for admin, merchant, payment and delivery transitions.
- PII minimization and retention rules.
- Database constraints plus application state-machine validation.
- Health/readiness checks, structured logs, metrics and tracing/correlation IDs.
- Backups and tested restore process before production launch.

## Development program
### Phase 0 — Foundation hardening
Agent instructions, architecture contract, test baseline, CI validation, domain/state-machine audit, security audit, PostGIS query audit and observability baseline.

### Phase 1 — Commerce core
Customer address/serviceability, catalogue/inventory, cart/quote, robust order lifecycle, merchant order operations and customer history.

### Phase 2 — Delivery core
Partner profile/availability, delivery-task lifecycle, dispatch/assignment, pickup/drop verification, tracking, proof of delivery and delivery admin operations.

### Phase 3 — Payments/settlements
Production provider integration, COD reconciliation, refunds, ledgers, merchant settlements and delivery earnings.

### Phase 4 — Product applications
Complete customer, merchant and delivery-partner mobile journeys plus production admin/ops experience.

### Phase 5 — Rural operating model
Scheduled/batched delivery, landmark addressing, offline partner behavior, assisted ordering/payment and multilingual foundations.

### Phase 6 — Intelligence and scale
AI discovery/voice/catalogue/support, demand forecasting, advanced dispatch, search infrastructure, performance/load hardening and selective service extraction.

### Phase 7 — Network expansion
External seller/logistics integrations such as ONDC where commercially and operationally justified, plus pan-India shipping integrations.

## Definition of MVP
A real customer in one launch geography can register, set a serviceable address, discover an approved merchant, view live stock/price, place an order, pay or choose COD, receive merchant acceptance, have a delivery task assigned to a partner, track fulfilment, receive the goods with proof of delivery, rate/report the experience, while merchant/admin/partner views all remain consistent and auditable.

## Immediate engineering priorities
1. Audit existing models/migrations/routes against the two state machines above.
2. Replace production-scale Python-side geo filtering with PostGIS-indexed queries.
3. Establish explicit serviceability/address model.
4. Harden order transition and idempotency rules.
5. Harden delivery assignment/tracking/POD lifecycle.
6. Establish payment/COD ledger and webhook invariants.
7. Expand integration tests around the complete order-to-delivery journey.
8. Build the three role-specific product journeys against stable APIs.

## Rule for every future feature
A feature is not complete because an endpoint or screen exists. It is complete only when authorization, validation, state transitions, persistence/migration, error behavior, tests, observability and the affected user journey are all coherent.