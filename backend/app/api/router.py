from fastapi import APIRouter

from app.api.v1.address_book import router as address_book_router
from app.api.v1.admin_audit import router as admin_audit_router
from app.api.v1.admin_carrier_api import router as admin_carrier_api_router
from app.api.v1.admin_carrier_webhooks import router as admin_carrier_webhooks_router
from app.api.v1.admin_cancellations import router as admin_cancellations_router
from app.api.v1.admin_carriers import router as admin_carriers_router
from app.api.v1.admin_commission_configs import (
    router as admin_commission_configs_router,
)
from app.api.v1.admin_commissions import router as admin_commissions_router
from app.api.v1.admin_customers import router as admin_customers_router
from app.api.v1.admin_orders import router as admin_orders_router
from app.api.v1.admin_payments import router as admin_payments_router
from app.api.v1.admin_settings import router as admin_settings_router
from app.api.v1.auth import router as auth_router
from app.api.v1.carrier_portal import router as carrier_portal_router
from app.api.v1.carrier_tracking import router as carrier_tracking_router
from app.api.v1.cse import admin_router as cse_admin_router, router as cse_router
from app.api.v1.documents import router as documents_router
from app.api.v1.health import router as health_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.orders import router as orders_router
from app.api.v1.partners import router as partners_router
from app.api.v1.payments import router as payments_router
from app.api.v1.profile import router as profile_router
from app.api.v1.public_tracking import router as public_tracking_router
from app.api.v1.reviews import router as reviews_router
from app.api.v1.shipping import router as shipping_router
from app.api.v1.tracking import router as tracking_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router)
api_router.include_router(profile_router)
api_router.include_router(address_book_router)
api_router.include_router(shipping_router)
api_router.include_router(orders_router)
api_router.include_router(tracking_router)
api_router.include_router(payments_router)
api_router.include_router(notifications_router)
api_router.include_router(admin_carriers_router)
api_router.include_router(admin_cancellations_router)
api_router.include_router(admin_customers_router)
api_router.include_router(admin_orders_router)
api_router.include_router(admin_commissions_router)
api_router.include_router(admin_settings_router)
api_router.include_router(admin_carrier_webhooks_router)
api_router.include_router(admin_payments_router)
api_router.include_router(carrier_tracking_router)
api_router.include_router(carrier_portal_router)
api_router.include_router(reviews_router)
api_router.include_router(documents_router)
api_router.include_router(admin_commission_configs_router)
api_router.include_router(admin_carrier_api_router)
api_router.include_router(admin_audit_router)
api_router.include_router(cse_router)
api_router.include_router(cse_admin_router)
api_router.include_router(public_tracking_router)
api_router.include_router(partners_router)
