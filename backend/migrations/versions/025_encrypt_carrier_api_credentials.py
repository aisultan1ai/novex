"""Encrypt existing plaintext api_token and api_url in carrier_api_credentials

Revision ID: 025_encrypt_carrier_creds
Revises: 024_carrier_integration
Create Date: 2026-06-20
"""

from __future__ import annotations

import base64
import hashlib
import os

from alembic import op
from sqlalchemy import text

revision = "025_encrypt_carrier_creds"
down_revision = "024_carrier_integration"
branch_labels = None
depends_on = None

_ENC_PREFIX = "enc:"


def _get_fernet():
    from cryptography.fernet import Fernet

    key = os.getenv("FIELD_ENCRYPTION_KEY", "")
    if not key:
        secret = os.getenv("SECRET_KEY", "dev-only-insecure-key")
        derived = hashlib.sha256(f"novex:field_enc:{secret}".encode()).digest()
        key = base64.urlsafe_b64encode(derived).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        text("SELECT id, api_token, api_url FROM carrier_api_credentials")
    ).fetchall()

    if not rows:
        return

    fernet = _get_fernet()
    for row in rows:
        updates: dict[str, str] = {}
        if row.api_token and not row.api_token.startswith(_ENC_PREFIX):
            updates["api_token"] = _ENC_PREFIX + fernet.encrypt(row.api_token.encode()).decode()
        if row.api_url and not row.api_url.startswith(_ENC_PREFIX):
            updates["api_url"] = _ENC_PREFIX + fernet.encrypt(row.api_url.encode()).decode()
        if updates:
            set_clause = ", ".join(f"{k} = :{k}" for k in updates)
            conn.execute(
                text(f"UPDATE carrier_api_credentials SET {set_clause} WHERE id = :id"),
                {**updates, "id": row.id},
            )


def downgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        text("SELECT id, api_token, api_url FROM carrier_api_credentials")
    ).fetchall()

    if not rows:
        return

    fernet = _get_fernet()
    for row in rows:
        updates: dict[str, str] = {}
        if row.api_token and row.api_token.startswith(_ENC_PREFIX):
            updates["api_token"] = fernet.decrypt(row.api_token[len(_ENC_PREFIX):].encode()).decode()
        if row.api_url and row.api_url.startswith(_ENC_PREFIX):
            updates["api_url"] = fernet.decrypt(row.api_url[len(_ENC_PREFIX):].encode()).decode()
        if updates:
            set_clause = ", ".join(f"{k} = :{k}" for k in updates)
            conn.execute(
                text(f"UPDATE carrier_api_credentials SET {set_clause} WHERE id = :id"),
                {**updates, "id": row.id},
            )
