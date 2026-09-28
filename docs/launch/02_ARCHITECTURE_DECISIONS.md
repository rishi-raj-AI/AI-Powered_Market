# Architecture decisions

GaonOne remains a modular monolith: FastAPI/SQLAlchemy/Alembic/PostgreSQL/PostGIS/Redis, Next.js, Flutter, Docker Compose, and durable worker/outbox processing. Provider integrations stay behind service boundaries; routes do not own provider details.

Auth target: Firebase authenticates the external person; GaonOne owns account records, roles, merchant and delivery ownership, admin authorization, addresses, orders, and all business state. After server verification of an ID token, the backend issues its existing-style GaonOne session. Domain routes continue to authorize from the GaonOne account, not Firebase client claims.

Persistent schema changes require additive, forward-safe Alembic migrations. A provider-identity record is preferred over treating email as permanent identity: provider name + immutable Firebase UID, linked to a GaonOne user, with uniqueness and audit timestamps. Validate exact existing-account/linking constraints before implementation.

Production/staging must fail closed: no development OTP; no active SMS endpoints without selected provider and required provider configuration; no implicit deployment from application merge.
