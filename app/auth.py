"""Password hashing and API token (PAT) helpers for doction."""

from __future__ import annotations

import hashlib
import hmac
import secrets


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        200_000,
    )
    return f"{salt}${digest.hex()}"


TOKEN_PREFIX = "doction_"


def generate_api_token() -> str:
    return TOKEN_PREFIX + secrets.token_hex(20)


def hash_api_token(token: str) -> str:
    # High-entropy random secret: plain SHA-256 is enough (no salt/stretching needed).
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    try:
        salt, digest = hashed.split("$", 1)
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        200_000,
    ).hex()
    return hmac.compare_digest(candidate, digest)
