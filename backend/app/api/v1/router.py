from fastapi import APIRouter

from app.api.v1.routes.admin import router as admin_router
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.checkout import router as checkout_router
from app.api.v1.routes.commerce import router as commerce_router
from app.api.v1.routes.delivery_operations import router as delivery_operations_router
from app.api.v1.routes.delivery_tasks import router as delivery_tasks_router
from app.api.v1.routes.dispatch import router as dispatch_router
from app.api.v1.routes.geography import router as geography_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.media import router as media_router
from app.api.v1.routes.notifications import router as notifications_router
from app.api.v1.routes.order_mutations import router as order_mutations_router
from app.api.v1.routes.orders import router as orders_router
from app.api.v1.routes.payments import router as payments_router
from app.api.v1.routes.tracking import router as tracking_router
from app.api.v1.routes.users import router as users_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(geography_router)
api_router.include_router(commerce_router)
api_router.include_router(delivery_tasks_router)
# Hardened mutation routes are registered before the legacy orders router so
# checkout and cancellation use concurrency-safe transaction boundaries.
api_router.include_router(checkout_router)
api_router.include_router(order_mutations_router)
api_router.include_router(orders_router)
api_router.include_router(delivery_operations_router)
api_router.include_router(dispatch_router)
api_router.include_router(tracking_router)
api_router.include_router(payments_router)
api_router.include_router(notifications_router)
api_router.include_router(media_router)
api_router.include_router(admin_router)
