import base64
import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import (
    ALGORITHM,
    MAX_PASSWORD_BYTES,
    create_access_token,
    decode_access_token,
    ensure_jwt_secret_configured,
    hash_password,
    verify_password,
)
from app.schemas.auth import LoginRequest


@pytest.fixture(autouse=True)
def _fast_bcrypt(monkeypatch):
    monkeypatch.setattr(get_settings(), "bcrypt_rounds", 4)


def test_hash_is_bcrypt_salted_and_not_plaintext():
    first, second = hash_password("Sup3r-secret!"), hash_password("Sup3r-secret!")
    assert first.startswith("$2b$") and len(first) == 60
    assert "Sup3r-secret!" not in first
    assert first != second


def test_verify_password():
    hashed = hash_password("Sup3r-secret!")
    assert verify_password("Sup3r-secret!", hashed)
    assert not verify_password("sup3r-secret!", hashed)
    assert not verify_password("", hashed)


def test_verify_rejects_overlong_password_and_malformed_hash_instead_of_crashing():
    hashed = hash_password("short")
    assert not verify_password("x" * (MAX_PASSWORD_BYTES + 1), hashed)
    assert not verify_password("anything", "not-a-bcrypt-hash")


def test_hash_cost_follows_configuration():
    assert hash_password("x").startswith("$2b$04$")


def test_token_round_trip():
    assert decode_access_token(create_access_token(42)) == 42


def test_token_contains_no_role_or_secret():
    payload = jwt.decode(create_access_token(7), options={"verify_signature": False})
    assert set(payload) == {"sub", "iat", "exp"}


def test_expired_token_is_rejected():
    assert decode_access_token(create_access_token(1, expires_delta=timedelta(seconds=-5))) is None


def test_tampered_and_foreign_tokens_are_rejected():
    token = create_access_token(1)
    header, payload, signature = token.split(".")
    forged_payload = base64.urlsafe_b64encode(json.dumps({"sub": "2", "exp": 9999999999}).encode()).rstrip(b"=")
    assert decode_access_token(f"{header}.{forged_payload.decode()}.{signature}") is None
    assert decode_access_token(token[:-3] + ("AAA" if not token.endswith("AAA") else "BBB")) is None

    foreign = jwt.encode({"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "x" * 40, ALGORITHM)
    assert decode_access_token(foreign) is None


def test_unsigned_alg_none_token_is_rejected():
    def part(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    unsigned = f"{part({'alg': 'none', 'typ': 'JWT'})}.{part({'sub': '1', 'exp': 9999999999})}."
    assert decode_access_token(unsigned) is None


def test_token_without_required_claims_or_with_bad_subject_is_rejected():
    secret = get_settings().jwt_secret
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    assert decode_access_token(jwt.encode({"sub": "1"}, secret, ALGORITHM)) is None
    assert decode_access_token(jwt.encode({"exp": future}, secret, ALGORITHM)) is None
    assert decode_access_token(jwt.encode({"sub": "abc", "exp": future}, secret, ALGORITHM)) is None
    assert decode_access_token("not.a.jwt") is None
    assert decode_access_token("") is None


def test_missing_or_weak_secret_is_refused(monkeypatch):
    monkeypatch.setattr(get_settings(), "jwt_secret", "")
    with pytest.raises(RuntimeError):
        ensure_jwt_secret_configured()
    monkeypatch.setattr(get_settings(), "jwt_secret", "too-short")
    with pytest.raises(RuntimeError):
        create_access_token(1)


def test_passwords_are_masked_in_reprs():
    request = LoginRequest(email="a@b.c", password="Plaintext-Password-1")
    assert "Plaintext-Password-1" not in repr(request)
    assert "Plaintext-Password-1" not in str(request.model_dump())
