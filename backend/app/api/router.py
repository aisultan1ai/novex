from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.orders import router as orders_router
from app.api.v1.payments import router as payments_router
from app.api.v1.profile import router as profile_router
from app.api.v1.shipping import router as shipping_router
from app.api.v1.admin_carriers import router as admin_carriers_router
from app.api.v1.admin_customers import router as admin_customers_router
from app.api.v1.admin_orders import router as admin_orders_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router)
api_router.include_router(profile_router)
api_router.include_router(shipping_router)
api_router.include_router(orders_router)
api_router.include_router(payments_router)
api_router.include_router(admin_carriers_router)
api_router.include_router(admin_customers_router)
api_router.include_router(admin_orders_router)
