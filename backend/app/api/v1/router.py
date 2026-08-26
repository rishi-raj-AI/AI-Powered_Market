from fastapi import APIRouter

from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.commerce import router as commerce_router
from app.api.v1.routes.geography import router as geography_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.media import router as media_router
from app.api.v1.routes.orders import router as orders_router
from app.api.v1.routes.users import router as users_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(geography_router)
api_router.include_router(commerce_router)
api_router.include_router(orders_router)
api_router.include_router(media_router)
