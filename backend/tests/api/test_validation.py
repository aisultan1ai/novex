from __future__ import annotations

# Pydantic validation runs before dependencies are called, so no DB/service
# mocks are needed — a 422 is returned before any business logic executes.


def test_register_invalid_email_returns_422(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "securepass1"},
        headers={"X-Real-IP": "10.1.0.1"},
    )
    assert r.status_code == 422


def test_register_short_password_returns_422(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "valid@example.com", "password": "short"},
        headers={"X-Real-IP": "10.1.0.1"},
    )
    assert r.status_code == 422


def test_shipping_quote_negative_weight_returns_422(client):
    r = client.post(
        "/api/v1/shipping/quote",
        json={
            "from_country": "KZ",
            "from_city": "Almaty",
            "to_country": "KZ",
            "to_city": "Astana",
            "shipment_type": "parcel",
            "weight_kg": -1,
            "quantity": 1,
            "width_cm": 10,
            "height_cm": 10,
            "depth_cm": 10,
        },
        headers={"X-Real-IP": "10.1.0.2"},
    )
    assert r.status_code == 422


def test_shipping_quote_zero_quantity_returns_422(client):
    r = client.post(
        "/api/v1/shipping/quote",
        json={
            "from_country": "KZ",
            "from_city": "Almaty",
            "to_country": "KZ",
            "to_city": "Astana",
            "shipment_type": "parcel",
            "weight_kg": 1.5,
            "quantity": 0,
            "width_cm": 10,
            "height_cm": 10,
            "depth_cm": 10,
        },
        headers={"X-Real-IP": "10.1.0.2"},
    )
    assert r.status_code == 422
