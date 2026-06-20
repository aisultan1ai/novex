from __future__ import annotations

from app.core.dependencies import get_current_user, require_admin
from app.main import app
from app.modules.identity.models import RoleCode
from tests.api.conftest import make_mock_user


# ---------------------------------------------------------------------------
# GET /admin/users/stats — requires ADMIN role
# ---------------------------------------------------------------------------


def test_admin_stats_customer_gets_403(client, mock_db):
    customer = make_mock_user(1, RoleCode.CUSTOMER)
    app.dependency_overrides[get_current_user] = lambda: customer
    r = client.get("/api/v1/admin/users/stats")
    assert r.status_code == 403


def test_admin_stats_admin_gets_200(client, mock_db):
    admin = make_mock_user(2, RoleCode.ADMIN)
    app.dependency_overrides[require_admin] = lambda: admin
    mock_db.scalar.return_value = 0
    r = client.get("/api/v1/admin/users/stats")
    assert r.status_code == 200
    body = r.json()
    assert "total_users" in body
    assert "total_orders" in body


# ---------------------------------------------------------------------------
# GET /admin/orders — requires ADMIN role
# ---------------------------------------------------------------------------


def test_admin_orders_customer_gets_403(client):
    customer = make_mock_user(1, RoleCode.CUSTOMER)
    app.dependency_overrides[get_current_user] = lambda: customer
    r = client.get("/api/v1/admin/orders")
    assert r.status_code == 403
