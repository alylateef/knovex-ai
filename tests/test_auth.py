"""
Knovex AI - Unit Tests for Authentication, Password Hashing & Security
"""

import pytest
from knovex.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hashing():
    raw_pass = "SuperSecureP@ssword123!"
    hashed = hash_password(raw_pass)

    assert hashed != raw_pass
    assert verify_password(raw_pass, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_create_and_decode():
    user_id = "user-1234"
    tenant_id = "tenant-abcd"
    role = "admin"
    email = "admin@knovex.ai"

    token, jti = create_access_token(user_id=user_id, tenant_id=tenant_id, role=role, email=email)
    assert token is not None
    assert len(jti) > 0

    token_data = decode_access_token(token)
    assert token_data is not None
    assert token_data.user_id == user_id
    assert token_data.tenant_id == tenant_id
    assert token_data.role == role
    assert token_data.email == email


def test_invalid_jwt_token():
    invalid_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature"
    token_data = decode_access_token(invalid_token)
    assert token_data is None
