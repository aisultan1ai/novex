from __future__ import annotations

import os
import time

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-only")
os.environ.setdefault("DATABASE_URL", "postgresql://x:x@localhost/x")


from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        h = get_password_hash("mypassword")
        assert h != "mypassword"

    def test_verify_correct_password(self):
        h = get_password_hash("secure123")
        assert verify_password("secure123", h) is True

    def test_verify_wrong_password(self):
        h = get_password_hash("secure123")
        assert verify_password("wrong", h) is False

    def test_same_password_different_hashes(self):
        h1 = get_password_hash("abc")
        h2 = get_password_hash("abc")
        assert h1 != h2  # bcrypt uses random salt


class TestJwtTokens:
    def test_create_and_decode(self):
        payload = {"sub": "42", "email": "user@example.com", "role": "customer"}
        token = create_access_token(payload)
        decoded = decode_access_token(token)
        assert decoded["sub"] == "42"
        assert decoded["email"] == "user@example.com"

    def test_decode_invalid_token_raises(self):
        with pytest.raises(ValueError):
            decode_access_token("not.a.valid.token")

    def test_decode_tampered_token_raises(self):
        token = create_access_token({"sub": "1"})
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(ValueError):
            decode_access_token(tampered)
