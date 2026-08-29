from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from app.db.session import SessionLocal
from app.models.orders import DeliveryLocation


def main() -> None:
    days = int(os.getenv("DELIVERY_LOCATION_RETENTION_DAYS", "30"))
    if days < 1 or days > 365:
        raise RuntimeError("DELIVERY_LOCATION_RETENTION_DAYS must be between 1 and 365")

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    db = SessionLocal()
    try:
        before = db.scalar(select(func.count()).select_from(DeliveryLocation)) or 0
        result = db.execute(delete(DeliveryLocation).where(DeliveryLocation.recorded_at < cutoff))
        db.commit()
        removed = result.rowcount or 0
        after = before - removed
        print(
            f"Delivery location retention complete. Removed={removed}, remaining={after}, "
            f"cutoff={cutoff.isoformat()}, retention_days={days}"
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
