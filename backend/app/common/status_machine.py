from __future__ import annotations

ALLOWED_ORDER_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["shipment_details_completed", "cancelled"],
    "shipment_details_completed": ["ready_for_checkout", "cancelled"],
    "ready_for_checkout": ["awaiting_payment", "cancelled"],
    "awaiting_payment": ["payment_under_review", "cancelled"],
    "payment_under_review": ["paid", "payment_rejected", "cancelled"],
    "paid": ["dispatch_queued", "cancelled"],
    "dispatch_queued": ["sent_to_carrier", "dispatch_failed"],
    "sent_to_carrier": [
        "picked_up", "out_for_delivery", "in_transit",
        "delivered", "return_requested", "delivery_failed", "customs_hold",
    ],
    "picked_up": ["out_for_delivery", "in_transit", "delivered", "return_requested", "delivery_failed", "customs_hold"],
    "in_transit": ["arrived", "out_for_delivery", "delivered", "return_requested", "delivery_failed", "customs_hold"],
    "out_for_delivery": ["delivered", "return_requested", "delivery_failed"],
    "delivery_failed": ["out_for_delivery", "in_transit", "return_requested", "delivered"],
    "customs_hold": ["in_transit", "delivered", "return_requested"],
    "arrived": ["out_for_delivery", "delivered", "return_requested"],
    "delivered": ["return_requested"],
    "return_requested": ["return_in_progress", "cancelled"],
    "return_in_progress": ["returned"],
    "returned": [],
    "cancelled": [],
    "payment_rejected": ["awaiting_payment", "cancelled"],
    "dispatch_failed": ["dispatch_queued", "cancelled"],
    "pending_manual_dispatch": ["dispatch_queued", "cancelled"],
    "pending_manual": ["dispatch_queued", "cancelled"],
}


class InvalidTransitionError(ValueError):
    pass


def transition_order(current_status: str, new_status: str) -> None:
    allowed = ALLOWED_ORDER_TRANSITIONS.get(current_status, [])
    if new_status not in allowed:
        raise InvalidTransitionError(
            f"Cannot transition order from '{current_status}' to '{new_status}'. "
            f"Allowed: {allowed}"
        )


def can_transition(current_status: str, new_status: str) -> bool:
    return new_status in ALLOWED_ORDER_TRANSITIONS.get(current_status, [])
