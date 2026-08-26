import redis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health_check() -> dict[str, str]:
    return {"status": "ok", "version": settings.APP_VERSION}


@router.get("/ready")
def readiness_check(db: Session = Depends(get_db)) -> dict[str, str]:
    checks = {"database": "down", "redis": "down"}

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        pass

    try:
        client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
        if client.ping():
            checks["redis"] = "ok"
    except Exception:
        pass

    if any(value != "ok" for value in checks.values()):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", **checks},
        )
    return {"status": "ready", **checks}
