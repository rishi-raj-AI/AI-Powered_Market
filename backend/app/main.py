from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    debug=settings.APP_DEBUG,
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {
        "name": settings.APP_NAME,
        "status": "running",
        "version": "0.1.0",
    }
