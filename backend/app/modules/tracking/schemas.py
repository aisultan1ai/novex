from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TrackingEventCreate(BaseModel):
    status: str
    description: str | None = None
    location: str | None = None
    carrier_status: str | None = None


class TrackingEventResponse(BaseModel):
    id: int
    order_draft_id: int
    status: str
    description: str | None
    location: str | None
    carrier_status: str | None
    occurred_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class TrackingHistoryResponse(BaseModel):
    order_draft_id: int
    # Frontend needs this to decide whether to prefer raw carrier description
    # over the normalized internal status label (per-carrier UX).
    carrier_code: str
    events: list[TrackingEventResponse]


class PublicTrackingEventResponse(BaseModel):
    status: str
    description: str | None
    location: str | None
    occurred_at: datetime

    model_config = {"from_attributes": True}


class DeliveryInfo(BaseModel):
    # Populated only after the shipment reaches a terminal delivered state.
    # `delivered_at` is the occurred_at of the last event mapped to `delivered`.
    #
    # ВАЖНО: этот блок отдаётся из ПУБЛИЧНОГО эндпоинта отслеживания (кто угодно,
    # имеющий трек-номер). Персональные данные получателя (ФИО, адрес) сюда НЕ
    # включаются, чтобы не превращать трекинг в утечку PII. Если понадобится
    # показать эти поля владельцу заказа, нужна отдельная авторизованная схема.
    delivered_at: datetime


class PublicTrackingResponse(BaseModel):
    tracking_number: str
    carrier_code: str
    carrier_name: str
    from_city: str
    to_city: str
    order_status: str
    eta_days_min: int
    eta_days_max: int
    created_at: datetime
    events: list[PublicTrackingEventResponse]
    delivery: DeliveryInfo | None = None
