from fastapi import APIRouter

from app.api.v1.routes.admin import router as admin_router
from app.api.v1.routes.ai_assist import router as ai_assist_router
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.basket_recommendations import router as basket_recommendations_router
from app.api.v1.routes.cart_health import router as cart_health_router
from app.api.v1.routes.checkout import router as checkout_router
from app.api.v1.routes.checkout_decision import router as checkout_decision_router
from app.api.v1.routes.checkout_quote import router as checkout_quote_router
from app.api.v1.routes.commerce import router as commerce_router
from app.api.v1.routes.delivery_analytics import router as delivery_analytics_router
from app.api.v1.routes.delivery_financials import router as delivery_financials_router
from app.api.v1.routes.delivery_operations import router as delivery_operations_router
from app.api.v1.routes.delivery_tasks import router as delivery_tasks_router
from app.api.v1.routes.delivery_windows import router as delivery_windows_router
from app.api.v1.routes.discovery import router as discovery_router
from app.api.v1.routes.dispatch import router as dispatch_router
from app.api.v1.routes.fulfillment import router as fulfillment_router
from app.api.v1.routes.fulfillment_recommendation import router as fulfillment_recommendation_router
from app.api.v1.routes.geography import router as geography_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.media import router as media_router
from app.api.v1.routes.merchant_intelligence import router as merchant_intelligence_router
from app.api.v1.routes.merchant_reliability import router as merchant_reliability_router
from app.api.v1.routes.notifications import router as notifications_router
from app.api.v1.routes.order_mutations import router as order_mutations_router
from app.api.v1.routes.order_recovery import router as order_recovery_router
from app.api.v1.routes.orders import router as orders_router
from app.api.v1.routes.payment_hardening import router as payment_hardening_router
from app.api.v1.routes.payments import router as payments_router
from app.api.v1.routes.personalized_feed import router as personalized_feed_router
from app.api.v1.routes.preparation_estimate import router as preparation_estimate_router
from app.api.v1.routes.reorder import router as reorder_router
from app.api.v1.routes.repeat_cadence import router as repeat_cadence_router
from app.api.v1.routes.search_suggestions import router as search_suggestions_router
from app.api.v1.routes.store_availability import router as store_availability_router
from app.api.v1.routes.store_discovery import router as store_discovery_router
from app.api.v1.routes.substitutions import router as substitutions_router
from app.api.v1.routes.support import router as support_router
from app.api.v1.routes.tracking import router as tracking_router
from app.api.v1.routes.tracking_hardening import router as tracking_hardening_router
from app.api.v1.routes.users import router as users_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(geography_router)
api_router.include_router(store_discovery_router)
api_router.include_router(discovery_router)
api_router.include_router(search_suggestions_router)
api_router.include_router(fulfillment_router)
api_router.include_router(fulfillment_recommendation_router)
api_router.include_router(delivery_windows_router)
api_router.include_router(substitutions_router)
api_router.include_router(reorder_router)
api_router.include_router(repeat_cadence_router)
api_router.include_router(personalized_feed_router)
api_router.include_router(basket_recommendations_router)
api_router.include_router(store_availability_router)
api_router.include_router(cart_health_router)
api_router.include_router(preparation_estimate_router)
api_router.include_router(merchant_reliability_router)
api_router.include_router(commerce_router)
api_router.include_router(delivery_tasks_router)
api_router.include_router(checkout_quote_router)
api_router.include_router(checkout_decision_router)
api_router.include_router(checkout_router)
api_router.include_router(order_recovery_router)
api_router.include_router(order_mutations_router)
api_router.include_router(orders_router)
api_router.include_router(delivery_financials_router)
api_router.include_router(delivery_operations_router)
api_router.include_router(dispatch_router)
api_router.include_router(delivery_analytics_router)
api_router.include_router(tracking_hardening_router)
api_router.include_router(tracking_router)
api_router.include_router(payment_hardening_router)
api_router.include_router(payments_router)
api_router.include_router(notifications_router)
api_router.include_router(media_router)
api_router.include_router(ai_assist_router)
api_router.include_router(merchant_intelligence_router)
api_router.include_router(support_router)
api_router.include_router(admin_router)
