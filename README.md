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

## Sprint 1
1. Backend foundation
2. PostgreSQL/PostGIS connectivity
3. Health endpoint
4. Authentication and role model
5. Village/service area model
6. Merchant/store/product models
7. First Flutter shell

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
Foundation setup in progress.
