# GaonOne / AI-Powered Market

Hyperlocal rural commerce platform for village and semi-rural markets in India.

## MVP goal
Build a production-ready platform that connects customers, local merchants and delivery partners through mobile and web applications.

## Planned applications
- Customer mobile app
- Merchant mobile app
- Delivery partner mobile app
- Customer web app
- Admin web portal
- FastAPI backend

## Initial stack
- Backend: FastAPI + Python
- Database: PostgreSQL + PostGIS
- Cache/async support: Redis
- Mobile: Flutter
- Web/Admin: Next.js
- Containers: Docker

## Delivery-first foundation — complete

The delivery-first foundation and Waves 1–6 implementation program are
integrated on `main`. This includes authoritative pricing and inventory,
delivery lifecycle and proof controls, PostGIS serviceability and dispatch,
payment/COD/refund/settlement boundaries, tracking, notifications, and the
customer, merchant, rider, and admin product surfaces.

The next operating stage is **staging E2E validation and launch preparation**:
configure the required provider credentials, exercise real provider flows in
staging, and retain exact-SHA CI evidence before any production decision.

## Local backend quick start

```bash
cp .env.example .env
docker compose up --build
```

Then open:
- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health

## Status
Foundation complete. The current deployable integration commit is
`5528f86224ba2cf2533d9f5632740286c2009a14`; its Backend, Web, Mobile, and
Production CI workflows passed. See `docs/release-reconciliation-state.md` for
the integration record and `docs/PRODUCTION_DEPLOYMENT.md` for the staging
deployment procedure.
