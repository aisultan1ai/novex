"""
Fernet (AES-128-CBC + HMAC-SHA256) transparent column encryption.

Set FIELD_ENCRYPTION_KEY to a URL-safe base64 32-byte key in production:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

In development, a key is derived from SECRET_KEY automatically — no extra config needed.
"""
from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

_ENC_PREFIX = "enc:"


def _get_fernet() -> Fernet:
    key = os.getenv("FIELD_ENCRYPTION_KEY", "")
    if not key:
        # Dev/CI fallback: stable key derived from SECRET_KEY.
        # NEVER rely on this in production — set FIELD_ENCRYPTION_KEY explicitly.
        secret = os.getenv("SECRET_KEY", "dev-only-insecure-key")
        derived = hashlib.sha256(f"novex:field_enc:{secret}".encode()).digest()
        key = base64.urlsafe_b64encode(derived).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


class EncryptedText(TypeDecorator):
    """Transparently encrypts text columns using Fernet symmetric encryption.

    Encrypted values are stored with an ``enc:`` prefix so existing plaintext
    rows remain readable during rolling migration — they are re-encrypted on
    the next write.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:  # type: ignore[override]
        if value is None:
            return None
        return _ENC_PREFIX + _get_fernet().encrypt(value.encode()).decode()

    def process_result_value(self, value: str | None, dialect) -> str | None:  # type: ignore[override]
        if value is None:
            return None
        if value.startswith(_ENC_PREFIX):
            return _get_fernet().decrypt(value[len(_ENC_PREFIX):].encode()).decode()
        return value  # legacy plaintext — re-encrypted on next write
