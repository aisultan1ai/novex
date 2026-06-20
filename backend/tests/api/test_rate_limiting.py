from __future__ import annotations

from unittest.mock import patch

from app.core.exceptions import UnauthorizedError

# The login endpoint is limited to 10 requests/minute per IP.
# We use a dedicated IP so the counter does not bleed into other tests.
_RATE_TEST_IP = "203.0.113.1"  # TEST-NET-3, safe to use in test suites


def test_login_rate_limit_429_on_11th_request(client):
    """Requests 1–10 are processed (bad password → 401). Request 11 → 429."""
    with patch(
        "app.api.v1.auth.identity_service.authenticate_user",
        side_effect=UnauthorizedError("bad credentials"),
    ):
        statuses = []
        for _ in range(11):
            r = client.post(
                "/api/v1/auth/login",
                json={"email": "brute@example.com", "password": "wrongpass1"},
                headers={"X-Real-IP": _RATE_TEST_IP},
            )
            statuses.append(r.status_code)

    # First 10 requests hit the endpoint (rate limit not exceeded) → 401
    assert all(s == 401 for s in statuses[:10]), f"Expected 401s, got: {statuses[:10]}"
    # 11th request is rejected by the limiter before reaching the handler → 429
    assert statuses[10] == 429, f"Expected 429 on request 11, got: {statuses[10]}"
