from fastapi import APIRouter

from app.api.v1.health import router as health_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])

# api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
# api_router.include_router(profile_router, prefix="/profile", tags=["profile"])
# api_router.include_router(shipping_router, prefix="/shipping", tags=["shipping"])
# api_router.include_router(orders_router, prefix="/orders", tags=["orders"])