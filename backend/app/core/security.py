from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
PASSWORD_HASH_ITERATIONS = 100_000


def _secret_key() -> str:
    key = os.getenv("SECRET_KEY", "")
    if not key:
        raise RuntimeError(
            "SECRET_KEY environment variable is not set. "
            'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'  # noqa: E501
        )
    return key


def get_password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${salt}${password_hash}"


def verify_password(plain_password: str, stored_password_hash: str) -> bool:
    try:
        algorithm, iterations_str, salt_hex, expected_hash = stored_password_hash.split(
            "$", 3
        )
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    try:
        iterations = int(iterations_str)
    except ValueError:
        return False

    computed_hash = hashlib.pbkdf2_hmac(
        "sha256",
        plain_password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        iterations,
    ).hex()

    return hmac.compare_digest(computed_hash, expected_hash)


def create_access_token(
    subject: dict[str, Any],
    expires_minutes: int | None = None,
) -> str:
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=expires_minutes or ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {**subject, "iat": now, "exp": expire}
    return jwt.encode(payload, _secret_key(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, _secret_key(), algorithms=[JWT_ALGORITHM])
    except ExpiredSignatureError as exc:
        raise ValueError("Token has expired") from exc
    except InvalidTokenError as exc:
        raise ValueError(f"Invalid token: {exc}") from exc


# ---------------------------------------------------------------------------
# Token versioning — enables immediate revocation without a DB migration.
# Version is stored in Redis (key: user:tkver:<user_id>).
# Incrementing the version in Redis invalidates all existing tokens for a user.
# ---------------------------------------------------------------------------

_TOKEN_VER_PREFIX = "user:tkver:"
_REFRESH_PREFIX = "refresh:"
REFRESH_TOKEN_TTL_SECONDS = 7 * 24 * 3600  # 7 days


def get_token_version(user_id: int) -> int:
    """Return the current token version for a user. Defaults to 0."""
    try:
        from app.core.redis import get_redis
        val = get_redis().get(f"{_TOKEN_VER_PREFIX}{user_id}")
        return int(val) if val else 0
    except Exception:
        return 0  # fail open — don't lock everyone out if Redis is temporarily down


def invalidate_user_tokens(user_id: int) -> None:
    """Invalidate all active tokens for a user by incrementing the version counter."""
    from app.core.redis import get_redis
    get_redis().incr(f"{_TOKEN_VER_PREFIX}{user_id}")


# ---------------------------------------------------------------------------
# Refresh tokens — opaque tokens stored in Redis with 7-day TTL.
# Each token maps to a user_id. Rotation on every use prevents replay.
# ---------------------------------------------------------------------------

def create_refresh_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    from app.core.redis import get_redis
    get_redis().setex(f"{_REFRESH_PREFIX}{token}", REFRESH_TOKEN_TTL_SECONDS, str(user_id))
    return token


_CONSUME_SCRIPT = """
local val = redis.call('GET', KEYS[1])
if val then redis.call('DEL', KEYS[1]) end
return val
"""


def consume_refresh_token(token: str) -> int | None:
    """Validate and atomically delete a refresh token. Returns user_id or None if invalid."""
    from app.core.redis import get_redis
    r = get_redis()
    key = f"{_REFRESH_PREFIX}{token}"
    val = r.eval(_CONSUME_SCRIPT, 1, key)
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def revoke_refresh_token(token: str) -> None:
    from app.core.redis import get_redis
    get_redis().delete(f"{_REFRESH_PREFIX}{token}")
