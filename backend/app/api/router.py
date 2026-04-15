from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.profile import router as profile_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router)
api_router.include_router(profile_router)

# api_router.include_router(shipping_router, prefix="/shipping", tags=["shipping"])
# api_router.include_router(orders_router, prefix="/orders", tags=["orders"])